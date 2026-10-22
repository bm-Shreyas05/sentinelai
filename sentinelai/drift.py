"""Population Stability Index drift monitoring against the reference saved with each model."""
import json

import numpy as np


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
    rows = conn.execute("SELECT features, score FROM transactions WHERE model_version=? "
                        "ORDER BY created_at DESC LIMIT ?", (bundle.version, window)).fetchall()
    if len(rows) < min_rows:
        return {"ready": False, "rows": len(rows), "needed": min_rows}
    names = bundle.features                               # the serving model's own feature list
    X = np.array([[json.loads(r["features"]).get(f, 0.0) for f in names] for r in rows])
    scores = np.array([r["score"] for r in rows])
    feats = []
    for i, name in enumerate(names):
        ref = bundle.reference["features"][name]
        v = psi(ref["edges"], ref["props"], X[:, i])
        feats.append({"feature": name, "psi": round(v, 4), "status": status(v)})
    sref = bundle.reference["score"]
    score_psi = psi(sref["edges"], sref["props"], scores)
    n_crit = sum(f["status"] == "critical" for f in feats)
    trigger = n_crit >= 2 or score_psi > 0.15            # policy FRF-3.2
    return {"ready": True, "rows": len(rows), "model_version": bundle.version,
            "features": sorted(feats, key=lambda f: -f["psi"]),
            "score_psi": round(score_psi, 4), "score_status": status(score_psi, 0.10, 0.15),
            "critical_features": n_crit, "retrain_recommended": bool(trigger)}
