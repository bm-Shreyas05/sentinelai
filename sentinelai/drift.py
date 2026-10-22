"""Population Stability Index drift monitoring against the reference saved with each model."""
import json

import numpy as np

from .features import FEATURES

# Time-of-day features follow a daily cycle, so a window covering only part of a day always looks
# "drifted" against a reference spanning weeks. They are compared only once the window covers a day.
DAILY_FEATURES = {"hour", "is_night"}
# history_log only grows as customers transact, so its full distribution tracks the age of the
# customer base rather than risk. What matters is a rise in cold-start payments (fewer than 3
# prior payments), which is monitored one-sided against the share seen in training.
COLD_START_LOG = float(np.log1p(3))


def psi(edges, ref_props, values, eps=1e-4):
    edges = np.asarray(edges, dtype=float)
    e = edges.copy(); e[0], e[-1] = -np.inf, np.inf
    cur = np.histogram(np.asarray(values, dtype=float), bins=e)[0]
    cur = cur / max(cur.sum(), 1)
    ref = np.asarray(ref_props, dtype=float)
    cur, ref = np.clip(cur, eps, None), np.clip(ref, eps, None)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


def status(v, warn=0.10, crit=0.25):
    return "critical" if v >= crit else ("warning" if v >= warn else "stable")


def drift_report(conn, bundle, window=2000, min_rows=200):
    rows = conn.execute("SELECT features, score, ts FROM transactions WHERE model_version=? "
                        "ORDER BY created_at DESC LIMIT ?", (bundle.version, window)).fetchall()
    if len(rows) < min_rows:
        return {"ready": False, "rows": len(rows), "needed": min_rows}
    names = getattr(bundle, "features", FEATURES)         # the serving model's own feature list
    X = np.array([[json.loads(r["features"]).get(f, 0.0) for f in names] for r in rows])
    scores = np.array([r["score"] for r in rows])
    ts = np.array([r["ts"] for r in rows])
    span_h = float(ts.max() - ts.min()) / 3600
    feats = []
    for i, name in enumerate(names):
        ref = bundle.reference["features"][name]
        if name == "history_log" and "cold_start_share" in bundle.reference:
            ref_share, share = bundle.reference["cold_start_share"], float((X[:, i] < COLD_START_LOG).mean())
            v = psi([0, COLD_START_LOG, 1], [ref_share, 1 - ref_share], X[:, i]) if share > ref_share else 0.0
            feats.append({"feature": name, "psi": round(v, 4), "status": status(v),
                          "cold_start_share": round(share, 4), "reference_cold_start_share": round(ref_share, 4)})
            continue
        v = psi(ref["edges"], ref["props"], X[:, i])
        st = "partial_day" if name in DAILY_FEATURES and span_h < 24 else status(v)
        feats.append({"feature": name, "psi": round(v, 4), "status": st})
    sref = bundle.reference["score"]
    score_psi = psi(sref["edges"], sref["props"], scores)
    n_crit = sum(f["status"] == "critical" for f in feats)
    trigger = n_crit >= 2 or score_psi > 0.15            # policy FRF-3.2
    return {"ready": True, "rows": len(rows), "window_hours": round(span_h, 1), "model_version": bundle.version,
            "features": sorted(feats, key=lambda f: -f["psi"]),
            "score_psi": round(score_psi, 4), "score_status": status(score_psi, 0.10, 0.15),
            "critical_features": n_crit, "retrain_recommended": bool(trigger)}
