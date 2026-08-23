#!/usr/bin/env python3
"""Chapter 1 §1.4 — how unstable is extraction, and does temperature=0 fix it?

Costs about $0.05. Watch the `identical` column: it is False even at temp 0.
"""
from insighthub.config import MODEL_FAST
from insighthub.corpus import get_note
from insighthub.extract import extract_note

NOTE_ID = "NOTE-0009"   # long advisory-board debrief, 6 seeded insights
N_RUNS = 5


def main() -> None:
    note = get_note(NOTE_ID)
    print(f"{NOTE_ID}: {len(note.body)} chars\n")
    for temp in (0.0, 0.3, 1.0):
        counts, catsets, texts = [], [], []
        for _ in range(N_RUNS):
            e = extract_note(note, model=MODEL_FAST, temperature=temp)
            counts.append(len(e.insights))
            catsets.append(tuple(sorted(i["category"] for i in e.insights)))
            texts.append(tuple(sorted(i["insight"] for i in e.insights)))
        print(f"temp={temp:<4} counts={counts} "
              f"distinct_category_sets={len(set(catsets))} "
              f"distinct_texts={len(set(texts))} "
              f"identical={len(set(texts)) == 1}")

    print("\nNow diff two temp=1.0 outputs by hand and ask: do they disagree about")
    print("WHICH insights exist, or about HOW they are worded? The first kind of")
    print("disagreement is pointing at a gap in your task definition.")


if __name__ == "__main__":
    main()
