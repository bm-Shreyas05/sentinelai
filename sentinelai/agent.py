"""Investigation agent.

Runs automatically for every REVIEW/BLOCK decision. It calls a sequence of tools, records a
trace of every call (tool, input, output, latency) and writes the result onto the case:
priority, recommended actions with policy citations, customer notification and analyst summary.

The chain is deterministic so results are reproducible and auditable. If ANTHROPIC_API_KEY is
set, an LLM additionally writes a short narrative from the same evidence; it never changes the
decision, priority or actions.
"""
import json, logging, time

import httpx

from .reasons import customer_message, inr

log = logging.getLogger("sentinelai.agent")

ACTIONS = {
    "velocity": "Block and reissue the card; review the burst of small payments (card testing).",
    "travel": "Treat card as cloned: block it and check the merchant terminals involved.",
    "shared_device": "Escalate to AML: device shared across accounts suggests a mule ring; assess STR.",
    "device": "Verify the new device with the customer through a registered channel.",
    "amount": "Call the customer to confirm the payment before release.",
    "location": "Confirm whether the customer is travelling.",
    "merchant": "Check the merchant and apply step-up authentication.",
    "time": "Contact the customer; overnight activity is common in takeovers.",
    "new_customer": "Apply new-account limits and verify identity documents.",
    "spend_velocity": "Hold further outgoing payments until the customer confirms; spending is far above normal.",
    "scam_pattern": "Call the customer before release and ask whether anyone told them to make this payment.",
}


class Investigator:
    def __init__(self, engine):
        self.e = engine

    def _call(self, trace, tool, fn, arg):
        t0 = time.perf_counter()
        out = fn(arg)
        trace.append({"step": len(trace) + 1, "tool": tool, "input": arg,
                      "output": out if isinstance(out, (str, int, float)) or out is None else _summ(out),
                      "ms": round((time.perf_counter() - t0) * 1000, 2)})
        return out

    def investigate(self, txn_id):
        trace = []
        txn = self._call(trace, "get_transaction", self.e.get_transaction, txn_id)
        reasons = txn["reasons"]
        codes = [r["code"] for r in reasons.get("risk", [])]
        history = self._call(trace, "get_user_history", lambda u: self.e.user_history(u, 20), txn["user_id"])
        prior_fraud = sum(1 for h in history if h.get("label") == 1)
        prior_alerts = sum(1 for h in history if h["decision"] in ("REVIEW", "BLOCK") and h["txn_id"] != txn_id)
        refs = self._call(trace, "lookup_policy",
                          lambda a: self.e.policy.for_reasons(a["codes"], a["decision"]),
                          {"codes": codes, "decision": txn["decision"]})

        if txn["decision"] == "BLOCK" and (reasons.get("strength") == "multiple" or prior_fraud):
            priority = "critical"
        elif txn["decision"] == "BLOCK" or prior_alerts >= 2:
            priority = "high"
        else:
            priority = "normal"
        trace.append({"step": len(trace) + 1, "tool": "assess_priority",
                      "input": {"decision": txn["decision"], "signal_strength": reasons.get("strength"),
                                "prior_confirmed_fraud": prior_fraud, "prior_alerts": prior_alerts},
                      "output": priority, "ms": 0.0})

        actions = [ACTIONS[c] for c in codes if c in ACTIONS]
        if reasons.get("strength") == "single" and txn["decision"] == "REVIEW":
            actions.insert(0, "Only one weak signal: likely false positive, verify before any customer impact.")
        actions = list(dict.fromkeys(actions))

        summary = self._summary(txn, reasons, priority, prior_fraud, prior_alerts, refs)
        if txn["decision"] == "BLOCK":
            msg = customer_message(txn, txn["decision"], reasons)
            self._call(trace, "notify_customer",
                       lambda m: self.e.alerts.send(txn_id, "customer", "Payment paused", m), msg)
        if priority in ("high", "critical"):
            self._call(trace, "notify_analysts",
                       lambda m: self.e.alerts.send(txn_id, "analyst", f"[{priority.upper()}] {txn_id}", m), summary)
        narrative = self._narrative(txn, reasons, refs, summary)
        if narrative:
            trace.append({"step": len(trace) + 1, "tool": "llm_narrative", "input": "evidence bundle",
                          "output": narrative[:120] + "…", "ms": None})
        return {"priority": priority, "actions": actions, "summary": narrative or summary,
                "policy_refs": [{"id": r["id"], "text": r["text"], "document": r["document"]} for r in refs],
                "trace": trace}

    @staticmethod
    def _summary(txn, reasons, priority, prior_fraud, prior_alerts, refs):
        risk = "; ".join(f"{r['title']} ({r['observed']} vs {r['normal']})" for r in reasons.get("risk", []))
        ok = ", ".join(reasons.get("reassuring", [])) or "none"
        return (f"{txn['decision']} ({priority} priority): {inr(txn['amount'])} at {txn['merchant']} in "
                f"{txn['city']} by {txn['user_id']}. Risk signals: {risk or 'combination of weak signals'}. "
                f"Reassuring: {ok}. Prior alerts: {prior_alerts}, prior confirmed fraud: {prior_fraud}. "
                f"Policy: {', '.join(r['id'] for r in refs) or 'n/a'}."
                + (f" Note: {reasons['policy_override']}" if reasons.get("policy_override") else ""))

    def _narrative(self, txn, reasons, refs, summary):
        key = self.e.settings.anthropic_api_key
        if not key:
            return None
        prompt = ("You are a fraud analyst assistant at an Indian bank. Using ONLY the evidence below, write "
                  "3 short sentences for the case file: what happened, why it is risky or not, and the next "
                  "step with the policy clause IDs. Do not invent facts.\n\n"
                  + json.dumps({"summary": summary, "reasons": reasons,
                                "policy": [{"id": r["id"], "text": r["text"]} for r in refs]}))
        try:
            r = httpx.post("https://api.anthropic.com/v1/messages", timeout=20,
                           headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                           json={"model": self.e.settings.llm_model, "max_tokens": 300,
                                 "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json()["content"])
        except Exception as exc:
            log.error("LLM narrative failed, using deterministic summary: %s", exc)
            return None


def _summ(obj):
    if isinstance(obj, list):
        return f"{len(obj)} item(s)" + (f": {', '.join(str(o.get('id', o.get('txn_id', ''))) for o in obj[:5])}"
                                        if obj and isinstance(obj[0], dict) else "")
    if isinstance(obj, dict):
        return {k: obj[k] for k in list(obj)[:6] if not isinstance(obj[k], (dict, list))}
    return str(obj)
