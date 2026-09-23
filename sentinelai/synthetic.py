"""Event-level transaction simulator for Indian payments.

Generates raw events (user, amount, merchant category, city, device, channel, timestamp) with
ground-truth labels. Used for demos, tests and bootstrapping a model before a bank's own
labelled history is available. It deliberately includes legitimate edge cases so the model
learns context rather than single-feature rules:
  - legitimate new devices with ordinary amounts (phone upgrades)
  - legitimate travel to other cities at plausible speeds
  - occasional large legitimate purchases
Fraud scenarios: UPI social-engineering scams (hardest: victim's own device and city),
account takeover (incl. malware on the victim's phone), fast and slow card testing,
cloned cards (impossible travel) and mule rings on shared devices.
"""
import numpy as np

from .geo import CITIES, haversine_km

CATEGORIES = ["grocery", "restaurant", "fuel", "medical", "utilities", "travel",
              "online_shopping", "electronics", "jewellery", "atm", "p2p_transfer", "gaming", "crypto"]
LEGIT_CAT_P = np.array([22, 16, 9, 5, 8, 3, 18, 4, 1, 7, 6, 0.7, 0.3]); LEGIT_CAT_P /= LEGIT_CAT_P.sum()
CITY_NAMES = list(CITIES)
CHANNELS = ["card", "upi", "netbanking", "wallet"]


