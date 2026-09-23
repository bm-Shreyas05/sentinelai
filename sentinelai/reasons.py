"""Turn model contributions into plain-English reasons a bank analyst or customer can read.

Each reason compares what we observed with what is normal for this customer. Only features
that actually pushed the score up (positive TreeSHAP contribution) are reported as risk
reasons; features that pulled it down are reported as reassuring factors.
"""


def inr(x):
    n = int(round(x)); s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-₹" if n < 0 else "₹") + s


def _risk_reason(name, f, ctx, txn):
    typ = ctx["typical_amount"]
    if name in ("amount_log", "amount_ratio"):
        ratio = f["amount_ratio"]
        if ratio >= 2:
            return ("amount", "Unusually large amount", inr(txn["amount"]),
                    f"{inr(typ)} typical", f"{ratio:.1f}× this customer's usual spend.")
        if ratio <= 0.2:
            return ("amount", "Very small test-sized amount", inr(txn["amount"]), f"{inr(typ)} typical",
                    "Tiny payments are how stolen cards are often tested. On its own this is a weak signal.")
        return None
    if name in ("tx_count_5min", "tx_count_1h", "spend_1h_ratio", "secs_since_last_log"):
        if f["tx_count_5min"] >= 3 or f["tx_count_1h"] >= 6:
            return ("velocity", "Rapid burst of transactions", f"{f['tx_count_5min']} in 5 min, {f['tx_count_1h']} in 1 h",
                    "1–2 per hour", "Bursts of small payments are how stolen cards are tested before a big purchase.")
        if f["spend_1h_ratio"] >= 4:
            return ("spend_velocity", "High spending in the last hour", f"{inr(f['spend_1h_ratio'] * typ)} in 1 h",
                    f"{inr(typ)} per transaction", "Money is leaving the account much faster than usual.")
        return None   # timing contributed only weakly; not presented as a standalone reason
    if name == "is_new_device" and f["is_new_device"]:
        return ("device", "Unrecognised device", "Device never seen before",
                f"{ctx['known_devices']} known device(s)",
                "The payment came from a phone or terminal this customer has never used.")
    if name == "device_user_count" and f["device_user_count"] > 2:
        return ("shared_device", "Device shared across many accounts",
                f"{int(f['device_user_count'])} accounts on this device", "1 account",
                "Many accounts transacting from one device is a hallmark of mule rings.")
    if name == "travel_speed_kmh" and f["travel_speed_kmh"] > 300:
        return ("travel", "Impossible travel", f"{ctx['previous_city']} → {txn['city']} in {ctx['minutes_since_last']} min",
                "Physically possible travel",
                f"That journey would require {int(f['travel_speed_kmh'])} km/h; the card may be cloned.")
    if name in ("dist_from_home_km", "is_new_city") and (f["dist_from_home_km"] > 300 or f["is_new_city"]):
        return ("location", "Unfamiliar location", f"{txn['city']} ({int(f['dist_from_home_km'])} km from home)",
                f"{ctx['home_city']}", "The customer has not transacted here before.")
    if name in ("merchant_risk", "is_new_category") and txn.get("category") == "p2p_transfer" \
            and f["amount_ratio"] >= 1.5:
        return ("scam_pattern", "Large transfer to an individual", inr(txn["amount"]), f"{inr(typ)} typical",
                "Transfers to individuals are how most UPI scams are paid; the customer may have been tricked.")
    if name in ("merchant_risk", "is_new_category"):
        cat = txn.get("category", "?").replace("_", " ")
        usual = ", ".join(c.replace("_", " ") for c in ctx["known_categories"][:3]) or "no history"
        if f["is_new_category"]:
            return ("merchant", "Merchant type new for this customer", cat, usual,
                    "The customer has never paid this kind of merchant before.")
        if f["merchant_risk"] >= 1.5:
            return ("merchant", "High-risk merchant type", cat, "Everyday merchants",
                    "Fraudsters favour merchants where money is hard to recover.")
        return None
    if name in ("hour", "is_night") and f["is_night"]:
        return ("time", "Unusual time of day", f"{f['hour']:02d}:00 IST", "Daytime",
                "Takeovers often happen overnight while the customer is asleep.")
    if name == "history_log" and ctx["history_count"] < 3:
        return ("new_customer", "Very little account history", f"{ctx['history_count']} prior transactions",
                "Established pattern", "There isn't enough history yet to know what is normal.")
    return None   # channel and other weak contributors are not shown as standalone reasons


_REASSURING = {
    "is_new_device": "Known device", "is_new_city": "Usual city", "dist_from_home_km": "Close to home",
    "amount_ratio": "Normal amount", "amount_log": "Normal amount", "tx_count_5min": "Normal pace",
    "tx_count_1h": "Normal pace", "travel_speed_kmh": "Plausible travel", "merchant_risk": "Low-risk merchant",
    "device_user_count": "Device not shared", "history_log": "Established customer",
}


def explain(feats, contributions, ctx, txn, top_k=4, min_contrib=0.15):
    """Return {"risk": [...], "reassuring": [...], "strength": "none|single|multiple"}."""
    risk, seen = [], set()
    for name, c in sorted(contributions.items(), key=lambda kv: -kv[1]):
        if c < min_contrib or len(risk) >= top_k:
            break
        r = _risk_reason(name, feats, ctx, txn)
        if r and r[0] not in seen:
            seen.add(r[0])
            risk.append({"code": r[0], "title": r[1], "observed": r[2], "normal": r[3],
                         "detail": r[4], "weight": round(c, 3)})
    reassuring = []
    for name, c in sorted(contributions.items(), key=lambda kv: kv[1]):
        if c > -min_contrib or len(reassuring) >= 3:
            break
        label = _REASSURING.get(name)
        if label and label not in reassuring:
            reassuring.append(label)
    strong = [r for r in risk if r["weight"] >= 0.5]
    strength = "multiple" if len(strong) >= 2 else ("single" if risk else "none")
    return {"risk": risk, "reassuring": reassuring, "strength": strength}


def customer_message(txn, decision, reasons):
    """Short, jargon-free notification suitable for SMS or app push."""
    lead = {"BLOCK": "We have paused", "REVIEW": "We are checking"}.get(decision, "We noticed")
    # customers recognise concrete facts first: amount, device, place, speed — not merchant taxonomy
    order = ["amount", "scam_pattern", "device", "travel", "location", "velocity", "spend_velocity",
             "shared_device", "time", "merchant", "new_customer"]
    risk = sorted(reasons["risk"], key=lambda r: order.index(r["code"]) if r["code"] in order else 99)
    why = " and ".join(r["title"].lower() for r in risk[:2]) if risk else "unusual activity"
    return (f"SentinelAI: {lead} a payment of {inr(txn['amount'])} at {txn.get('merchant', 'a merchant')} "
            f"in {txn['city']} because of {why}. If this was you, reply YES. If not, reply NO "
            f"and your card/UPI will be frozen. Never share your OTP with anyone.")
