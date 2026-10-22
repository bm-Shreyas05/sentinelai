"""Online feature store.

One code path computes features for both training (replaying historical events) and live
scoring, which removes training/serving skew. Per-user state is kept in memory and, when a
database connection is supplied, written through to SQLite so it survives restarts.
"""
import json, math
from collections import deque

from .geo import haversine_km

FEATURES = [
    "amount_log",            # log(1 + amount in INR)
    "amount_ratio",          # amount / user's typical spend (EMA); 1.0 = normal
    "history_log",           # log(1 + number of prior transactions) — cold-start awareness
    "tx_count_5min",         # transactions by this user in the previous 5 minutes
    "tx_count_1h",           # transactions by this user in the previous hour
    "spend_1h_ratio",        # INR spent in the previous hour / typical spend
    "secs_since_last_log",   # log(1 + seconds since previous transaction)
    "is_new_device",         # device never seen for this user
    "device_user_count",     # distinct users seen on this device (mule / shared-device signal)
    "is_new_city",           # city never seen for this user
    "dist_from_home_km",     # distance from the user's most frequent city
    "travel_speed_kmh",      # distance from previous txn city / elapsed time (impossible travel)
    "hour",                  # hour of day (IST)
    "is_night",              # 00:00-05:00 IST
    "merchant_risk",         # category-level risk prior
    "is_new_category",       # merchant category never used by this user
    "channel_code",          # 0 card, 1 UPI, 2 netbanking, 3 wallet
    "is_new_payee",          # transfer to an individual this user has never paid (0 for merchant payments)
    "payee_fan_in_log",      # log(1 + distinct other accounts that have paid this individual payee)
]

MERCHANT_RISK = {
    "grocery": 0.2, "restaurant": 0.3, "fuel": 0.4, "medical": 0.2, "utilities": 0.2,
    "travel": 0.9, "online_shopping": 1.2, "electronics": 1.8, "jewellery": 2.0,
    "atm": 1.0, "p2p_transfer": 1.5, "gaming": 2.4, "crypto": 3.0,
}
CHANNELS = {"card": 0, "upi": 1, "netbanking": 2, "wallet": 3}
DEFAULT_EMA = 2500.0          # cold-start typical spend (INR)
EMA_ALPHA = 0.1
IST_OFFSET = 5.5 * 3600


def _new_state():
    return {"ema": DEFAULT_EMA, "n": 0, "recent": [], "devices": [], "cities": {},
            "categories": [], "payees": [], "last_ts": None, "last_city": None}


def _personal_payee(txn):
    """Payee features apply to transfers to individuals; merchants are covered by category features."""
    return txn.get("payee") if txn.get("category") == "p2p_transfer" else None


