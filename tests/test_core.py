import numpy as np
import pytest

from sentinelai.drift import psi
from sentinelai.features import FeatureStore
from sentinelai.geo import haversine_km
from sentinelai.model import Registry


def test_haversine_known_distance():
    assert 1700 < haversine_km("Delhi", "Chennai") < 1800
    assert haversine_km("Pune", "Pune") == 0


def test_feature_store_persists_state_across_restart(engine, known_user):
    fresh = FeatureStore(engine.conn)            # new process, same database
    txn = {"user_id": known_user["user_id"], "amount": 500, "city": known_user["home"],
           "device_id": known_user["device"], "ts": known_user["last_ts"] + 3600}
    assert fresh.compute(txn)[0] == engine.store.compute(txn)[0]


def test_registry_roundtrip_is_exact(settings, engine):
    reg = Registry(settings.model_dir)
    loaded = reg.load()
    X = np.random.default_rng(0).normal(size=(50, len(loaded.features))).clip(0)
    assert np.allclose(loaded.predict_batch(X), engine.bundle.predict_batch(X))
    assert loaded.thresholds["review"] <= loaded.thresholds["block"]


def test_model_beats_chance_on_holdout(engine):
    m = engine.bundle.metrics
    assert m["pr_auc"] > 0.5 and m["roc_auc"] > 0.9


def test_psi_detects_shift_and_not_noise():
    rng = np.random.default_rng(1)
    ref = rng.normal(0, 1, 5000)
    edges = np.quantile(ref, np.linspace(0, 1, 11))
    props = np.histogram(ref, bins=edges)[0] / len(ref)
    assert psi(edges, props, rng.normal(0, 1, 2000)) < 0.05
    assert psi(edges, props, rng.normal(1.5, 1, 2000)) > 0.25


def test_payee_features_and_old_database_migration(tmp_path):
    import sqlite3
    from sentinelai import db
    old = tmp_path / "old.db"                    # a database created before payee support
    c = sqlite3.connect(old)
    c.execute("CREATE TABLE transactions (txn_id TEXT PRIMARY KEY, user_id TEXT, ts REAL, amount REAL, "
              "merchant TEXT, category TEXT, city TEXT, device_id TEXT, channel TEXT, score REAL, decision TEXT, "
              "model_version TEXT, features TEXT, contributions TEXT, reasons TEXT, label INTEGER, "
              "sim_label INTEGER, created_at REAL)")
    c.commit(); c.close()
    conn = db.connect(old)
    assert "payee" in {r["name"] for r in conn.execute("PRAGMA table_info(transactions)")}

    fs = FeatureStore(conn)
    p2p = lambda u, payee, ts: {"user_id": u, "amount": 2000, "city": "Pune", "device_id": f"d{u}",
                                "category": "p2p_transfer", "payee": payee, "ts": ts}
    for i in range(6):
        fs.update(p2p(f"U{i}", "COL1@upi", 1000 + i))
    f, ctx = FeatureStore(conn).compute(p2p("U9", "COL1@upi", 2000))     # state survives a restart
    assert f["is_new_payee"] == 1 and ctx["payee_other_senders"] == 6
    f, ctx = fs.compute(p2p("U0", "COL1@upi", 2000))                     # paid before; others excludes self
    assert f["is_new_payee"] == 0 and ctx["payee_other_senders"] == 5
    shop = {**p2p("U0", "", 2000), "category": "grocery", "payee": "grocery-PUN"}
    f, _ = fs.compute(shop)                                             # merchants: payee features off
    assert f["is_new_payee"] == 0 and f["payee_fan_in_log"] == 0
