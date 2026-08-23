"""Theme discovery: cluster with maths, name with an LLM. Chapter 3 §3.13.

The division of labour is the whole idea. Clustering is deterministic, cheap,
reproducible and evaluable — so a clustering algorithm does it. Naming a cluster
in language a medical director recognises is a linguistic judgement — so the LLM
does that, and only that.

Ask an LLM to "find the themes in these 300 insights" and you get something
plausible, different every run, and impossible to evaluate.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from . import llm
from .config import MODEL_DEEP
from .embed import embed_texts


@dataclass
class Theme:
    theme_id: str
    member_ids: list[str]
    member_texts: list[str]
    name: str = ""
    summary: str = ""
    representative: str = ""
    size: int = 0
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------
def choose_k(X: np.ndarray, lo: int = 4, hi: int = 24) -> list[tuple[int, float]]:
    """Silhouette across a range of k. A curve to read, not an answer."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    out = []
    hi = min(hi, len(X) - 1)
    for k in range(lo, hi + 1):
        labels = KMeans(k, n_init=10, random_state=0).fit_predict(X)
        out.append((k, float(silhouette_score(X, labels))))
    return out


def cluster(texts: list[str], ids: list[str], *, k: int | None = None,
            method: str = "kmeans", min_cluster_size: int = 3) -> list[Theme]:
    """Group near-duplicate and near-synonymous insights.

    method="kmeans"  — every point gets a cluster. Simple, forces singletons into
                       a group they do not belong to.
    method="agglom"  — average-linkage with a distance threshold. No k required,
                       handles uneven cluster sizes, and (with the threshold) can
                       leave genuinely novel insights as singletons. Prefer this.
    """
    X = embed_texts(texts)
    if method == "kmeans":
        from sklearn.cluster import KMeans
        k = k or max(2, len(texts) // 12)
        labels = KMeans(k, n_init=10, random_state=0).fit_predict(X)
    elif method == "agglom":
        from sklearn.cluster import AgglomerativeClustering
        labels = AgglomerativeClustering(
            n_clusters=k, metric="cosine", linkage="average",
            distance_threshold=None if k else 0.45).fit_predict(X)
    else:
        raise ValueError(method)

    themes: list[Theme] = []
    for lab in sorted(set(labels)):
        idx = [i for i, l in enumerate(labels) if l == lab]
        centroid = X[idx].mean(axis=0)
        centroid /= max(np.linalg.norm(centroid), 1e-9)
        rep = idx[int(np.argmax(X[idx] @ centroid))]
        themes.append(Theme(
            theme_id=f"T-{lab:03d}",
            member_ids=[ids[i] for i in idx],
            member_texts=[texts[i] for i in idx],
            representative=texts[rep],
            size=len(idx),
            meta={"singleton": len(idx) < min_cluster_size},
        ))
    return sorted(themes, key=lambda t: -t.size)


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------
NAME_TOOL = {
    "name": "name_theme",
    "description": "Give the cluster of insights a name and a one-paragraph summary.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string",
                     "description": "6-10 words, states the substance, not the topic. "
                                    "'Onset slower than trial data implies', not 'Efficacy'."},
            "summary": {"type": "string",
                        "description": "2-3 sentences. What the field is saying and why "
                                       "it matters. No numbers you were not given."},
            "coherent": {"type": "boolean",
                         "description": "False if these insights are not really about "
                                        "one thing."},
            "outliers": {"type": "array", "items": {"type": "integer"},
                         "description": "0-based indices of members that do not belong."},
        },
        "required": ["name", "summary", "coherent", "outliers"],
    },
    "strict": True,
}

NAME_SYSTEM = """You name clusters of medical affairs field insights.

A good theme name states the substance in the field's own terms, so a medical director
reading a list of twelve theme names knows what each one is without opening it.

Bad:  "Efficacy"                          (a category, not a finding)
Bad:  "Concerns about the product"        (says nothing)
Good: "Onset slower in practice than AURORA-1 curves imply"
Good: "Step edits, not clinical reasoning, are setting line of therapy"

You are also the quality gate on the clustering. If the members are not really about one
thing, say so with coherent=false and list the indices that do not belong. Do not invent
a name that papers over a bad cluster — a false theme in a quarterly report is worse than
a missing one."""


