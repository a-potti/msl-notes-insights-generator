#!/usr/bin/env python3
"""Chapter 5 §5.2 — structured error analysis (open coding) over a run.

    python scripts/ch5_error_analysis.py runs/ch1_dev_v1.jsonl --n 30
    python scripts/ch5_error_analysis.py runs/ch1_dev_v1.jsonl --report

Phase 1 (open coding): you look at outputs and write a free-text note on every
problem you see. No taxonomy yet — inventing categories before looking is how you
end up measuring the failures you imagined instead of the ones you have.

Phase 2 (axial coding): you group your free-text notes into a taxonomy and count.
The counts are what tell you where to spend the next week.

This tool is deliberately manual. There is no way to skip the looking.
"""
import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path

from insighthub.corpus import get_note
from insighthub.extract import load

LOG = Path("runs/error_analysis.csv")
FIELDS = ["run", "note_id", "insight_idx", "insight", "verbatim_ok", "note",
          "code"]


def existing() -> list[dict]:
    if not LOG.exists():
        return []
    return list(csv.DictReader(open(LOG)))


def append(rows: list[dict]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)


def code(args) -> None:
    rows = load(args.path)
    random.Random(args.seed).shuffle(rows)
    seen = {(r["run"], r["note_id"]) for r in existing()}
    out = []
    done = 0
    print("For each note: press enter if the extraction is fine, or type what is")
    print("wrong in your own words. Do NOT use a fixed vocabulary yet.")
    print("Type 'q' to stop and save.\n")

    for row in rows:
        if (args.path, row["note_id"]) in seen:
            continue
        if done >= args.n:
            break
        note = get_note(row["note_id"])
        print("=" * 78)
        print(f"{note.note_id}  [{note.split}]  {note.msl_name}")
        print("-" * 78)
        print(note.body)
        print("-" * 78)
        if not row["insights"]:
            print("  (nothing extracted)")
        for i, ins in enumerate(row["insights"]):
            ok = "OK" if ins["verbatim"] in note.body else "!!"
            print(f"  [{i}] {ok} ({ins['category']}) {ins['insight']}")
            print(f"        verbatim: {ins['verbatim'][:90]!r}")
        ans = input("\nwhat's wrong? (enter = nothing, q = quit) > ").strip()
        if ans.lower() == "q":
            break
        done += 1
        out.append({
            "run": args.path, "note_id": row["note_id"], "insight_idx": "",
            "insight": "", "verbatim_ok": all(
                i["verbatim"] in note.body for i in row["insights"]),
            "note": ans, "code": "",
        })

    append(out)
    print(f"\nlogged {len(out)} observations to {LOG}")
    print("Now open it, and in the `code` column group your free-text notes into")
    print("a small taxonomy. Then re-run with --report.")


def report(args) -> None:
    rows = existing()
    if not rows:
        raise SystemExit(f"nothing in {LOG} yet — run without --report first")
    coded = [r for r in rows if r["code"].strip()]
    uncoded = len(rows) - len(coded)
    clean = sum(1 for r in rows if not r["note"].strip())
    print(f"{len(rows)} observations, {clean} with no problem noted, "
          f"{uncoded} not yet coded\n")
    counts = Counter(r["code"].strip() for r in coded)
    total = sum(counts.values())
    for code_name, n in counts.most_common():
        print(f"  {n:4d}  {n/max(total,1):6.1%}  {code_name}")
    print("\nWork on the top row. Not the one that annoyed you most — the top row.")
    print("Then re-run this after your change and check that the top row moved,")
    print("and that nothing below it got worse.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="runs/ch1_dev_v1.jsonl")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    (report if args.report else code)(args)


if __name__ == "__main__":
    main()