class FeatureStore:
    def __init__(self, conn=None):
        self.conn = conn
        self._users = {}
        self._device_users = {}
        self._payee_senders = {}

    # ── state access ──────────────────────────────────────────────────────────
    def _state(self, user_id):
        if user_id in self._users:
            return self._users[user_id]
        st = None
        if self.conn is not None:
            row = self.conn.execute("SELECT state FROM user_state WHERE user_id=?", (user_id,)).fetchone()
            if row:
                st = json.loads(row["state"])
        st = st or _new_state()
        self._users[user_id] = st
        return st

    def _device_count(self, device_id):
        if device_id not in self._device_users:
            users = set()
            if self.conn is not None:
                users = {r["user_id"] for r in self.conn.execute(
                    "SELECT user_id FROM device_users WHERE device_id=?", (device_id,))}
            self._device_users[device_id] = users
        return self._device_users[device_id]

    def _payee_senders_of(self, payee):
        if payee not in self._payee_senders:
            users = set()
            if self.conn is not None:
                users = {r["user_id"] for r in self.conn.execute(
                    "SELECT user_id FROM payee_users WHERE payee=?", (payee,))}
            self._payee_senders[payee] = users
        return self._payee_senders[payee]

    # ── feature computation ───────────────────────────────────────────────────
    def compute(self, txn: dict):
        """Return (feature_dict, context_dict). Does not mutate state."""
        st = self._state(txn["user_id"])
        ts, amount = float(txn["ts"]), float(txn["amount"])
        recent = [(t, a) for t, a in st["recent"] if ts - t <= 3600]
        home = max(st["cities"], key=st["cities"].get) if st["cities"] else txn["city"]
        dist_home = haversine_km(home, txn["city"])
        dt = (ts - st["last_ts"]) if st["last_ts"] is not None else None
        if st["last_city"] and dt is not None:
            hops = haversine_km(st["last_city"], txn["city"])
            speed = hops / max(dt / 3600.0, 1 / 60) if hops > 0 else 0.0
        else:
            speed = 0.0
        device_users = self._device_count(txn["device_id"])
        n_dev_users = len(device_users | {txn["user_id"]})
        hour = int(((ts + IST_OFFSET) % 86400) // 3600)
        category = txn.get("category", "online_shopping")
        payee = _personal_payee(txn)
        known_payees = st.setdefault("payees", [])
        payee_others = len(self._payee_senders_of(payee) - {txn["user_id"]}) if payee else 0

        f = {
            "amount_log": math.log1p(amount),
            "amount_ratio": amount / max(st["ema"], 1.0),
            "history_log": math.log1p(st["n"]),
            "tx_count_5min": sum(1 for t, _ in recent if ts - t <= 300),
            "tx_count_1h": len(recent),
            "spend_1h_ratio": sum(a for _, a in recent) / max(st["ema"], 1.0),
            "secs_since_last_log": math.log1p(dt) if dt is not None else math.log1p(86400 * 30),
            "is_new_device": 0 if txn["device_id"] in st["devices"] else 1,
            "device_user_count": n_dev_users,
            "is_new_city": 0 if txn["city"] in st["cities"] else 1,
            "dist_from_home_km": dist_home,
            "travel_speed_kmh": min(speed, 5000.0),
            "hour": hour,
            "is_night": 1 if hour < 5 else 0,
            "merchant_risk": MERCHANT_RISK.get(category, 1.0),
            "is_new_category": 0 if category in st["categories"] else 1,
            "channel_code": CHANNELS.get(txn.get("channel", "card"), 0),
            "is_new_payee": 1 if payee and payee not in known_payees else 0,
            "payee_fan_in_log": math.log1p(payee_others),
        }
        # Context used by the explanation layer ("this transaction vs normal for this user")
        ctx = {
            "typical_amount": round(st["ema"], 2), "history_count": st["n"],
            "home_city": home, "known_devices": len(st["devices"]),
            "known_cities": sorted(st["cities"], key=st["cities"].get, reverse=True)[:3],
            "previous_city": st["last_city"],
            "minutes_since_last": round(dt / 60, 1) if dt is not None else None,
            "known_categories": st["categories"][:5],
            "known_payees": len(known_payees), "payee_other_senders": payee_others,
        }
        return f, ctx

    # ── state update (call after scoring) ─────────────────────────────────────
    def update(self, txn: dict):
        st = self._state(txn["user_id"])
        ts, amount = float(txn["ts"]), float(txn["amount"])
        st["ema"] = amount if st["n"] == 0 else (1 - EMA_ALPHA) * st["ema"] + EMA_ALPHA * amount
        st["n"] += 1
        st["recent"] = [(t, a) for t, a in st["recent"] if ts - t <= 3600] + [(ts, amount)]
        if txn["device_id"] not in st["devices"]:
            st["devices"] = (st["devices"] + [txn["device_id"]])[-10:]
        st["cities"][txn["city"]] = st["cities"].get(txn["city"], 0) + 1
        cat = txn.get("category", "online_shopping")
        if cat not in st["categories"]:
            st["categories"] = (st["categories"] + [cat])[-20:]
        payee = _personal_payee(txn)
        if payee and payee not in st.setdefault("payees", []):
            st["payees"] = (st["payees"] + [payee])[-50:]
        st["last_ts"], st["last_city"] = ts, txn["city"]
        self._device_count(txn["device_id"]).add(txn["user_id"])
        if payee:
            self._payee_senders_of(payee).add(txn["user_id"])
        if self.conn is not None:
            self.conn.execute("INSERT OR REPLACE INTO user_state(user_id, state) VALUES (?,?)",
                              (txn["user_id"], json.dumps(st)))
            self.conn.execute("INSERT OR IGNORE INTO device_users(device_id, user_id) VALUES (?,?)",
                              (txn["device_id"], txn["user_id"]))
            if payee:
                self.conn.execute("INSERT OR IGNORE INTO payee_users(payee, user_id) VALUES (?,?)",
                                  (payee, txn["user_id"]))
            self.conn.commit()


def warm_up(store: FeatureStore, events):
    """Build customer histories from past events without scoring them (demo / backfill).

    State is updated in memory and written to SQLite in one transaction at the end, so replaying
    tens of thousands of events takes seconds. Without this, simulated demo traffic is all
    cold-start and the drift monitor rightly reports it as unlike the training data.
    """
    conn, n = store.conn, 0
    try:
        for e in events:
            store._state(e["user_id"]); store._device_count(e["device_id"])   # load persisted state
            store.conn = None
            store.update(e)                                                     # in memory only
            store.conn = conn; n += 1
    finally:
        store.conn = conn
    if conn is not None:
        with conn:
            conn.executemany("INSERT OR REPLACE INTO user_state(user_id, state) VALUES (?,?)",
                             [(u, json.dumps(st)) for u, st in store._users.items()])
            conn.executemany("INSERT OR IGNORE INTO device_users(device_id, user_id) VALUES (?,?)",
                             [(d, u) for d, us in store._device_users.items() for u in us])
    return n


def to_vector(f: dict):
    return [float(f[k]) for k in FEATURES]
