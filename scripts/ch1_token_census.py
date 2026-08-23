#!/usr/bin/env python3
"""Chapter 1 §1.2 — how big is our corpus, really?

Uses the free count_tokens endpoint, so this costs nothing but a few round trips.
"""
import statistics

from insighthub import llm
from insighthub.corpus import (fact_base, load_evidence, load_notes,
                               taxonomy_prompt_block)


def tok(text: str) -> int:
    return llm.count_tokens(messages=[{"role": "user", "content": text}])


def main() -> None:
    notes = load_notes()
    note_tokens = [tok(n.body) for n in notes]
    print(f"notes:          n={len(notes):3d}  total={sum(note_tokens):7,d}  "
          f"median={int(statistics.median(note_tokens)):4d}  max={max(note_tokens):4d}")

    ev = load_evidence()
    ev_tokens = [tok(d["text"]) for d in ev]
    print(f"evidence docs:  n={len(ev):3d}  total={sum(ev_tokens):7,d}  "
          f"median={int(statistics.median(ev_tokens)):4d}  max={max(ev_tokens):4d}")

    tax = tok(taxonomy_prompt_block())
    fb = tok(fact_base())
    print(f"taxonomy block: {tax:,}")
    print(f"fact base:      {fb:,}")
    print(f"\nEVERYTHING:     {sum(note_tokens) + sum(ev_tokens) + tax + fb:,} tokens")

    # chars-per-token by MSL style — see exercise 1
    print("\nchars/token by MSL:")
    by_msl: dict[str, list[tuple[int, int]]] = {}
    for n, t in zip(notes, note_tokens):
        by_msl.setdefault(n.msl_name, []).append((len(n.body), t))
    for msl, pairs in sorted(by_msl.items()):
        c = sum(p[0] for p in pairs)
        t = sum(p[1] for p in pairs)
        print(f"  {msl:16s} {c/t:.2f}  ({len(pairs)} notes)")


if __name__ == "__main__":
    main()
