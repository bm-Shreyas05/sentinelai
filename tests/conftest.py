import os, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def settings(tmp_path_factory):
    d = tmp_path_factory.mktemp("sentinel")
    os.environ.update(SENTINEL_DB_PATH=str(d / "t.db"), SENTINEL_MODEL_DIR=str(d / "models"),
                      SENTINEL_POLICY_DIR=str(ROOT / "policies"), SENTINEL_API_KEYS="test-key",
                      SENTINEL_RATE_LIMIT_PER_MIN="100000", ANTHROPIC_API_KEY="", ALERT_WEBHOOK_URL="", SMTP_HOST="")
    from sentinelai.config import get_settings
    from sentinelai.retrain import train_initial
    s = get_settings()
    train_initial(s, n_events=60_000, seed=5)
    return s


@pytest.fixture(scope="session")
def engine(settings):
    from sentinelai.engine import SentinelEngine
    from sentinelai.synthetic import Simulator
    eng = SentinelEngine(settings)
    for e in Simulator(n_users=300, seed=21).stream(4000):   # warm up customer histories
        e["txn_id"] = "W" + e["txn_id"]
        eng.score(e, actor="warmup")
    return eng


@pytest.fixture
def known_user(engine):
    """A warmed-up customer with an established history, home city and device."""
    uid = engine.conn.execute("SELECT user_id FROM transactions GROUP BY user_id "
                              "ORDER BY COUNT(*) DESC LIMIT 1").fetchone()["user_id"]
    st = engine.store._state(uid)
    return {"user_id": uid, "home": max(st["cities"], key=st["cities"].get), "device": st["devices"][0],
            "typical": st["ema"], "last_ts": st["last_ts"]}
