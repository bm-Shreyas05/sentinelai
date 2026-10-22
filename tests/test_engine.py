import pytest


def _txn(u, **kw):
    t = {"user_id": u["user_id"], "amount": round(u["typical"]), "city": u["home"],
         "device_id": u["device"], "category": "grocery", "channel": "upi", "ts": u["last_ts"] + 7200}
    t.update(kw); return t


def test_normal_payment_is_allowed(engine, known_user):
    r = engine.score(_txn(known_user))
    assert r["decision"] == "ALLOW" and r["case_id"] is None


def test_takeover_pattern_is_blocked_with_full_case(engine, known_user):
    far = "Kolkata" if known_user["home"] != "Kolkata" else "Mumbai"
    r = engine.score(_txn(known_user, amount=known_user["typical"] * 40, city=far, device_id="never-seen",
                          category="electronics", ts=known_user["last_ts"] + 9000))
    assert r["decision"] == "BLOCK" and r["case_id"]
    codes = {x["code"] for x in r["reasons"]["risk"]}
    assert "amount" in codes and "device" in codes
    case = engine.get_case(r["case_id"])
    tools = [s["tool"] for s in case["trace"]]
    assert tools[:4] == ["get_transaction", "get_user_history", "lookup_policy", "assess_priority"]
    assert "notify_customer" in tools and case["policy_refs"]
    assert case["summary"]["actions"]


def test_recent_investigations_feed(engine, known_user):
    far = "Kolkata" if known_user["home"] != "Kolkata" else "Mumbai"
    r = engine.score(_txn(known_user, amount=known_user["typical"] * 30, city=far, device_id="feed-dev",
                          category="electronics", ts=known_user["last_ts"] + 9500), actor="mcp")
    feed = engine.recent_investigations(5)
    top = feed[0]
    assert top["case_id"] == r["case_id"] and top["actor"] == "mcp"
    assert top["trace"][0]["tool"] == "get_transaction" and top["agent_ms"] >= 0
    assert "notify_customer" in top["notified"]
    assert all(f["case_id"] < top["case_id"] for f in feed[1:])


def test_small_payment_on_new_device_is_never_blocked(engine, known_user):
    """Regression: the old heuristic scored a ₹64 payment on a new phone as 99% / BLOCK."""
    r = engine.score(_txn(known_user, amount=64, device_id="new-phone-xyz", category="atm", channel="card",
                          ts=known_user["last_ts"] + 20000))
    assert r["decision"] != "BLOCK"
    if r["model_decision"] == "BLOCK":                     # override must be explained for audit
        assert "policy_override" in r["reasons"]
    titles = " ".join(x["title"] for x in r["reasons"]["risk"]).lower()
    assert "large amount" not in titles          # regression: ₹64 was described as "unusually large"


def test_card_testing_burst_then_big_payment_is_still_blocked(engine, known_user):
    """The low-value cap must not let card testing through: the big follow-up is blocked."""
    t0, dev = known_user["last_ts"] + 60000, "tester-device"
    for i in range(6):
        engine.score(_txn(known_user, amount=20 + i, device_id=dev, category="online_shopping",
                          channel="card", ts=t0 + i * 20))
    r = engine.score(_txn(known_user, amount=known_user["typical"] * 8, device_id=dev,
                          category="electronics", channel="card", ts=t0 + 200))
    assert r["decision"] == "BLOCK"


def test_no_false_velocity_reasons(engine):
    """Regression: 'Rapid burst' was shown with 0 transactions in 5 minutes."""
    for row in engine.conn.execute("SELECT features, reasons FROM transactions WHERE decision!='ALLOW'"):
        import json
        f, r = json.loads(row["features"]), json.loads(row["reasons"])
        for reason in r["risk"]:
            if reason["code"] == "velocity":
                assert f["tx_count_5min"] >= 3 or f["tx_count_1h"] >= 6


def test_validation_and_duplicates(engine, known_user):
    with pytest.raises(ValueError):
        engine.score({"user_id": "u", "amount": 10})
    with pytest.raises(ValueError):
        engine.score(_txn(known_user, amount=-5))
    t = _txn(known_user, txn_id="DUP-1", ts=known_user["last_ts"] + 30000)
    engine.score(t)
    with pytest.raises(ValueError):
        engine.score(t)


def test_resolution_labels_transaction_and_blocks_double_resolve(engine):
    case = engine.list_cases("open")[0]
    out = engine.resolve_case(case["case_id"], is_fraud=False, analyst="asha", notes="customer confirmed")
    assert out["status"] == "false_positive"
    assert engine.get_transaction(case["txn_id"])["label"] == 0
    with pytest.raises(ValueError):
        engine.resolve_case(case["case_id"], True, "asha")
    actions = [r["action"] for r in engine.conn.execute("SELECT action FROM audit_log")]
    assert "case_resolved" in actions and "case_opened" in actions


def test_drift_report_and_metrics(engine):
    d = engine.drift(window=2000)
    assert d["ready"] and len(d["features"]) == len(engine.bundle.features)
    m = engine.live_metrics(10**9)
    assert m["transactions"] > 4000 and 0 < m["alert_rate"] < 0.2
