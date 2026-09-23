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
