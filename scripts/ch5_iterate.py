#!/usr/bin/env python3
"""Chapter 5 §5.8 — run one measured iteration on the extraction prompt.

    python scripts/ch5_iterate.py --version v2 --split dev
    python -m insighthub.evals.run --run runs/ch5_dev_v2.jsonl --split dev \
        --compare runs/ch1_dev_v1.jsonl

Prompt variants live in this file, side by side, so a diff between two versions
is a diff you can read. Keep every version you try — including the ones you
reverted. The graveyard is more instructive than the survivors.
"""
import argparse

from insighthub import extract
from insighthub.config import MODEL_WORK
from insighthub.corpus import notes_by_split

# --- v1: the Chapter 1 baseline (lives in extract.INSTRUCTIONS) -------------

# --- v2: iteration 1. ONE change: three negative examples drawn from real
#         failures found in §5.2 error analysis. Nothing else moved.
V2_ADDITION = """

## Worked negative examples
These are all things a previous version of this extractor wrongly returned as insights.

1. Note said: "Walked through the mechanism of action deck, no questions."
   WRONG: "The HCP was receptive to the mechanism of action data."
   Why: nothing was contributed by the HCP. This is MSL activity. Return nothing.

2. Note said: "We reviewed the AURORA-1 primary endpoint slides."
   WRONG: "The HCP is aware of the AURORA-1 induction results."
   Why: a restatement of what we presented. The company already knows this.

3. Note said: "He said his first four patients took closer to 8 weeks to improve."
   WRONG: "Clinicians find onset slower than the trial data implies."
   RIGHT: "This clinician observed symptomatic improvement at around 8 weeks in his
   first four patients, later than he expected from the trial data."
   Why: one clinician's four patients is not a statement about clinicians.
"""

# --- v3: iteration 2. ONE change: an explicit completeness instruction for
#         long notes, targeting MISSED_INSIGHT. Do not combine with v2's change
#         when measuring — that is two variables.
V3_ADDITION = V2_ADDITION + """

## Completeness
Before you finish, re-read the note and count the distinct things the HCP contributed.
Long notes from advisory boards and congress interactions routinely contain five or six.
If your list is shorter than your count, you have missed something. It is not unusual for
a single note to yield six insights.
"""

VARIANTS = {
    "v1": "",
    "v2": V2_ADDITION,
    "v3": V3_ADDITION,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=list(VARIANTS), default="v2")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--model", default=MODEL_WORK)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    base = extract.INSTRUCTIONS
    extract.INSTRUCTIONS = base + VARIANTS[args.version]
    try:
        notes = notes_by_split(args.split)
        exs = extract.extract_many(notes, model=args.model, temperature=0.0)
        out = args.out or f"runs/ch5_{args.split}_{args.version}.jsonl"
        for e in exs:
            e.prompt_version = args.version
        extract.save(exs, out)
        total = sum(len(e.insights) for e in exs)
        cost = sum(e.result.cost_usd for e in exs if e.result)
        print(f"{args.version}: {len(exs)} notes, {total} insights "
              f"({total/len(exs):.2f}/note), ${cost:.4f}")
        print(f"\nNow: python -m insighthub.evals.run --run {out} "
              f"--split {args.split} --compare runs/ch1_{args.split}_v1.jsonl")
    finally:
        extract.INSTRUCTIONS = base


if __name__ == "__main__":
    main()