def name_theme(theme: Theme, *, model: str = MODEL_DEEP, max_members: int = 25) -> Theme:
    members = theme.member_texts[:max_members]
    listing = "\n".join(f"{i}. {t}" for i, t in enumerate(members))
    res = llm.call(
        model=model, max_tokens=1024, temperature=0.0,
        system=[{"type": "text", "text": NAME_SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        tools=[NAME_TOOL], tool_choice={"type": "tool", "name": "name_theme"},
        messages=[{"role": "user", "content":
                   f"Cluster of {theme.size} insights "
                   f"(showing {len(members)}):\n\n{listing}"}],
        meta={"step": "name_theme", "theme_id": theme.theme_id},
    )
    uses = res.tool_uses()
    if uses:
        p = uses[0].input
        theme.name = p["name"]
        theme.summary = p["summary"]
        theme.meta["coherent"] = p["coherent"]
        theme.meta["outlier_idx"] = p["outliers"]
    return theme


def name_themes(themes: list[Theme], *, model: str = MODEL_DEEP,
                max_workers: int = 6) -> list[Theme]:
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(lambda t: name_theme(t, model=model), themes))


# ---------------------------------------------------------------------------
# A tiny KOL / theme graph — Chapter 3 §3.10
# ---------------------------------------------------------------------------
@dataclass
class Graph:
    """Adjacency over (kol_id, theme_id) and (theme_id, evidence_id).

    Forty lines instead of a graph database, because the question we need it for
    — 'which KOLs raised more than one of these themes, and which evidence
    addresses them?' — is two hops. Reach for a real graph store when you need
    variable-length paths or transitive closure, not before.
    """
    kol_themes: dict[str, set[str]] = field(default_factory=dict)
    theme_kols: dict[str, set[str]] = field(default_factory=dict)
    theme_evidence: dict[str, set[str]] = field(default_factory=dict)

    def add_mention(self, kol_id: str, theme_id: str) -> None:
        self.kol_themes.setdefault(kol_id, set()).add(theme_id)
        self.theme_kols.setdefault(theme_id, set()).add(kol_id)

    def add_evidence(self, theme_id: str, doc_id: str) -> None:
        self.theme_evidence.setdefault(theme_id, set()).add(doc_id)

    def kols_for(self, theme_id: str) -> set[str]:
        return self.theme_kols.get(theme_id, set())

    def co_occurring_themes(self, theme_id: str, min_shared: int = 2) -> list[tuple[str, int]]:
        """Themes raised by the same people. 'The KOLs worried about durability are
        the same ones asking for TDM' is a finding you cannot get from a vector index."""
        kols = self.kols_for(theme_id)
        counts: dict[str, int] = {}
        for k in kols:
            for t in self.kol_themes.get(k, ()):
                if t != theme_id:
                    counts[t] = counts.get(t, 0) + 1
        return sorted(((t, c) for t, c in counts.items() if c >= min_shared),
                      key=lambda kv: -kv[1])

    def unsupported_themes(self) -> list[str]:
        """Themes with no linked evidence — the medical strategy gap list."""
        return sorted(t for t in self.theme_kols if not self.theme_evidence.get(t))


def build_graph(themes: list[Theme], insight_to_kol: dict[str, str],
                evidence_index=None, top_evidence: int = 3) -> Graph:
    g = Graph()
    for t in themes:
        for iid in t.member_ids:
            kol = insight_to_kol.get(iid)
            if kol:
                g.add_mention(kol, t.theme_id)
        if evidence_index is not None:
            query = t.name or t.representative
            for hit in evidence_index.hybrid_search(query, top_evidence):
                g.add_evidence(t.theme_id, hit.doc.doc_id)
    return g
