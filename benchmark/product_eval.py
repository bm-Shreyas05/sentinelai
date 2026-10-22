"""Product model evaluation on simulated Indian payment events, broken down by fraud scenario.

Rebuilds the exact training run used by `python -m sentinelai train` (250,000 events, 3,000 users,
seed 11), then reports overall and per-scenario catch rates on the untouched time-ordered test
slice at the frozen review and block thresholds. Writes benchmark/product_results.json.

  python benchmark/product_eval.py
"""
import json, sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sentinelai.features import FeatureStore, to_vector   # noqa: E402
from sentinelai.model import train                        # noqa: E402
from sentinelai.synthetic import Simulator                # noqa: E402


def main(n_events=250_000, seed=11, n_users=3000):
    store, X, y, scen = FeatureStore(), [], [], []
    for e in Simulator(n_users=n_users, seed=seed).stream(n_events):
        f, _ = store.compute(e)
        X.append(to_vector(f)); y.append(int(e["label"])); scen.append(e["scenario"])
        store.update(e)
    X, y, scen = np.array(X, dtype=float), np.array(y, dtype=int), np.array(scen)
    bundle, (Xte, yte) = train(X, y)
    s_te = scen[len(y) - len(yte):]
    p = bundle.predict_batch(Xte)
    th = bundle.thresholds
    per = {}
    for s in sorted(set(s_te[yte == 1])):
        m = s_te == s
        per[s] = {"test_frauds": int(m.sum()),
                  "caught_review": round(float((p[m] >= th["review"]).mean()), 3),
                  "caught_block": round(float((p[m] >= th["block"]).mean()), 3)}
    legit = s_te == "legit"
    out = {"events": n_events, "users": n_users, "seed": seed, "thresholds": th,
           "metrics": bundle.metrics, "per_scenario": per,
           "legit_flag_rate_review": round(float((p[legit] >= th["review"]).mean()), 5),
           "test_scenario_counts": dict(Counter(s_te.tolist()))}
    path = Path(__file__).resolve().parent / "product_results.json"
    path.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
