#!/usr/bin/env python3
"""Chapter 3 §3.6-§3.7 — evaluate BM25, vector and hybrid retrieval.

Free (no LLM calls). Run it every time you touch the index, chunker or embedder.

    python scripts/ch3_retrieval_eval.py
    python scripts/ch3_retrieval_eval.py --worst 8
"""
import argparse

from insighthub.embed import backend_warning
from insighthub.index import notes_index
from insighthub.retrieval_eval import bootstrap_ci, evaluate


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ks", type=int, nargs="+", default=[5, 10, 20, 30])
    ap.add_argument("--worst", type=int, default=5)
    args = ap.parse_args()

    warn = backend_warning()
    if warn:
        print(f"!! {warn}\n")

    ix = notes_index().build()
    retrievers = {
        "bm25": ix.keyword_search,
        "vector": ix.vector_search,
        "hybrid": ix.hybrid_search,
    }

    print()
    for name, fn in retrievers.items():
        for k in args.ks:
            rep = evaluate(lambda q, kk, f=fn: f(q, kk), name=name, k=k)
            lo, hi = bootstrap_ci(rep)
            print(f"{rep}  recall95CI=[{lo:.3f},{hi:.3f}]")
        print()

    print("worst queries for hybrid @k=10 — read these, they tell you what to fix:")
    rep = evaluate(lambda q, kk: ix.hybrid_search(q, kk), name="hybrid", k=10)
    for w in rep.worst(args.worst):
        print(f"  {w['query_id']} recall={w['recall']:.2f} "
              f"n_relevant={w['n_relevant']:<3d} {w['query']}")
        print(f"      missed: {', '.join(w['missed'])}")

    print("\nTwo failure modes look identical in this table and need opposite fixes:")
    print("  (a) no lexical overlap        -> embeddings help")
    print("  (b) query spans many themes   -> decomposition helps (Chapter 4), not tuning")


if __name__ == "__main__":
    main()
