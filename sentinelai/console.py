"""Read models and demo controls for the web console (web/).

Everything here is mounted under /v1/console and needs the same X-API-Key as the rest of the
API. These routes only shape data for screens: scoring, cases and policy answers still go
through the engine and the public /v1 routes, so the console sees exactly what integrators see.
"""
import json, logging, threading, time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from . import db
from .geo import CITIES
from .reasons import customer_message

ROOT = Path(__file__).resolve().parent.parent
log = logging.getLogger("sentinelai.console")


class DemoTraffic:
    """Simulated payment traffic scored in a background thread, so the console has something to watch.
    In production transactions arrive through POST /v1/transactions or the webhook endpoint."""

    def __init__(self, engine):
        self.eng, self.rate, self.running = engine, 5, False
        self._stream, self._thread, self._lock = None, None, threading.Lock()

    def _next(self):
        if self._stream is None:
            from .synthetic import Simulator
            self._stream = Simulator(n_users=1500, seed=int(time.time()) % 1000, fraud_rate=0.006).stream(10**9)
        return next(self._stream)

    def warm_up(self, n=6000):
        """Give customers some history so the demo isn't all cold-start. No-op when data exists."""
        if self.eng.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]:
            return 0
        logging.getLogger("sentinelai.alerts").setLevel(logging.ERROR)
        for _ in range(n):
            e = self._next(); e["txn_id"] = f"B-{e['txn_id']}"
            self.eng.score(e, actor="bootstrap")
        return n

    def set(self, running=None, rate=None):
        with self._lock:
            if rate is not None:
                self.rate = int(rate)
            if running is not None:
                self.running = bool(running)
            if self.running and (self._thread is None or not self._thread.is_alive()):
                self._thread = threading.Thread(target=self._run, name="demo-traffic", daemon=True)
                self._thread.start()
        return self.state()

    def state(self):
        return {"running": self.running, "rate": self.rate}

    def _run(self):
        while self.running:
            t0 = time.monotonic()
            for _ in range(self.rate):
                e = self._next(); e["txn_id"] = f"L-{e['txn_id']}"
                try:
                    self.eng.score(e, actor="demo")
                except Exception as exc:          # a bad event must not kill the pump
                    log.error("demo traffic: %s", exc)
            time.sleep(max(0.0, 1.0 - (time.monotonic() - t0)))


class TrafficIn(BaseModel):
    running: Optional[bool] = None
    rate: Optional[int] = Field(None, ge=1, le=50)


def _top_reason(reasons):
    risk = (reasons or {}).get("risk") or []
    return risk[0]["title"] if risk else None