class Simulator:
    def __init__(self, n_users=2000, seed=7, fraud_rate=0.005, start_ts=1_767_225_600.0):
        self.rng = np.random.default_rng(seed)
        self.fraud_rate = fraud_rate
        self.t = start_ts
        self._n = 0
        self.users = []
        for i in range(n_users):
            home = CITY_NAMES[self.rng.integers(len(CITY_NAMES))]
            self.users.append({
                "user_id": f"U{i:05d}", "home": home, "city": home,
                "devices": [f"D{i:05d}a"] + ([f"D{i:05d}b"] if self.rng.random() < 0.3 else []),
                "typical": float(np.exp(self.rng.normal(7.3, 0.7))),     # median ~₹1,500
                "channel_p": self.rng.dirichlet([3, 5, 1, 1]),
            })
        self.mule_devices = [f"MULE{j:03d}" for j in range(12)]

    def _txn(self, u, amount, category, city, device, channel, ts, label, scenario):
        self._n += 1
        return {"txn_id": f"T{self._n:09d}", "user_id": u["user_id"], "ts": float(ts),
                "amount": float(max(1.0, round(amount))), "merchant": f"{category}-{city[:3].upper()}",
                "category": category, "city": city, "device_id": device, "channel": channel,
                "label": int(label), "scenario": scenario}

    def _legit(self, u, ts):
        r = self.rng
        cat = CATEGORIES[r.choice(len(CATEGORIES), p=LEGIT_CAT_P)]
        amount = u["typical"] * float(np.exp(r.normal(0, 0.7)))
        device = u["devices"][r.integers(len(u["devices"]))]
        channel = CHANNELS[r.choice(4, p=u["channel_p"])]
        if u["city"] != u["home"] and r.random() < 0.3:     # returning from a trip
            u["city"] = u["home"]
        elif r.random() < 0.006:                            # legitimate trip
            u["city"] = CITY_NAMES[r.integers(len(CITY_NAMES))]
        if r.random() < 0.012:                              # legitimate new device, any amount
            device = f"{u['user_id']}-new{r.integers(1e6)}"; u["devices"].append(device)
        roll = r.random()
        if roll < 0.02:                                     # big legitimate purchase
            amount *= r.uniform(3, 12); cat = str(r.choice(["electronics", "travel", "jewellery"]))
        elif roll < 0.035:                                  # rent / family transfer over UPI
            amount = u["typical"] * r.uniform(4, 15); cat, channel = "p2p_transfer", "upi"
        elif roll < 0.045:                                  # legit gaming / crypto user
            cat = str(r.choice(["gaming", "crypto"]))
        if r.random() < 0.02:                               # bill-splitting burst: several quick UPI payments
            return [self._txn(u, amount * r.uniform(0.2, 0.6), "restaurant", u["city"], device, "upi",
                              ts + k * r.uniform(15, 90), 0, "legit") for k in range(r.integers(3, 6))]
        return [self._txn(u, amount, cat, u["city"], device, channel, ts, 0, "legit")]

    def _fraud(self, u, ts):
        r = self.rng
        kind = str(r.choice(["upi_scam", "takeover", "card_testing", "cloned_card", "mule"],
                            p=[0.30, 0.25, 0.15, 0.18, 0.12]))
        far = [c for c in CITY_NAMES if haversine_km(c, u["home"]) > 800] or CITY_NAMES
        if kind == "upi_scam":
            # victim pays the scammer from their own phone, at home: only the payment itself is odd
            amount = u["typical"] * r.uniform(1.5, 12)
            out = [self._txn(u, amount, "p2p_transfer", u["city"], u["devices"][0], "upi", ts, 1, kind)]
            if r.random() < 0.4:                            # scammer asks for a "second fee"
                out.append(self._txn(u, amount * r.uniform(0.3, 1.0), "p2p_transfer", u["city"],
                                     u["devices"][0], "upi", ts + r.uniform(300, 3000), 1, kind))
            return out
        if kind == "takeover":
            own_device = r.random() < 0.35                  # malware / OTP theft on the victim's own phone
            dev = u["devices"][0] if own_device else f"X{r.integers(1e7)}"
            city = u["city"] if (own_device or r.random() < 0.4) else far[r.integers(len(far))]
            if r.random() < 0.4:                            # overnight, always in the future
                hour_ist = ((ts + 19800) % 86400) / 3600
                ts = ts + ((24 - hour_ist) % 24 + r.uniform(0, 4)) * 3600
            return [self._txn(u, u["typical"] * r.uniform(2, 25),
                              str(r.choice(["electronics", "jewellery", "crypto", "p2p_transfer", "online_shopping"])),
                              city, dev, str(r.choice(["upi", "netbanking", "card"])), ts, 1, kind)]
        if kind == "card_testing":
            dev = f"X{r.integers(1e7)}" if r.random() < 0.7 else u["devices"][0]
            gap = r.uniform(10, 40) if r.random() < 0.6 else r.uniform(600, 3000)   # fast or slow testing
            out = [self._txn(u, r.uniform(1, 150), str(r.choice(["online_shopping", "gaming"])),
                             u["city"], dev, "card", ts + k * gap, 1, kind) for k in range(r.integers(3, 9))]
            out.append(self._txn(u, u["typical"] * r.uniform(2, 10), "electronics", u["city"], dev,
                                 "card", out[-1]["ts"] + r.uniform(30, 600), 1, kind))
            return out
        if kind == "cloned_card":
            home_t = self._txn(u, u["typical"] * r.uniform(0.5, 1.5), "grocery", u["city"],
                               u["devices"][0], "card", ts, 0, "legit")
            city = far[r.integers(len(far))] if r.random() < 0.6 else CITY_NAMES[r.integers(len(CITY_NAMES))]
            clone = self._txn(u, u["typical"] * r.uniform(1, 8), str(r.choice(["atm", "electronics", "jewellery"])),
                              city, f"POS{r.integers(1e6)}", "card", ts + r.uniform(600, 6 * 3600), 1, kind)
            return [home_t, clone]
        dev = self.mule_devices[r.integers(len(self.mule_devices))]   # mule ring: shared devices
        return [self._txn(u, r.uniform(3000, 60000), "p2p_transfer", u["city"], dev, "upi", ts, 1, kind)]

    def stream(self, n_events, mean_gap_s=20.0):
        """Yield events in time order until at least n_events have been produced."""
        produced, pending = 0, []
        while produced < n_events:
            self.t += float(self.rng.exponential(mean_gap_s))
            u = self.users[self.rng.integers(len(self.users))]
            batch = self._fraud(u, self.t) if self.rng.random() < self.fraud_rate else self._legit(u, self.t)
            pending.extend(batch)
            pending.sort(key=lambda e: e["ts"])
            # an event may only be released once no future batch can precede it
            while pending and pending[0]["ts"] <= self.t:
                produced += 1
                yield pending.pop(0)
        for e in sorted(pending, key=lambda e: e["ts"]):
            yield e
