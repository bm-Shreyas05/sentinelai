"""Model training, versioned registry and inference with exact TreeSHAP contributions."""
import json, time
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from .features import FEATURES, FeatureStore, to_vector

PARAMS = dict(objective="binary", learning_rate=0.05, num_leaves=31, min_child_samples=30,
              feature_fraction=0.9, bagging_fraction=0.8, bagging_freq=1,
              scale_pos_weight=3.0, lambda_l2=1.0, verbose=-1, seed=42)


@dataclass
class ModelBundle:
    booster: lgb.Booster
    version: str
    thresholds: dict            # {"review": float, "block": float}
    metrics: dict
    reference: dict             # per-feature quantile edges + proportions, and score distribution
    features: list = field(default_factory=lambda: list(FEATURES))
    trained_at: float = field(default_factory=time.time)
    notes: str = ""

    def predict(self, feats: dict):
        x = np.array([[float(feats.get(k, 0.0)) for k in self.features]])   # bundles keep their own feature list
        p = float(self.booster.predict(x)[0])
        contrib = self.booster.predict(x, pred_contrib=True)[0]   # exact TreeSHAP, log-odds space
        contributions = {f: float(c) for f, c in zip(self.features, contrib[:-1])}
        return p, contributions, float(contrib[-1])

    def predict_batch(self, X):
        return self.booster.predict(np.asarray(X))

    def decide(self, p):
        if p >= self.thresholds["block"]:
            return "BLOCK"
        if p >= self.thresholds["review"]:
            return "REVIEW"
        return "ALLOW"


# ── dataset construction ─────────────────────────────────────────────────────
def build_matrix(events, store=None):
    """Replay events through a fresh feature store (same code as serving) → X, y."""
    store = store or FeatureStore()
    X, y = [], []
    for e in events:
        f, _ = store.compute(e)
        X.append(to_vector(f)); y.append(int(e["label"]))
        store.update(e)
    return np.array(X, dtype=float), np.array(y, dtype=int)


def pick_thresholds(y, p, block_precision=0.90, review_recall=0.85):
    prec, rec, thr = precision_recall_curve(y, p)
    prec, rec = prec[:-1], rec[:-1]
    ok = np.where(prec >= block_precision)[0]
    block = float(thr[ok[0]]) if len(ok) else 0.95
    ok = np.where(rec >= review_recall)[0]
    review = float(thr[ok[-1]]) if len(ok) else float(np.quantile(p, 0.99))
    review = min(review, block)
    return {"review": round(review, 5), "block": round(block, 5)}


def operating_point(y, p, t):
    pred = p >= t
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
    return {"threshold": round(float(t), 5), "precision": round(tp / max(tp + fp, 1), 4),
            "recall": round(tp / max(tp + fn, 1), 4),
            "alerts_per_10k": round((tp + fp) / max(len(y), 1) * 1e4, 1)}


def _reference(X, scores, bins=10):
    ref = {"features": {}, "score": {}}
    for i, name in enumerate(FEATURES):
        col = X[:, i]
        edges = np.unique(np.quantile(col, np.linspace(0, 1, bins + 1)))
        if len(edges) < 3:                              # (near-)binary feature: use value buckets
            edges = np.array([col.min() - 0.5, (col.min() + col.max()) / 2, col.max() + 0.5])
        counts = np.histogram(col, bins=edges)[0]
        ref["features"][name] = {"edges": edges.tolist(), "props": (counts / counts.sum()).tolist()}
    edges = np.linspace(0, 1, 21)
    counts = np.histogram(scores, bins=edges)[0]
    ref["score"] = {"edges": edges.tolist(), "props": (counts / counts.sum()).tolist()}
    return ref


def train(X, y, sample_weight=None, version=None, notes=""):
    """Time-ordered 70/15/15 split. X, y must already be in time order."""
    n = len(y); i1, i2 = int(n * 0.70), int(n * 0.85)
    w = sample_weight if sample_weight is not None else np.ones(n)
    dtr = lgb.Dataset(X[:i1], y[:i1], weight=w[:i1], feature_name=FEATURES, free_raw_data=False)
    dva = lgb.Dataset(X[i1:i2], y[i1:i2], feature_name=FEATURES, reference=dtr)
    booster = lgb.train(PARAMS, dtr, num_boost_round=1500, valid_sets=[dva],
                        callbacks=[lgb.early_stopping(80, verbose=False)])
    p_va, p_te = booster.predict(X[i1:i2]), booster.predict(X[i2:])
    y_va, y_te = y[i1:i2], y[i2:]
    th = pick_thresholds(y_va, p_va)
    metrics = {
        "pr_auc": round(float(average_precision_score(y_te, p_te)), 4),
        "roc_auc": round(float(roc_auc_score(y_te, p_te)), 4),
        "review": operating_point(y_te, p_te, th["review"]),
        "block": operating_point(y_te, p_te, th["block"]),
        "n_train": int(i1), "n_test": int(n - i2), "test_frauds": int(y_te.sum()),
        "best_iteration": int(booster.best_iteration),
    }
    version = version or time.strftime("v%Y%m%d-%H%M%S")
    bundle = ModelBundle(booster, version, th, metrics, _reference(X[:i1], booster.predict(X[:i1])), notes=notes)
    return bundle, (X[i2:], y_te)


# ── registry ──────────────────────────────────────────────────────────────────
class Registry:
    """Filesystem model registry: models/<version>/bundle.joblib + models/current.json pointer."""

    def __init__(self, root):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)

    def save(self, bundle: ModelBundle, promote=False):
        d = self.root / bundle.version; d.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model_str": bundle.booster.model_to_string(), "version": bundle.version,
                     "thresholds": bundle.thresholds, "metrics": bundle.metrics,
                     "reference": bundle.reference, "features": bundle.features,
                     "trained_at": bundle.trained_at, "notes": bundle.notes}, d / "bundle.joblib")
        (d / "model_card.json").write_text(json.dumps(
            {"version": bundle.version, "metrics": bundle.metrics, "thresholds": bundle.thresholds,
             "features": bundle.features, "trained_at": bundle.trained_at, "notes": bundle.notes}, indent=2))
        if promote:
            self.promote(bundle.version)
        return d

    def promote(self, version):
        prev = self.current_version()
        (self.root / "current.json").write_text(json.dumps({"version": version, "previous": prev,
                                                             "promoted_at": time.time()}))

    def current_version(self):
        p = self.root / "current.json"
        return json.loads(p.read_text())["version"] if p.exists() else None

    def load(self, version=None):
        version = version or self.current_version()
        if version is None:
            raise FileNotFoundError(f"No promoted model in {self.root}. Run: python -m sentinelai train")
        d = joblib.load(self.root / version / "bundle.joblib")
        return ModelBundle(lgb.Booster(model_str=d["model_str"]), d["version"], d["thresholds"],
                           d["metrics"], d["reference"], d["features"], d["trained_at"], d.get("notes", ""))

    def versions(self):
        out = []
        for d in sorted(self.root.iterdir()):
            card = d / "model_card.json"
            if card.exists():
                out.append(json.loads(card.read_text()))
        return out
