"""
Benchmark the SentinelAI training recipe on the public ULB credit-card fraud dataset.

Dataset: 284,807 European card transactions (Sept 2013), 492 frauds (0.172%).
Source: Kaggle "Credit Card Fraud Detection" (ULB Machine Learning Group), DbCL licence.

Protocol (chosen to avoid the usual leakage that inflates published numbers):
  * Time-ordered split: first 70% train, next 15% validation, last 15% test.
    Random splits leak future fraud patterns into training; production never sees the future.
  * Thresholds are picked on validation only, then frozen and applied to test.
  * Two operating points, matching the product's decision tiers:
      BLOCK  = highest-precision point with precision >= 0.90 on validation
      REVIEW = threshold that reaches recall >= 0.85 on validation

Usage:
    python benchmark/ulb_benchmark.py --csv data/creditcard.csv
"""
import argparse, json, time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, precision_recall_curve
from sklearn.preprocessing import StandardScaler


def pick_thresholds(y, p, block_precision=0.90, review_recall=0.85):
    prec, rec, thr = precision_recall_curve(y, p)
    prec, rec = prec[:-1], rec[:-1]
    ok = np.where(prec >= block_precision)[0]
    block = float(thr[ok[0]]) if len(ok) else float(thr[-1])
    ok = np.where(rec >= review_recall)[0]
    review = float(thr[ok[-1]]) if len(ok) else float(thr[0])
    return min(review, block), block


def at_threshold(y, p, t):
    pred = p >= t
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    return {"threshold": round(t, 4),
            "precision": round(tp / max(tp + fp, 1), 4),
            "recall": round(tp / max(tp + fn, 1), 4),
            "alerts_per_10k": round((tp + fp) / len(y) * 10_000, 1),
            "tp": tp, "fp": fp, "fn": fn}


def main(csv, out_dir):
    df = pd.read_csv(csv).sort_values("Time").reset_index(drop=True)
    df["hour"] = (df["Time"] // 3600) % 24
    df["amount_log"] = np.log1p(df["Amount"])
    feats = [f"V{i}" for i in range(1, 29)] + ["amount_log", "hour"]
    n = len(df); i1, i2 = int(n * 0.70), int(n * 0.85)
    tr, va, te = df.iloc[:i1], df.iloc[i1:i2], df.iloc[i2:]
    Xtr, ytr = tr[feats].values, tr["Class"].values
    Xva, yva = va[feats].values, va["Class"].values
    Xte, yte = te[feats].values, te["Class"].values

    results = {"dataset": "ULB creditcard.csv", "rows": n, "frauds": int(df["Class"].sum()),
               "split": "time-ordered 70/15/15",
               "test_rows": len(te), "test_frauds": int(yte.sum()), "models": {}}

    # Baseline: logistic regression
    sc = StandardScaler().fit(Xtr)
    lr = LogisticRegression(max_iter=2000, class_weight="balanced").fit(sc.transform(Xtr), ytr)
    p_va, p_te = lr.predict_proba(sc.transform(Xva))[:, 1], lr.predict_proba(sc.transform(Xte))[:, 1]
    r, b = pick_thresholds(yva, p_va)
    results["models"]["logistic_regression"] = {
        "pr_auc": round(average_precision_score(yte, p_te), 4),
        "roc_auc": round(roc_auc_score(yte, p_te), 4),
        "review": at_threshold(yte, p_te, r), "block": at_threshold(yte, p_te, b)}

    # SentinelAI recipe: LightGBM, mild positive weighting, early stopping on validation
    t0 = time.time()
    params = dict(objective="binary", learning_rate=0.03, num_leaves=31, min_child_samples=40,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                  scale_pos_weight=5.0, lambda_l2=1.0, verbose=-1, seed=42)
    booster = lgb.train(params, lgb.Dataset(Xtr, ytr), num_boost_round=2000,
                        valid_sets=[lgb.Dataset(Xva, yva)],
                        callbacks=[lgb.early_stopping(100, verbose=False)])
    p_va, p_te = booster.predict(Xva), booster.predict(Xte)
    r, b = pick_thresholds(yva, p_va)
    results["models"]["sentinelai_lightgbm"] = {
        "pr_auc": round(average_precision_score(yte, p_te), 4),
        "roc_auc": round(roc_auc_score(yte, p_te), 4),
        "best_iteration": booster.best_iteration,
        "train_seconds": round(time.time() - t0, 1),
        "review": at_threshold(yte, p_te, r), "block": at_threshold(yte, p_te, b)}

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/creditcard.csv")
    ap.add_argument("--out", default="benchmark")
    a = ap.parse_args()
    main(a.csv, a.out)
