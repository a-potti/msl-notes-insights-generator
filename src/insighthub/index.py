"""Retrieval: a vector index, a BM25 index, and a hybrid of the two.

Chapter 3 §3.4-§3.8. Both indexes are implemented here rather than imported from
a library, because the point of Chapter 3 is that you should be able to explain
why a document came back. Neither is more than forty lines. When you outgrow
them (roughly: > 1M chunks, or you need filtered ANN search at low latency) reach
for a real vector database and keep the interface.
"""
from __future__ import annotations

import json
import math
import pickle
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from .config import INDEX_DIR
from .embed import embed_one, embed_texts


@dataclass
class Doc:
    doc_id: str
    text: str
    meta: dict = field(default_factory=dict)


@dataclass
class Hit:
    doc: Doc
    score: float
    source: str = ""

    def __repr__(self) -> str:
        return f"Hit({self.doc.doc_id}, {self.score:.4f}, {self.source})"


Filter = Callable[[Doc], bool] | None


# ---------------------------------------------------------------------------
# BM25 — a lexical scorer in forty lines
# ---------------------------------------------------------------------------
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25:
    """Okapi BM25.

        score(q, d) = SUM_t IDF(t) * f(t,d)*(k1+1) / (f(t,d) + k1*(1-b+b*|d|/avgdl))

    k1 controls term-frequency saturation (a word appearing 10 times is not 10x
    as relevant); b controls length normalisation. The defaults are the defaults
    for a reason — tune them last, if ever.
    """

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.N = len(corpus)
        self.doc_len = np.array([len(d) for d in corpus], dtype=np.float32)
        self.avgdl = float(self.doc_len.mean()) if self.N else 0.0
        self.tf: list[Counter] = [Counter(d) for d in corpus]
        df: Counter = Counter()
        for c in self.tf:
            df.update(c.keys())
        # BM25+ style IDF floor keeps very common terms from going negative.
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5))
                    for t, n in df.items()}

    def scores(self, query: str) -> np.ndarray:
        out = np.zeros(self.N, dtype=np.float32)
        for term in tokenize(query):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(term, 0)
                if f:
                    denom = f + self.k1 * (1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                    out[i] += idf * f * (self.k1 + 1) / denom
        return out


# ---------------------------------------------------------------------------
# The index
# ---------------------------------------------------------------------------
class Index:
    """Vector + lexical retrieval over a list of Docs."""

    def __init__(self, docs: list[Doc]):
        self.docs = docs
        self.vectors: np.ndarray | None = None
        self.bm25: BM25 | None = None

    # -- build ------------------------------------------------------------
    def build(self, *, verbose: bool = True) -> "Index":
        if verbose:
            print(f"embedding {len(self.docs)} docs...")
        self.vectors = embed_texts([d.text for d in self.docs])
        self.bm25 = BM25([tokenize(d.text) for d in self.docs])
        return self

    # -- search -----------------------------------------------------------
    def _allowed(self, where: Filter) -> np.ndarray:
        if where is None:
            return np.ones(len(self.docs), dtype=bool)
        return np.array([bool(where(d)) for d in self.docs])

    def vector_search(self, query: str, k: int = 5, where: Filter = None) -> list[Hit]:
        """Cosine similarity. Vectors are L2-normalised, so it is a dot product."""
        assert self.vectors is not None, "call build() first"
        q = embed_one(query)
        sims = self.vectors @ q                       # <- the entire algorithm
        sims = np.where(self._allowed(where), sims, -np.inf)
        idx = np.argpartition(-sims, min(k, len(sims) - 1))[:k]
        idx = idx[np.argsort(-sims[idx])]
        return [Hit(self.docs[i], float(sims[i]), "vector")
                for i in idx if np.isfinite(sims[i])]

    def keyword_search(self, query: str, k: int = 5, where: Filter = None) -> list[Hit]:
        assert self.bm25 is not None, "call build() first"
        s = self.bm25.scores(query)
        s = np.where(self._allowed(where), s, -np.inf)
        idx = np.argsort(-s)[:k]
        return [Hit(self.docs[i], float(s[i]), "bm25")
                for i in idx if np.isfinite(s[i]) and s[i] > 0]

    def hybrid_search(self, query: str, k: int = 5, where: Filter = None,
                      rrf_k: int = 60, pool: int = 40) -> list[Hit]:
        """Reciprocal Rank Fusion.

            RRF(d) = SUM_over_rankers 1 / (rrf_k + rank(d))

        RRF fuses *ranks*, not scores, which is why it works: a cosine similarity
        of 0.42 and a BM25 score of 11.3 are not on comparable scales and any
        weighted sum of them is a fudge factor you will spend a week tuning.
        Ranks are always comparable. rrf_k=60 is the value from the original
        paper and is almost never worth changing.
        """
        v = self.vector_search(query, pool, where)
        b = self.keyword_search(query, pool, where)
        fused: dict[str, float] = {}
        srcs: dict[str, set] = {}
        for hits, name in ((v, "vector"), (b, "bm25")):
            for rank, h in enumerate(hits, start=1):
                fused[h.doc.doc_id] = fused.get(h.doc.doc_id, 0.0) + 1.0 / (rrf_k + rank)
                srcs.setdefault(h.doc.doc_id, set()).add(name)
        by_id = {d.doc_id: d for d in self.docs}
        ranked = sorted(fused.items(), key=lambda kv: -kv[1])[:k]
        return [Hit(by_id[i], s, "+".join(sorted(srcs[i]))) for i, s in ranked]

    # -- persistence ------------------------------------------------------
    def save(self, name: str = "main") -> Path:
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        path = INDEX_DIR / f"{name}.pkl"
        with open(path, "wb") as f:
            pickle.dump({"docs": [asdict(d) for d in self.docs],
                         "vectors": self.vectors, "bm25": self.bm25}, f)
        return path

    @classmethod
    def load(cls, name: str = "main") -> "Index":
        with open(INDEX_DIR / f"{name}.pkl", "rb") as f:
            blob = pickle.load(f)
        idx = cls([Doc(**d) for d in blob["docs"]])
        idx.vectors, idx.bm25 = blob["vectors"], blob["bm25"]
        return idx


# ---------------------------------------------------------------------------
# Filters — the part vector search cannot do
# ---------------------------------------------------------------------------
def meta_filter(**constraints) -> Filter:
    """Exact-match metadata filter. `since` and `until` are special-cased on date.

        meta_filter(region="EMEA", kol_tier=1, since="2026-02-18")

    'What are EMEA tier-1 KOLs saying since ECCO?' is two filters and one
    semantic query. Trying to express the filters semantically is the single most
    common retrieval mistake — embeddings have no idea what 'since February' means.
    """
    since = constraints.pop("since", None)
    until = constraints.pop("until", None)

    def f(doc: Doc) -> bool:
        for key, want in constraints.items():
            got = doc.meta.get(key)
            if isinstance(want, (list, tuple, set)):
                if got not in want:
                    return False
            elif got != want:
                return False
        d = doc.meta.get("date")
        if since and (d is None or d < since):
            return False
        if until and (d is None or d > until):
            return False
        return True

    return f


# ---------------------------------------------------------------------------
# Corpus builders
# ---------------------------------------------------------------------------
def notes_index(splits: Iterable[str] | None = None) -> Index:
    """One chunk per note. Notes are ~100 tokens; chunking them would be silly."""
    from .corpus import load_notes
    docs = [
        Doc(doc_id=n.note_id, text=n.body,
            meta={"kind": "note", "date": n.date, "msl_id": n.msl_id,
                  "region": n.region, "kol_id": n.kol_id, "kol_tier": n.kol_tier,
                  "interaction_type": n.interaction_type, "split": n.split})
        for n in load_notes() if splits is None or n.split in splits
    ]
    return Index(docs)


def evidence_index() -> Index:
    """Congress abstracts and publications, section-chunked."""
    from .corpus import load_evidence
    from .docs import chunk_markdown

    docs: list[Doc] = []
    for d in load_evidence():
        meta = {"kind": d.get("source_type", "evidence"),
                "title": d.get("title"), "date": str(d.get("date", "")),
                "congress": d.get("congress_code"), "parent_id": d["doc_id"]}
        for c in chunk_markdown(d["doc_id"], d["text"], meta):
            docs.append(Doc(doc_id=c.chunk_id, text=c.text, meta={**c.meta}))
    return Index(docs)
