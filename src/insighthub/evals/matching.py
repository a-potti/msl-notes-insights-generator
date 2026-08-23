"""Aligning predicted insights to labelled ones. Chapter 5 §5.5.

Before you can compute recall or precision on an extraction task you have to
decide when a predicted insight "is" a labelled one. That decision is a piece of
your evaluation, it is arbitrary, and it moves your numbers — so make it explicit
and report the threshold alongside every score.

We use embedding similarity plus greedy one-to-one matching. Alternatives worth
knowing: token overlap (cheap, brittle to paraphrase, useless here), an LLM
matcher (better on hard cases, expensive, and it needs its own validation), and
exact span overlap (only workable when both sides carry verbatim spans).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..embed import embed_texts

DEFAULT_THRESHOLD = 0.55


@dataclass
class MatchResult:
    note_id: str
    matched: list[tuple[int, str, float]] = field(default_factory=list)  # (pred_i, gold_seed, sim)
    unmatched_pred: list[int] = field(default_factory=list)   # false positives
    unmatched_gold: list[str] = field(default_factory=list)   # misses

    @property
    def tp(self) -> int:
        return len(self.matched)

    @property
    def fp(self) -> int:
        return len(self.unmatched_pred)

    @property
    def fn(self) -> int:
        return len(self.unmatched_gold)


def match_insights(pred_texts: list[str], gold: list[dict],
                   threshold: float = DEFAULT_THRESHOLD,
                   note_id: str = "") -> MatchResult:
    """Greedy highest-similarity-first one-to-one matching."""
    res = MatchResult(note_id=note_id)
    if not pred_texts or not gold:
        res.unmatched_pred = list(range(len(pred_texts)))
        res.unmatched_gold = [g["seed_id"] for g in gold]
        return res

    gold_texts = [g["canonical"] for g in gold]
    P = embed_texts(pred_texts)
    G = embed_texts(gold_texts)
    sim = P @ G.T

    used_p: set[int] = set()
    used_g: set[int] = set()
    order = np.dstack(np.unravel_index(np.argsort(-sim, axis=None), sim.shape))[0]
    for pi, gi in order:
        pi, gi = int(pi), int(gi)
        if sim[pi, gi] < threshold:
            break
        if pi in used_p or gi in used_g:
            continue
        used_p.add(pi)
        used_g.add(gi)
        res.matched.append((pi, gold[gi]["seed_id"], float(sim[pi, gi])))

    res.unmatched_pred = [i for i in range(len(pred_texts)) if i not in used_p]
    res.unmatched_gold = [gold[i]["seed_id"] for i in range(len(gold)) if i not in used_g]
    return res


def corpus_scores(rows: list[dict], gold_by_note: dict[str, dict],
                  threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Micro-averaged precision/recall/F1 over a run, plus category accuracy
    computed ONLY on matched pairs (scoring the category of a hallucinated
    insight is meaningless)."""
    tp = fp = fn = 0
    cat_right = cat_total = 0
    per_note = []
    for row in rows:
        g = gold_by_note.get(row["note_id"])
        if g is None:
            continue
        preds = [i["insight"] for i in row["insights"]]
        m = match_insights(preds, g["insights"], threshold, row["note_id"])
        tp, fp, fn = tp + m.tp, fp + m.fp, fn + m.fn
        gold_cat = {gi["seed_id"]: gi["category"] for gi in g["insights"]}
        for pi, seed, _ in m.matched:
            cat_total += 1
            cat_right += row["insights"][pi]["category"] == gold_cat[seed]
        per_note.append(m)

    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    return {
        "threshold": threshold,
        "tp": tp, "fp": fp, "fn": fn,
        "precision": prec, "recall": rec,
        "f1": 2 * prec * rec / max(prec + rec, 1e-9),
        "category_accuracy": cat_right / max(cat_total, 1),
        "per_note": per_note,
    }


def threshold_sensitivity(rows: list[dict], gold_by_note: dict[str, dict],
                          thresholds=(0.40, 0.50, 0.55, 0.60, 0.70)) -> list[dict]:
    """Always run this. If your headline F1 swings by 15 points across plausible
    thresholds, your metric is measuring your matcher, not your extractor."""
    out = []
    for t in thresholds:
        s = corpus_scores(rows, gold_by_note, t)
        out.append({k: s[k] for k in
                    ("threshold", "tp", "fp", "fn", "precision", "recall", "f1",
                     "category_accuracy")})
    return out
