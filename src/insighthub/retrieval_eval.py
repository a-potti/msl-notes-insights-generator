"""Retrieval evaluation. Chapter 3 §3.6 and §3.11.

Fix retrieval before you touch the generation prompt. If the right note is not
in the top k, no amount of prompt engineering will make the answer correct, and
you will spend a week rewording instructions to fix a search bug.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Callable

import numpy as np

from .config import EVAL_DIR
from .corpus import load_jsonl

Retriever = Callable[[str, int], list]   # (query, k) -> list of Hit


def load_queries() -> list[dict]:
    return load_jsonl(EVAL_DIR / "retrieval_queries.jsonl")


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return float("nan")
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / k


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for i, d in enumerate(retrieved, start=1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Binary-relevance nDCG. Rewards putting relevant items higher, not just
    having them somewhere in the top k."""
    dcg = sum((1.0 / np.log2(i + 1)) for i, d in enumerate(retrieved[:k], start=1)
              if d in relevant)
    ideal = sum(1.0 / np.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return float(dcg / ideal) if ideal else 0.0


@dataclass
class RetrievalReport:
    name: str
    k: int
    recall: float
    precision: float
    mrr: float
    ndcg: float
    per_query: list[dict]

    def __str__(self) -> str:
        return (f"{self.name:28s} k={self.k:<3d} recall={self.recall:.3f} "
                f"prec={self.precision:.3f} mrr={self.mrr:.3f} ndcg={self.ndcg:.3f}")

    def worst(self, n: int = 5) -> list[dict]:
        return sorted(self.per_query, key=lambda r: r["recall"])[:n]


def evaluate(retriever: Retriever, *, name: str, k: int = 10,
             queries: list[dict] | None = None) -> RetrievalReport:
    queries = queries or load_queries()
    rows = []
    for q in queries:
        relevant = set(q["relevant_note_ids"])
        hits = retriever(q["query"], k)
        got = [h.doc.doc_id for h in hits]
        rows.append({
            "query_id": q["query_id"], "query": q["query"],
            "n_relevant": len(relevant),
            "recall": recall_at_k(got, relevant, k),
            "precision": precision_at_k(got, relevant, k),
            "rr": reciprocal_rank(got, relevant),
            "ndcg": ndcg_at_k(got, relevant, k),
            "retrieved": got,
            "missed": sorted(relevant - set(got))[:5],
        })
    return RetrievalReport(
        name=name, k=k,
        recall=mean(r["recall"] for r in rows),
        precision=mean(r["precision"] for r in rows),
        mrr=mean(r["rr"] for r in rows),
        ndcg=mean(r["ndcg"] for r in rows),
        per_query=rows,
    )


def bootstrap_ci(report: RetrievalReport, metric: str = "recall",
                 n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    """30 queries is a small sample. Report the interval, not just the mean."""
    rng = np.random.default_rng(seed)
    vals = np.array([r[metric] for r in report.per_query])
    means = [rng.choice(vals, len(vals), replace=True).mean() for _ in range(n_boot)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))
