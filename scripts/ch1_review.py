#!/usr/bin/env python3
"""Chapter 1 §1.12 — print extractions next to their source note for human review.

This tiny script is the most valuable tool in the repository. Error analysis is
not a phase you do once; it is the thing you do every time a number moves and you
do not know why. Make looking at data cheap and you will do it.

    python scripts/ch1_review.py runs/ch1_dev_v1.jsonl --n 20
    python scripts/ch1_review.py runs/ch1_dev_v1.jsonl --only-unfaithful
"""
import argparse
import random

from insighthub.corpus import get_note
from insighthub.extract import load


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--only-unfaithful", action="store_true",
                    help="show only notes with a verbatim span that isn't a real substring")
    ap.add_argument("--only-empty", action="store_true",
                    help="show only notes where nothing was extracted")
    ap.add_argument("--no-pause", action="store_true")
    args = ap.parse_args()

    rows = load(args.path)

    if args.only_unfaithful:
        rows = [r for r in rows
                if any(i["verbatim"] not in get_note(r["note_id"]).body
                       for i in r["insights"])]
    if args.only_empty:
        rows = [r for r in rows if not r["insights"]]

    random.Random(args.seed).shuffle(rows)
    rows = rows[:args.n]
    print(f"showing {len(rows)} extractions\n")

    for row in rows:
        note = get_note(row["note_id"])
        print("=" * 78)
        print(f"{note.note_id}  [{note.split}]  {note.msl_name}  {note.date}")
        print("-" * 78)
        print(note.body)
        print("-" * 78)
        if row.get("suspicious"):
            print("  ** model flagged suspicious content in this note **")
        if not row["insights"]:
            print("  (no insights extracted)")
        for i in row["insights"]:
            mark = "OK" if i["verbatim"] in note.body else "!!"
            flags = ",".join(i.get("flags") or []) or "-"
            print(f"  {mark} [{i['category']:<30s}] {i['insight']}")
            print(f"       flags={flags} sent={i['sentiment']} "
                  f"sp={i['strategic_priority']} conf={i['confidence']}")
            print(f"       verbatim: {i['verbatim'][:100]!r}")
        if not args.no_pause:
            input("\n[enter for next] ")
        else:
            print()


if __name__ == "__main__":
    main()
