"""SentinelEngine: the single entry point used by the API, web console, MCP server and CLI."""
import json, threading, time, uuid

from . import db
from .agent import Investigator
from .alerts import Dispatcher
from .config import get_settings
from .drift import drift_report
from .features import FeatureStore
from .model import Registry
from .policy import PolicyIndex
from .reasons import explain

REQUIRED = ("user_id", "amount", "city", "device_id")


class SentinelEngine:
    def __init__(self, settings=None, bundle=None):
        self.settings = settings or get_settings()
        self.conn = db.connect(self.settings.db_path)
        self.registry = Registry(self.settings.model_dir)
        self.bundle = bundle or self.registry.load()
        self.store = FeatureStore(self.conn)
        self.policy = PolicyIndex(self.settings.policy_dir)
        self.alerts = Dispatcher(self.settings, self.conn)
        self.agent = Investigator(self)
        self._lock = threading.RLock()   # API, demo traffic and MCP may share one engine

    def reload_model(self):
        self.bundle = self.registry.load()
        return self.bundle.version

    # ── scoring ──────────────────────────────────────────────────────────────
    def score(self, txn: dict, actor="api"):
        missing = [k for k in REQUIRED if txn.get(k) in (None, "")]
        if missing:
            raise ValueError(f"missing fields: {missing}")
        if float(txn["amount"]) <= 0:
            raise ValueError("amount must be positive")
        txn = dict(txn)
        txn.setdefault("txn_id", f"T{uuid.uuid4().hex[:12].upper()}")
        txn.setdefault("ts", time.time())
        txn.setdefault("category", "online_shopping"); txn.setdefault("channel", "card")
        txn.setdefault("merchant", txn["category"])
        txn.setdefault("payee", txn["merchant"])
        sim_label = txn.pop("label", None); txn.pop("scenario", None)

        with self._lock:   # feature-store reads and writes for one user must not interleave
            if self.conn.execute("SELECT 1 FROM transactions WHERE txn_id=?", (txn["txn_id"],)).fetchone():
                raise ValueError(f"duplicate txn_id {txn['txn_id']}")
            t0 = time.perf_counter()
            feats, ctx = self.store.compute(txn)
            p, contrib, _ = self.bundle.predict(feats)
            model_decision = decision = self.bundle.decide(p)
            reasons = explain(feats, contrib, ctx, txn)
            if decision == "BLOCK" and float(txn["amount"]) < self.settings.min_block_amount:
                decision = "REVIEW"
                reasons["policy_override"] = (f"Model recommended BLOCK; downgraded to REVIEW because the amount is "
                                              f"below the ₹{self.settings.min_block_amount:,.0f} hard-block minimum.")
            self.conn.execute(
                "INSERT INTO transactions(txn_id,user_id,ts,amount,merchant,payee,category,city,device_id,channel,"
                "score,decision,model_version,features,contributions,reasons,sim_label,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (txn["txn_id"], txn["user_id"], txn["ts"], txn["amount"], txn["merchant"], txn["payee"], txn["category"],
                 txn["city"], txn["device_id"], txn["channel"], p, decision, self.bundle.version,
                 json.dumps(feats), json.dumps(contrib), json.dumps(reasons), sim_label, time.time()))
            self.store.update(txn)
            latency_ms = (time.perf_counter() - t0) * 1000

        result = {"txn_id": txn["txn_id"], "score": round(p, 5), "decision": decision,
                  "model_decision": model_decision,
                  "model_version": self.bundle.version, "reasons": reasons,
                  "latency_ms": round(latency_ms, 2), "case_id": None}
        if decision != "ALLOW":
            result["case_id"] = self._open_case(txn["txn_id"], actor)
        return result

    def _open_case(self, txn_id, actor):
        with self._lock:
            return self._open_case_locked(txn_id, actor)

    def _open_case_locked(self, txn_id, actor):
        now = time.time()
        cur = self.conn.execute("INSERT OR IGNORE INTO cases(txn_id, created_at, updated_at) VALUES (?,?,?)",
                                (txn_id, now, now))
        self.conn.commit()
        case_id = cur.lastrowid
        inv = self.agent.investigate(txn_id)
        self.conn.execute("UPDATE cases SET priority=?, summary=?, trace=?, policy_refs=?, updated_at=? "
                          "WHERE case_id=?",
                          (inv["priority"], json.dumps({"text": inv["summary"], "actions": inv["actions"]}),
                           json.dumps(inv["trace"]), json.dumps(inv["policy_refs"]), time.time(), case_id))
        self.conn.commit()
        db.audit(self.conn, actor, "case_opened", {"case_id": case_id, "txn_id": txn_id, "priority": inv["priority"]})
        return case_id

    # ── queries ──────────────────────────────────────────────────────────────
    def get_transaction(self, txn_id):
        t = db.row_to_dict(self.conn.execute("SELECT * FROM transactions WHERE txn_id=?", (txn_id,)).fetchone())
        if t is None:
            raise KeyError(f"unknown transaction {txn_id}")
        return t

    def user_history(self, user_id, limit=20):
        rows = self.conn.execute("SELECT txn_id, ts, amount, merchant, payee, category, city, device_id, score, "
                                 "decision, label FROM transactions WHERE user_id=? ORDER BY ts DESC LIMIT ?",
                                 (user_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def list_cases(self, status="open", limit=100):
        q = ("SELECT c.*, t.amount, t.user_id, t.city, t.merchant, t.score, t.decision FROM cases c "
             "JOIN transactions t USING(txn_id) ")
        args = []
        if status:
            q += "WHERE c.status=? "; args.append(status)
        q += ("ORDER BY CASE c.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, "
              "c.created_at DESC LIMIT ?")
        return [db.row_to_dict(r) for r in self.conn.execute(q, (*args, limit)).fetchall()]

    def get_case(self, case_id):
        c = db.row_to_dict(self.conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone())
        if c is None:
            raise KeyError(f"unknown case {case_id}")
        c["transaction"] = self.get_transaction(c["txn_id"])
        return c

    def recent_investigations(self, limit=20, since=None):
        """Latest agent investigations, newest first, with the trace, the transaction headline and who
        triggered it (api, demo, mcp, ...) from the audit log."""
        q = ("SELECT c.case_id, c.txn_id, c.priority, c.status, c.trace, c.created_at, t.amount, t.user_id, "
             "t.city, t.merchant, t.channel, t.decision, t.score, "
             "(SELECT a.actor FROM audit_log a WHERE a.action='case_opened' "
             " AND json_extract(a.detail, '$.case_id')=c.case_id LIMIT 1) AS actor "
             "FROM cases c JOIN transactions t USING(txn_id) WHERE c.trace IS NOT NULL ")
        args = []
        if since is not None:
            q += "AND c.created_at>=? "; args.append(since)
        rows = [db.row_to_dict(r) for r in self.conn.execute(q + "ORDER BY c.case_id DESC LIMIT ?",
                                                             (*args, limit)).fetchall()]
        for r in rows:
            r["agent_ms"] = round(sum(s["ms"] or 0 for s in r["trace"]), 2)
            r["notified"] = [s["tool"] for s in r["trace"] if s["tool"].startswith("notify_")]
        return rows

    def resolve_case(self, case_id, is_fraud: bool, analyst: str, notes: str = ""):
        with self._lock:
            return self._resolve_locked(case_id, is_fraud, analyst, notes)

    def _resolve_locked(self, case_id, is_fraud, analyst, notes):
        case = self.get_case(case_id)
        if case["status"] != "open":
            raise ValueError(f"case {case_id} already resolved as {case['status']}")
        status = "confirmed_fraud" if is_fraud else "false_positive"
        self.conn.execute("UPDATE cases SET status=?, assignee=?, resolution_notes=?, updated_at=? WHERE case_id=?",
                          (status, analyst, notes, time.time(), case_id))
        self.conn.execute("UPDATE transactions SET label=? WHERE txn_id=?", (int(is_fraud), case["txn_id"]))
        self.conn.commit()
        db.audit(self.conn, analyst, "case_resolved", {"case_id": case_id, "status": status, "notes": notes})
        if not is_fraud and case["transaction"]["decision"] == "BLOCK":   # policy CP-3.1
            self.alerts.send(case["txn_id"], "customer", "Payment released",
                             "SentinelAI: the payment we paused has been verified and released. Thank you.")
        return {"case_id": case_id, "status": status}

    def live_metrics(self, window_s=3600):
        since = time.time() - window_s
        r = self.conn.execute(
            "SELECT COUNT(*) n, SUM(decision='REVIEW') review, SUM(decision='BLOCK') block, AVG(score) avg_score, "
            "SUM(amount * (decision='BLOCK')) blocked_amount FROM transactions WHERE created_at>=?", (since,)).fetchone()
        c = self.conn.execute("SELECT status, COUNT(*) n FROM cases GROUP BY status").fetchall()
        lab = self.conn.execute(
            "SELECT SUM(label=1 AND decision!='ALLOW') tp, SUM(label=0 AND decision!='ALLOW') fp "
            "FROM transactions WHERE label IS NOT NULL").fetchone()
        n = r["n"] or 0
        return {"window_s": window_s, "transactions": n, "review": r["review"] or 0, "block": r["block"] or 0,
                "alert_rate": round(((r["review"] or 0) + (r["block"] or 0)) / max(n, 1), 4),
                "avg_score": round(r["avg_score"] or 0, 4), "blocked_amount": round(r["blocked_amount"] or 0, 2),
                "cases": {row["status"]: row["n"] for row in c},
                "analyst_precision": round((lab["tp"] or 0) / max((lab["tp"] or 0) + (lab["fp"] or 0), 1), 4)
                if (lab["tp"] or lab["fp"]) else None,
                "model_version": self.bundle.version}

    def drift(self, window=2000):
        return drift_report(self.conn, self.bundle, window)

    def ask_policy(self, question):
        return self.policy.answer(question)
