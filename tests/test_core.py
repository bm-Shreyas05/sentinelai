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


def test_warm_up_persists_histories_without_scoring(tmp_path):
    from sentinelai import db
    from sentinelai.features import warm_up
    from sentinelai.synthetic import Simulator
    conn = db.connect(tmp_path / "w.db")
    events = list(Simulator(n_users=50, seed=3).stream(2000))
    assert warm_up(FeatureStore(conn), events) == len(events)
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
    replayed = FeatureStore()
    for e in events:
        replayed.update(e)
    nxt = dict(events[-1], ts=events[-1]["ts"] + 60)
    assert FeatureStore(conn).compute(nxt)[0] == replayed.compute(nxt)[0]


def test_drift_ignores_partial_day_and_ageing_customers():
    import json, sqlite3
    from types import SimpleNamespace
    from sentinelai.drift import drift_report
    from sentinelai.features import FEATURES
    conn = sqlite3.connect(":memory:"); conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE transactions (features TEXT, score REAL, ts REAL, model_version TEXT, created_at REAL)")
    rng = np.random.default_rng(0)
    edges = [-1.0, 0.5, 1.0, 2.0]
    ref = {"features": {f: {"edges": edges, "props": [0.3, 0.4, 0.3]} for f in FEATURES},
           "score": {"edges": [0, 0.5, 1], "props": [0.9, 0.1]}, "cold_start_share": 0.1}
    ref["features"]["hour"] = {"edges": list(np.arange(-0.5, 24)), "props": [1 / 24] * 24}

    def report(hours, history):
        conn.execute("DELETE FROM transactions")
        for k in range(300):
            f = {n: float(rng.choice([0.0, 0.75, 1.5])) for n in FEATURES}
            f["hour"], f["history_log"] = float(k % hours), history
            conn.execute("INSERT INTO transactions VALUES (?,?,?,?,?)",
                         (json.dumps(f), 0.8 if k % 10 == 0 else 0.01, k * hours * 3600 / 300, "v1", k))
        d = drift_report(conn, SimpleNamespace(version="v1", reference=ref))
        return {f["feature"]: f for f in d["features"]}, d

    f, d = report(hours=6, history=4.0)                  # morning-only window, long-standing customers
    assert f["hour"]["status"] == "partial_day" and f["history_log"]["status"] == "stable"
    assert not d["retrain_recommended"]
    f, d = report(hours=30, history=0.0)                  # a full day, all cold-start customers
    assert f["hour"]["status"] == "critical" and f["history_log"]["status"] == "critical"


def test_llm_narrative_request(engine, monkeypatch):
    from sentinelai import agent
    sent = {}

    class Resp:
        def raise_for_status(self): pass
        def json(self): return {"stop_reason": "end_turn",
                                "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "Narrative."}]}

    def post(url, timeout, headers, json):
        sent.update(headers=headers, json=json); return Resp()

    monkeypatch.setattr(agent.httpx, "post", post)
    monkeypatch.setattr(engine.settings, "anthropic_api_key", "k")
    inv = agent.Investigator(engine)
    assert inv._narrative({}, {}, [], "s") == "Narrative."
    assert sent["json"]["model"] == "claude-opus-5-5" and sent["json"]["fallbacks"] == "default"
    assert "thinking" not in sent["json"] and "temperature" not in sent["json"]
    monkeypatch.setattr(engine.settings, "llm_model", "claude-haiku-4-5")
    inv._narrative({}, {}, [], "s")
    assert "fallbacks" not in sent["json"] and "anthropic-beta" not in sent["headers"]
