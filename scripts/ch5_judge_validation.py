#!/usr/bin/env python3
"""Chapter 5 §5.6-§5.7 — validate the LLM judge against human labels.

    python scripts/ch5_judge_validation.py --version v1 --show-disagreements
    python scripts/ch5_judge_validation.py --version v2 --show-disagreements
    python scripts/ch5_judge_validation.py --compare

Run v1 first and look at the disagreements before reading v2's prompt. The whole
lesson is in the gap between "the judge is wrong" and "I never told it my criteria".

Costs ~$0.30 per version on the 60-example calibration set.
"""
import argparse

from insighthub.config import MODEL_DEEP
from insighthub.evals.judge import (JUDGE_V1, JUDGE_V2, correct_pass_rate,
                                    validate_judge)

VERSIONS = {"v1": JUDGE_V1, "v2": JUDGE_V2}


def show(name: str, val, show_dis: bool, limit: int) -> None:
    print(f"\nJUDGE_{name.upper()}  {val}")
    print(f"usable (kappa>=0.6, TPR>=0.8, TNR>=0.8): {val.usable()}")
    if show_dis and val.disagreements:
        print(f"\n{len(val.disagreements)} disagreements — read these, not the score:")
        for d in val.disagreements[:limit]:
            print(f"\n  {d['example_id']}  human={d['human']} judge={d['judge']}")
            print(f"    candidate: {d['candidate']}")
            print(f"    human_why: {d['human_why']}")
            print(f"    judge_why: {d['judge_why']}")
    if val.usable():
        for observed in (0.6, 0.7, 0.8):
            print(f"  observed pass rate {observed:.0%} -> corrected "
                  f"{correct_pass_rate(observed, val.tpr, val.tnr):.1%}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", choices=list(VERSIONS), default="v2")
    ap.add_argument("--model", default=MODEL_DEEP)
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--show-disagreements", action="store_true")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--compare", action="store_true", help="run both versions")
    args = ap.parse_args()

    names = list(VERSIONS) if args.compare else [args.version]
    for name in names:
        val = validate_judge(VERSIONS[name], model=args.model, n=args.n)
        show(name, val, args.show_disagreements, args.limit)

    print("\nA judge below the bar must not gate anything. If yours is below it,")
    print("read your disagreements, make ONE change to the prompt, and re-measure.")


if __name__ == "__main__":
    main()
