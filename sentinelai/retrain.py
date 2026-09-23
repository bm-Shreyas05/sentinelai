"""Training and champion/challenger retraining with analyst feedback.

Analyst-resolved cases become labelled rows (weighted higher, since they are the institution's
own ground truth) and are added to the base training data. The challenger is promoted only if
it passes the gate in policy FRF-3.3; otherwise it is saved but not served.
"""
import json, time

import numpy as np
from sklearn.metrics import average_precision_score

from . import db
from .features import FEATURES
from .model import Registry, build_matrix, operating_point, train
from .synthetic import Simulator

FEEDBACK_WEIGHT = 3.0


def base_dataset(n_events=250_000, seed=11, n_users=3000):
    events = list(Simulator(n_users=n_users, seed=seed).stream(n_events))
    return build_matrix(events)


def feedback_rows(conn):
    rows = conn.execute("SELECT features, label FROM transactions WHERE label IS NOT NULL ORDER BY ts").fetchall()
    if not rows:
        return np.empty((0, len(FEATURES))), np.empty(0, dtype=int)
    X = np.array([[json.loads(r["features"])[f] for f in FEATURES] for r in rows])
    return X, np.array([r["label"] for r in rows], dtype=int)


def train_initial(settings, n_events=250_000, seed=11):
    X, y = base_dataset(n_events, seed)
    bundle, _ = train(X, y, notes=f"initial model, {n_events} simulated events (seed {seed})")
    Registry(settings.model_dir).save(bundle, promote=True)
    return bundle


def retrain(settings, n_events=250_000, seed=None, min_gain=0.003, max_recall_drop=0.01, force=False):
    conn = db.connect(settings.db_path)
    reg = Registry(settings.model_dir)
    champion = reg.load()
    Xb, yb = base_dataset(n_events, seed if seed is not None else int(time.time()) % 10_000)
    Xf, yf = feedback_rows(conn)
    X, y = np.vstack([Xb, Xf]), np.concatenate([yb, yf])
    w = np.concatenate([np.ones(len(yb)), np.full(len(yf), FEEDBACK_WEIGHT)])
    challenger, (Xte, yte) = train(X, y, sample_weight=w,
                                   notes=f"retrain: {len(yb)} base rows + {len(yf)} analyst labels")

    # Evaluate both models on the challenger's (most recent) held-out slice
    p_ch, p_ch_old = challenger.predict_batch(Xte), champion.predict_batch(Xte)
    ch = {"pr_auc": float(average_precision_score(yte, p_ch)),
          "recall": operating_point(yte, p_ch, challenger.thresholds["review"])["recall"]}
    old = {"pr_auc": float(average_precision_score(yte, p_ch_old)),
           "recall": operating_point(yte, p_ch_old, champion.thresholds["review"])["recall"]}
    gain, recall_drop = ch["pr_auc"] - old["pr_auc"], old["recall"] - ch["recall"]
    promote = force or (gain >= min_gain and recall_drop <= max_recall_drop)
    decision = "PROMOTED" if promote else "REJECTED"
    reason = (f"PR-AUC {old['pr_auc']:.4f} → {ch['pr_auc']:.4f} (Δ {gain:+.4f}, need ≥ {min_gain}); "
              f"review recall {old['recall']:.3f} → {ch['recall']:.3f}")
    challenger.metrics["comparison"] = {"champion": champion.version, "decision": decision, "reason": reason,
                                        "feedback_labels": int(len(yf))}
    reg.save(challenger, promote=promote)
    db.audit(conn, "retrain", "retrain_run", {"challenger": challenger.version, "champion": champion.version,
                                              "decision": decision, "reason": reason})
    return {"decision": decision, "reason": reason, "challenger": challenger.version,
            "champion": champion.version, "feedback_labels": int(len(yf))}
