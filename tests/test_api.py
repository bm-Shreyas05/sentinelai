import pytest
from fastapi.testclient import TestClient

H = {"X-API-Key": "test-key"}


@pytest.fixture(scope="module")
def client(engine):
    from sentinelai import api
    api.ENGINE = engine
    with TestClient(api.app) as c:
        yield c


def test_auth_required(client):
    assert client.get("/v1/metrics").status_code == 401
    assert client.get("/v1/metrics", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/health").status_code == 200


def test_score_and_validation(client, known_user):
    body = {"user_id": known_user["user_id"], "amount": 450, "city": known_user["home"],
            "device_id": known_user["device"], "channel": "upi", "category": "grocery",
            "ts": known_user["last_ts"] + 40000}
    r = client.post("/v1/transactions", json=body, headers=H)
    assert r.status_code == 200 and r.json()["decision"] in ("ALLOW", "REVIEW", "BLOCK")
    assert client.get(f"/v1/transactions/{r.json()['txn_id']}", headers=H).status_code == 200
    assert client.post("/v1/transactions", json={**body, "amount": -1}, headers=H).status_code == 422
    assert client.post("/v1/transactions", json={**body, "channel": "cheque"}, headers=H).status_code == 422


def test_case_workflow(client):
    cases = client.get("/v1/cases", headers=H).json()
    assert cases
    cid = cases[0]["case_id"]
    assert client.get(f"/v1/cases/{cid}", headers=H).json()["trace"]
    r = client.post(f"/v1/cases/{cid}/resolve", json={"is_fraud": True, "analyst": "ravi"}, headers=H)
    assert r.status_code == 200
    assert client.post(f"/v1/cases/{cid}/resolve", json={"is_fraud": True, "analyst": "ravi"},
                       headers=H).status_code == 409
    assert client.get("/v1/cases/999999", headers=H).status_code == 404


def test_webhook_batch_and_policy(client, known_user):
    batch = [{"user_id": known_user["user_id"], "amount": 300 + i, "city": known_user["home"],
              "device_id": known_user["device"], "ts": known_user["last_ts"] + 50000 + i} for i in range(5)]
    r = client.post("/v1/webhooks/transactions", json=batch, headers=H)
    assert r.status_code == 200 and len(r.json()["results"]) == 5
    a = client.post("/v1/policy/ask", json={"question": "when do we file an STR?"}, headers=H).json()
    assert a["citations"][0]["id"] == "AML-1.1"


def test_rate_limit(engine):
    from sentinelai import api
    api._bucket = api._Bucket(per_min=3)
    with TestClient(api.app) as c:
        codes = [c.get("/v1/metrics", headers=H).status_code for _ in range(6)]
    api._bucket = None
    assert 429 in codes


def test_mcp_tools_registered(engine):
    import asyncio
    from sentinelai import mcp_server
    mcp_server._engine = engine
    names = {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert {"score_transaction", "get_case", "lookup_policy", "check_drift", "resolve_case"} <= names
    out = mcp_server.list_open_cases(5)                  # every tool returns one JSON object
    assert isinstance(out, dict) and "cases" in out
