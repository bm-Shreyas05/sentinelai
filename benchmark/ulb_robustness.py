"""
How much should the ULB benchmark numbers be trusted? Robustness checks on the same real data.

The headline benchmark (ulb_benchmark.py) is one split, one seed and a test period with 52 frauds.
This script asks four questions of the same data and protocol (time order, thresholds frozen on
validation):

  1. Product hyperparameters: does sentinelai.model.PARAMS (what the product actually trains with)
     score like the tuned benchmark recipe?
  2. Uncertainty: bootstrap 95% intervals on test PR-AUC and on each tier's precision / recall.
  3. Seed stability: spread of test PR-AUC across LightGBM seeds.
  4. Time stability: rolling-origin folds (train on everything before, validate on the next 10%,
     test on the 10% after that), so the result does not hinge on one test window. The logistic
     baseline (trained on train + validation) is scored on each fold too.

Usage:
    python benchmark/ulb_robustness.py --csv data/creditcard.csv
"""
import argparse, json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import StandardScaler

from ulb_benchmark import at_threshold, pick_thresholds

BENCH_PARAMS = dict(objective="binary", learning_rate=0.03, num_leaves=31, min_child_samples=40,
                    feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                    scale_pos_weight=5.0, lambda_l2=1.0, verbose=-1, seed=42)
# Copied from sentinelai/model.py so the script runs without importing the package's DB/feature code
PRODUCT_PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_child_samples=30,
                      feature_fraction=0.9, bagging_fraction=0.8, bagging_freq=1,
                      scale_pos_weight=3.0, lambda_l2=1.0, verbose=-1, seed=42)
FEATS = [f"V{i}" for i in range(1, 29)] + ["amount_log", "hour"]


def load(csv):
    df = pd.read_csv(csv).sort_values("Time").reset_index(drop=True)
    df["hour"] = (df["Time"] // 3600) % 24
    df["amount_log"] = np.log1p(df["Amount"])
    return df[FEATS].values, df["Class"].values


def fit(params, Xtr, ytr, Xva, yva, rounds=2000, patience=100):
    return lgb.train(params, lgb.Dataset(Xtr, ytr), num_boost_round=rounds,
                     valid_sets=[lgb.Dataset(Xva, yva)],
                     callbacks=[lgb.early_stopping(patience, verbose=False)])


def evaluate(params, Xtr, ytr, Xva, yva, Xte, yte, **kw):
    b = fit(params, Xtr, ytr, Xva, yva, **kw)
    p_va, p_te = b.predict(Xva), b.predict(Xte)
    r, bl = pick_thresholds(yva, p_va)
    return {"pr_auc": round(average_precision_score(yte, p_te), 4),
            "review": at_threshold(yte, p_te, r), "block": at_threshold(yte, p_te, bl)}, p_te, (r, bl)


def logistic_pr_auc(Xtr, ytr, Xte, yte):
    sc = StandardScaler().fit(Xtr)
    lr = LogisticRegression(max_iter=2000, class_weight="balanced").fit(sc.transform(Xtr), ytr)
    return round(average_precision_score(yte, lr.predict_proba(sc.transform(Xte))[:, 1]), 4)


def bootstrap(y, p, thresholds, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    r, b = thresholds
    out = {k: [] for k in ("pr_auc", "review_precision", "review_recall",
                           "block_precision", "block_recall")}
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        yi, pi = y[i], p[i]
        if yi.sum() == 0:
            continue
        out["pr_auc"].append(average_precision_score(yi, pi))
        for name, t in (("review", r), ("block", b)):
            m = at_threshold(yi, pi, t)
            out[f"{name}_precision"].append(m["precision"]); out[f"{name}_recall"].append(m["recall"])
    return {k: [round(float(np.percentile(v, 2.5)), 3), round(float(np.percentile(v, 97.5)), 3)]
            for k, v in out.items()}


def main(csv, out_dir):
    X, y = load(csv)
    n = len(y); i1, i2 = int(n * 0.70), int(n * 0.85)
    split = (X[:i1], y[:i1], X[i1:i2], y[i1:i2], X[i2:], y[i2:])
    res = {"dataset": "ULB creditcard.csv", "split": "time-ordered 70/15/15",
           "test_frauds": int(y[i2:].sum())}

    # 1 + 2. both parameter sets on the headline split, with bootstrap intervals
    res["headline_split"] = {}
    for name, params, kw in (("benchmark_recipe", BENCH_PARAMS, {}),
                             ("product_params", PRODUCT_PARAMS, {"rounds": 1500, "patience": 80})):
        m, p_te, th = evaluate(params, *split, **kw)
        m["bootstrap_95ci"] = bootstrap(split[5], p_te, th)
        res["headline_split"][name] = m

    # 3. seed stability (benchmark recipe)
    aps = []
    for s in range(5):
        m, _, _ = evaluate({**BENCH_PARAMS, "seed": s}, *split)
        aps.append(m["pr_auc"])
    res["seed_pr_auc"] = {"values": aps, "mean": round(float(np.mean(aps)), 4),
                          "sd": round(float(np.std(aps)), 4)}

    # 4. rolling-origin folds (benchmark recipe)
    folds = []
    for start in (0.50, 0.60, 0.70, 0.80):
        a, b, c = int(n * start), int(n * (start + 0.10)), int(min(n, n * (start + 0.20)))
        m, _, _ = evaluate(BENCH_PARAMS, X[:a], y[:a], X[a:b], y[a:b], X[b:c], y[b:c])
        folds.append({"train_end": start, "test_window": [round(start + 0.10, 2), round(start + 0.20, 2)],
                      "test_rows": c - b, "test_frauds": int(y[b:c].sum()), **m,
                      "logistic_pr_auc": logistic_pr_auc(X[:b], y[:b], X[b:c], y[b:c])})
    res["rolling_folds"] = folds

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "ulb_robustness.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/creditcard.csv")
    ap.add_argument("--out", default="benchmark")
    a = ap.parse_args()
    main(a.csv, a.out)