def build_router(engine, traffic) -> APIRouter:
    """`engine` and `traffic` are zero-argument callables, so tests can swap the engine."""
    r = APIRouter(prefix="/v1/console", tags=["console"])

    @r.get("/overview")
    def overview(window_s: int = Query(3600, ge=60, le=10**9), minutes: int = Query(30, ge=5, le=240)):
        """KPIs, alerts per minute, city and channel breakdowns and the score distribution."""
        eng = engine(); now = time.time(); since = now - window_s
        series = eng.conn.execute(
            "SELECT CAST(created_at/60 AS INT)*60 AS minute, COUNT(*) n, SUM(decision='REVIEW') review, "
            "SUM(decision='BLOCK') block, SUM(amount * (decision='BLOCK')) held FROM transactions "
            "WHERE created_at >= ? GROUP BY minute ORDER BY minute", (now - minutes * 60,)).fetchall()
        cities = eng.conn.execute(
            "SELECT city, COUNT(*) n, SUM(decision!='ALLOW') alerts, SUM(decision='BLOCK') block, "
            "SUM(amount * (decision='BLOCK')) held FROM transactions WHERE created_at >= ? GROUP BY city",
            (since,)).fetchall()
        channels = eng.conn.execute(
            "SELECT channel, COUNT(*) n, SUM(decision!='ALLOW') alerts FROM transactions "
            "WHERE created_at >= ? GROUP BY channel ORDER BY n DESC", (since,)).fetchall()
        hist = eng.conn.execute(
            "SELECT MIN(CAST(score*20 AS INT), 19) b, COUNT(*) n FROM transactions WHERE created_at >= ? "
            "GROUP BY b", (since,)).fetchall()
        bins = [0] * 20
        for h in hist:
            bins[h["b"]] = h["n"]
        return {
            "metrics": eng.live_metrics(window_s),
            "thresholds": eng.bundle.thresholds,
            "series": [dict(s) for s in series],
            "cities": [dict(c, lat=CITIES.get(c["city"], (None, None))[0], lon=CITIES.get(c["city"], (None, None))[1])
                       for c in cities],
            "channels": [dict(c) for c in channels],
            "score_histogram": bins,
            "traffic": traffic().state(),
            "server_time": now,
        }

    @r.get("/feed")
    def feed(limit: int = Query(40, ge=1, le=200), flagged: bool = False, after: float = 0):
        """Most recent scored transactions, newest first."""
        q = ("SELECT t.txn_id, t.created_at, t.user_id, t.amount, t.merchant, t.category, t.city, t.channel, "
             "t.device_id, t.score, t.decision, t.reasons, c.case_id FROM transactions t "
             "LEFT JOIN cases c USING(txn_id) WHERE t.created_at > ? ")
        if flagged:
            q += "AND t.decision != 'ALLOW' "
        rows = engine().conn.execute(q + "ORDER BY t.created_at DESC LIMIT ?", (after, limit)).fetchall()
        out = []
        for row in rows:
            d = db.row_to_dict(row)
            d["reason"] = _top_reason(d.pop("reasons")) if d["decision"] != "ALLOW" else None
            out.append(d)
        return out

    @r.get("/investigations")
    def investigations(limit: int = Query(30, ge=1, le=500), since: Optional[float] = None,
                       actor: Optional[str] = None):
        """The investigation agent's recent runs with their step traces, newest first."""
        q = ("SELECT c.case_id, c.txn_id, c.priority, c.status, c.trace, c.created_at, t.amount, t.user_id, "
             "t.city, t.merchant, t.channel, t.decision, t.score, "
             "(SELECT a.actor FROM audit_log a WHERE a.action='case_opened' "
             " AND json_extract(a.detail, '$.case_id')=c.case_id LIMIT 1) AS actor "
             "FROM cases c JOIN transactions t USING(txn_id) WHERE c.trace IS NOT NULL ")
        args = []
        if since is not None:
            q += "AND c.created_at >= ? "; args.append(since)
        if actor:
            q = f"SELECT * FROM ({q}) WHERE actor = ? "; args.append(actor)
        rows = [db.row_to_dict(x) for x in engine().conn.execute(q + "ORDER BY case_id DESC LIMIT ?",
                                                                   (*args, limit)).fetchall()]
        for x in rows:
            x["agent_ms"] = round(sum(s["ms"] or 0 for s in x["trace"]), 2)
            x["notified"] = [s["tool"] for s in x["trace"] if s["tool"].startswith("notify_")]
        actors = [a[0] for a in engine().conn.execute(
            "SELECT DISTINCT actor FROM audit_log WHERE action='case_opened' AND actor IS NOT NULL")]
        return {"items": rows, "actors": sorted(actors)}

    @r.get("/cases/{case_id}")
    def case_detail(case_id: int):
        """A case with everything the investigation screen needs in one call."""
        eng = engine()
        try:
            c = eng.get_case(case_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc))
        t = c["transaction"]
        c["customer_message"] = customer_message(t, t["decision"], t["reasons"])
        c["history"] = eng.user_history(t["user_id"], 25)
        st = eng.store._state(t["user_id"])
        cities = st.get("cities") or {}
        c["profile"] = {"home_city": max(cities, key=cities.get) if cities else None,
                        "typical_amount": round(st.get("ema") or 0, 2), "transactions": st.get("n", 0),
                        "devices": len(st.get("devices") or []), "cities": len(cities),
                        "categories": (st.get("categories") or [])[:8]}
        c["thresholds"] = eng.bundle.thresholds
        c["alerts"] = [dict(a) for a in eng.conn.execute(
            "SELECT audience, channel, body, created_at FROM alerts WHERE txn_id=? ORDER BY alert_id",
            (t["txn_id"],)).fetchall()]
        c["audit"] = [db.row_to_dict(a) for a in eng.conn.execute(
            "SELECT ts, actor, action, detail FROM audit_log WHERE json_extract(detail, '$.case_id')=? "
            "ORDER BY id", (case_id,)).fetchall()]
        return c

    @r.get("/audit")
    def audit(limit: int = Query(50, ge=1, le=500)):
        rows = engine().conn.execute("SELECT id, ts, actor, action, detail FROM audit_log "
                                     "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [db.row_to_dict(x) for x in rows]

    @r.get("/traffic")
    def get_traffic():
        return traffic().state()

    @r.post("/traffic")
    def set_traffic(body: TrafficIn):
        return traffic().set(body.running, body.rate)

    @r.get("/model")
    def model():
        eng = engine()
        labels = eng.conn.execute("SELECT COUNT(*) FROM transactions WHERE label IS NOT NULL").fetchone()[0]
        bench = ROOT / "benchmark" / "results.json"
        return {"current": eng.bundle.version, "thresholds": eng.bundle.thresholds,
                "features": eng.bundle.features, "versions": eng.registry.versions(), "labels": labels,
                "benchmark": json.loads(bench.read_text()) if bench.exists() else None}

    @r.post("/retrain")
    def retrain(events: int = Query(150_000, ge=20_000, le=500_000)):
        """Champion/challenger retraining with analyst labels. Takes tens of seconds."""
        from .retrain import retrain as run
        eng = engine()
        out = run(eng.settings, n_events=events)
        if out["decision"] == "PROMOTED":
            eng.reload_model()
        return out

    @r.get("/connect")
    def connect():
        s = engine().settings
        return {"mcp": {"mcpServers": {"sentinelai": {
            "command": "python", "args": ["-m", "sentinelai", "mcp"], "cwd": str(ROOT),
            "env": {"SENTINEL_DB_PATH": str(Path(s.db_path).resolve()),
                    "SENTINEL_MODEL_DIR": str(Path(s.model_dir).resolve())}}}},
            "tools": ["score_transaction", "get_case", "list_open_cases", "resolve_case", "get_user_history",
                      "lookup_policy", "check_drift", "live_metrics"]}

    return r
