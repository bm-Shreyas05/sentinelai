"""REST API.

Auth: every /v1 route requires an `X-API-Key` header matching SENTINEL_API_KEYS.
Rate limiting: token bucket per API key (SENTINEL_RATE_LIMIT_PER_MIN).
Interactive docs at /docs. The web console (web/, built to web/dist) is served at /.
"""
import logging, os, secrets, threading, time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import __version__
from .console import ROOT, DemoTraffic, build_router
from .engine import SentinelEngine

ENGINE: Optional[SentinelEngine] = None
TRAFFIC: Optional[DemoTraffic] = None
WEB_DIST = Path(os.environ.get("SENTINEL_WEB_DIST", ROOT / "web" / "dist"))


def _start_demo():
    """SENTINEL_DEMO=1: warm up customer histories, then keep simulated traffic flowing."""
    try:
        traffic().warm_up()
        traffic().set(running=True)
    except Exception:
        logging.getLogger("sentinelai.console").exception("demo start failed")


@asynccontextmanager
async def lifespan(app):
    global ENGINE
    if ENGINE is None:
        ENGINE = SentinelEngine()
    if os.environ.get("SENTINEL_DEMO") == "1":
        threading.Thread(target=_start_demo, name="demo-start", daemon=True).start()
    yield
    if TRAFFIC is not None:
        TRAFFIC.set(running=False)


app = FastAPI(title="SentinelAI", version=__version__, lifespan=lifespan,
              description="Real-time fraud scoring, explanation and case management for Indian payments.")


class _Bucket:
    def __init__(self, per_min):
        self.rate, self.cap = per_min / 60.0, float(per_min)
        self.state, self.lock = {}, threading.Lock()

    def take(self, key):
        with self.lock:
            tokens, last = self.state.get(key, (self.cap, time.monotonic()))
            now = time.monotonic()
            tokens = min(self.cap, tokens + (now - last) * self.rate)
            if tokens < 1:
                self.state[key] = (tokens, now); return False
            self.state[key] = (tokens - 1, now); return True


_bucket = None


def engine() -> SentinelEngine:
    if ENGINE is None:
        raise HTTPException(503, "engine not initialised")
    return ENGINE


def traffic() -> DemoTraffic:
    global TRAFFIC
    if TRAFFIC is None or TRAFFIC.eng is not engine():
        TRAFFIC = DemoTraffic(engine())
    return TRAFFIC


def require_key(x_api_key: str = Header(default="")):
    global _bucket
    eng = engine()
    if not any(secrets.compare_digest(x_api_key, k) for k in eng.settings.api_keys):
        raise HTTPException(401, "invalid or missing X-API-Key")
    if _bucket is None:
        _bucket = _Bucket(eng.settings.rate_limit_per_min)
    if not _bucket.take(x_api_key):
        raise HTTPException(429, "rate limit exceeded")
    return x_api_key


class TransactionIn(BaseModel):
    txn_id: Optional[str] = Field(None, max_length=64)
    user_id: str = Field(..., min_length=1, max_length=64)
    amount: float = Field(..., gt=0, le=1e9, description="Amount in INR")
    city: str = Field(..., min_length=1, max_length=64)
    device_id: str = Field(..., min_length=1, max_length=128)
    category: str = Field("online_shopping", max_length=32)
    merchant: Optional[str] = Field(None, max_length=128)
    payee: Optional[str] = Field(None, max_length=128,
                                 description="Beneficiary, e.g. the UPI ID for a p2p_transfer; defaults to merchant")
    channel: Literal["card", "upi", "netbanking", "wallet"] = "card"
    ts: Optional[float] = Field(None, description="Unix epoch seconds; defaults to now")


class Resolution(BaseModel):
    is_fraud: bool
    analyst: str = Field(..., min_length=1, max_length=64)
    notes: str = Field("", max_length=2000)


class Question(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


@app.get("/health")
def health():
    eng = engine()
    return {"status": "ok", "version": __version__, "model_version": eng.bundle.version}


@app.post("/v1/transactions", dependencies=[Depends(require_key)])
def score_transaction(txn: TransactionIn):
    try:
        return engine().score(txn.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.post("/v1/webhooks/transactions", dependencies=[Depends(require_key)])
async def ingest_batch(request: Request):
    """Bulk ingestion for payment-switch webhooks: a JSON list of transactions, scored in order."""
    body = await request.json()
    items = body if isinstance(body, list) else body.get("transactions", [])
    if not items or len(items) > 1000:
        raise HTTPException(422, "send 1-1000 transactions")
    out = []
    for raw in items:
        try:
            out.append(engine().score(TransactionIn(**raw).model_dump(exclude_none=True), actor="webhook"))
        except Exception as exc:
            out.append({"error": str(exc), "input": raw.get("txn_id")})
    return {"results": out}


@app.get("/v1/transactions/{txn_id}", dependencies=[Depends(require_key)])
def get_transaction(txn_id: str):
    try:
        return engine().get_transaction(txn_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@app.get("/v1/users/{user_id}/history", dependencies=[Depends(require_key)])
def user_history(user_id: str, limit: int = Query(20, ge=1, le=200)):
    return engine().user_history(user_id, limit)


@app.get("/v1/cases", dependencies=[Depends(require_key)])
def list_cases(status: Literal["open", "confirmed_fraud", "false_positive", "all"] = "open",
               limit: int = Query(100, ge=1, le=500)):
    return engine().list_cases(None if status == "all" else status, limit)


@app.get("/v1/cases/{case_id}", dependencies=[Depends(require_key)])
def get_case(case_id: int):
    try:
        return engine().get_case(case_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))


@app.post("/v1/cases/{case_id}/resolve", dependencies=[Depends(require_key)])
def resolve_case(case_id: int, body: Resolution):
    try:
        return engine().resolve_case(case_id, body.is_fraud, body.analyst, body.notes)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@app.get("/v1/metrics", dependencies=[Depends(require_key)])
def metrics(window_s: int = Query(3600, ge=60, le=10**9)):
    return engine().live_metrics(window_s)


@app.get("/v1/drift", dependencies=[Depends(require_key)])
def drift(window: int = Query(2000, ge=100, le=50_000)):
    return engine().drift(window)


@app.post("/v1/policy/ask", dependencies=[Depends(require_key)])
def ask_policy(q: Question):
    return engine().ask_policy(q.question)


@app.get("/v1/models", dependencies=[Depends(require_key)])
def models():
    eng = engine()
    return {"current": eng.bundle.version, "versions": eng.registry.versions()}


@app.post("/v1/models/reload", dependencies=[Depends(require_key)])
def reload_model():
    return {"current": engine().reload_model()}


app.include_router(build_router(engine, traffic), dependencies=[Depends(require_key)])


# ── web console: static build with client-side routing ───────────────────────
@app.get("/{path:path}", include_in_schema=False)
def web_console(path: str):
    if path.startswith(("v1/", "docs", "openapi.json", "health")):
        raise HTTPException(404)
    index = WEB_DIST / "index.html"
    if not index.exists():
        raise HTTPException(404, "web console not built: cd web && npm ci && npm run build")
    f = (WEB_DIST / path).resolve()
    if path and f.is_file() and f.is_relative_to(WEB_DIST.resolve()):
        return FileResponse(f)
    return FileResponse(index)
