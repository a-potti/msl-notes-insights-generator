"""Chapter 2 — the insight triage model.

Business framing: the medical strategy team can review ~40 insights a week. We
generate far more than that. The model's job is to rank, so that the 40 they read
are the 40 most worth reading. That framing decides the metric (precision in the
top-k), the threshold, and what a "good" model even means here.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             precision_recall_curve, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import ML_DIR

TARGET = "selected_for_review"

CATEGORICAL = ["category", "region"]
NUMERIC = [
    "kol_tier",
    "kol_is_investigator",
    "novelty_score",
    "n_corroborating_notes",
    "sentiment",
    "has_compliance_flag",
    "insight_char_length",
    "aligned_to_strategic_priority",
]
# days_since_captured is deliberately EXCLUDED. See Chapter 2 §2.4: it encodes
# position in time, so a model trained on old rows and applied to new rows learns
# a coefficient that cannot transfer. Either drop it or re-express it relative to
# prediction time. We drop it.
EXCLUDED = ["days_since_captured", "insight_id"]

REVIEW_CAPACITY_PER_WEEK = 40
INSIGHTS_PER_WEEK = 250   # 8 MSLs x 15 notes x ~2 insights


def load_history() -> pd.DataFrame:
    return pd.read_csv(ML_DIR / "insight_review_history.csv")


def temporal_split(df: pd.DataFrame, cutoff_days: int = 120):
    """Older rows train, newer rows test. Random splits flatter you."""
    train = df[df["days_since_captured"] >= cutoff_days].copy()
    test = df[df["days_since_captured"] < cutoff_days].copy()
    return train, test


def make_pipeline(kind: str = "logreg") -> Pipeline:
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("num", StandardScaler(), NUMERIC),
    ])
    if kind == "logreg":
        clf = LogisticRegression(max_iter=2000, class_weight=None)
    elif kind == "logreg_balanced":
        clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    elif kind == "gbm":
        clf = GradientBoostingClassifier(random_state=0)
    else:
        raise ValueError(kind)
    return Pipeline([("pre", pre), ("clf", clf)])


@dataclass
class Scored:
    y_true: np.ndarray
    y_prob: np.ndarray

    def metrics(self) -> dict:
        return {
            "base_rate": float(self.y_true.mean()),
            "roc_auc": float(roc_auc_score(self.y_true, self.y_prob)),
            "pr_auc": float(average_precision_score(self.y_true, self.y_prob)),
            "brier": float(brier_score_loss(self.y_true, self.y_prob)),
        }

    def precision_at_k(self, k: int) -> float:
        """The metric that matches the actual decision: we read the top k."""
        idx = np.argsort(-self.y_prob)[:k]
        return float(self.y_true[idx].mean())

    def recall_at_k(self, k: int) -> float:
        idx = np.argsort(-self.y_prob)[:k]
        return float(self.y_true[idx].sum() / max(self.y_true.sum(), 1))

    def threshold_for_volume(self, n_flagged: int) -> float:
        """The score cutoff that flags exactly n_flagged items."""
        return float(np.sort(self.y_prob)[::-1][min(n_flagged, len(self.y_prob)) - 1])


def fit_and_score(train: pd.DataFrame, test: pd.DataFrame, kind: str = "logreg",
                  calibrate: str | None = None) -> tuple[Pipeline, Scored]:
    X_tr, y_tr = train.drop(columns=[TARGET] + EXCLUDED), train[TARGET].to_numpy()
    X_te, y_te = test.drop(columns=[TARGET] + EXCLUDED), test[TARGET].to_numpy()
    pipe = make_pipeline(kind)
    if calibrate:
        pipe = CalibratedClassifierCV(pipe, method=calibrate, cv=5)
    pipe.fit(X_tr, y_tr)
    prob = pipe.predict_proba(X_te)[:, 1]
    return pipe, Scored(y_te, prob)


# ---------------------------------------------------------------------------
# Baselines. Always build these first, always report them.
# ---------------------------------------------------------------------------

def baseline_majority(test: pd.DataFrame) -> Scored:
    y = test[TARGET].to_numpy()
    return Scored(y, np.full(len(y), y.mean()))


def baseline_rules(test: pd.DataFrame) -> Scored:
    """The rule the strategy team uses today, written down as code.

    'Show me tier-1 KOLs, or anything with a compliance flag, or anything with
    lots of corroboration.' If your model cannot beat this, do not ship a model.
    """
    y = test[TARGET].to_numpy()
    score = (
        0.40 * (test["kol_tier"] == 1).to_numpy()
        + 0.30 * test["has_compliance_flag"].to_numpy()
        + 0.20 * (test["n_corroborating_notes"] >= 4).to_numpy()
        + 0.10 * test["aligned_to_strategic_priority"].to_numpy()
    )
    return Scored(y, score)


# ---------------------------------------------------------------------------
# Calibration diagnostics
# ---------------------------------------------------------------------------

def reliability_table(scored: Scored, n_bins: int = 10) -> pd.DataFrame:
    """Predicted probability vs observed frequency. The honesty check."""
    bins = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(scored.y_prob, bins) - 1, 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        rows.append({
            "bin": f"{bins[b]:.1f}-{bins[b+1]:.1f}",
            "n": int(m.sum()),
            "mean_predicted": float(scored.y_prob[m].mean()),
            "observed_rate": float(scored.y_true[m].mean()),
            "gap": float(scored.y_prob[m].mean() - scored.y_true[m].mean()),
        })
    return pd.DataFrame(rows)


def expected_value(scored: Scored, threshold: float,
                   value_true_positive: float = 1.0,
                   cost_false_positive: float = 0.15,
                   cost_false_negative: float = 2.0) -> dict:
    """Turn a threshold into money-shaped units.

    The defaults encode a claim: a missed strategically-relevant insight costs
    about 13x more than a wasted five minutes of an analyst's reading time.
    That claim comes from the business, not from the data. Argue about it
    explicitly rather than hiding it inside an F1 score.
    """
    pred = scored.y_prob >= threshold
    tp = int((pred & (scored.y_true == 1)).sum())
    fp = int((pred & (scored.y_true == 0)).sum())
    fn = int((~pred & (scored.y_true == 1)).sum())
    tn = int((~pred & (scored.y_true == 0)).sum())
    ev = tp * value_true_positive - fp * cost_false_positive - fn * cost_false_negative
    return {"threshold": round(threshold, 4), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "flagged": tp + fp,
            "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1),
            "expected_value": round(ev, 2)}


def sweep_thresholds(scored: Scored, **kw) -> pd.DataFrame:
    prec, rec, thr = precision_recall_curve(scored.y_true, scored.y_prob)
    rows = [expected_value(scored, t, **kw) for t in np.quantile(thr, np.linspace(0.5, 0.995, 25))]
    return pd.DataFrame(rows)
