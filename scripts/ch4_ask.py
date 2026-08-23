#!/usr/bin/env python3
"""Chapter 4 §4.3 — ask the analyst agent a question and read the transcript.

    python scripts/ch4_ask.py "What is driving physicians toward competitors?"
    python scripts/ch4_ask.py --answer-only "Which themes have no supporting evidence?"

Read the transcript, not just the answer. Agent debugging is transcript reading.
"""
import argparse

from insighthub.agent import run_agent
from insighthub.config import MODEL_WORK
from insighthub.index import evidence_index, notes_index
from insighthub.tools import default_registry

SUGGESTIONS = [
    "What is driving physicians toward competitors, and how widespread is it?",
    "What have EMEA tier-1 KOLs raised about durability since ECCO 2026?",
    "Which questions is the field asking that we have no published evidence for?",
    "Are the KOLs worried about loss of response the same ones asking about drug levels?",
    "Which high-influence KOLs have we not engaged this year?",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="*", help="if omitted, runs the suggestion list")
    ap.add_argument("--model", default=MODEL_WORK)
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument("--answer-only", action="store_true")
    args = ap.parse_args()

    notes = notes_index().build()
    evidence = evidence_index().build()
    registry = default_registry(notes, evidence)

    questions = [" ".join(args.question)] if args.question else SUGGESTIONS
    for q in questions:
        run = run_agent(q, registry, model=args.model, max_steps=args.max_steps)
        print("=" * 78)
        print(run.transcript() if not args.answer_only else f"Q: {q}\nA: {run.answer}")
        print("-" * 78)
        print(run.summary())
        if run.injections_seen:
            print(f"!! injection patterns surfaced in tool output: {run.injections_seen}")
        print()


if __name__ == "__main__":
    main()
