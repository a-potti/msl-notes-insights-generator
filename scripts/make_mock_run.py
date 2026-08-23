#!/usr/bin/env python3
"""Build a synthetic extraction run so you can exercise the eval harness offline.

    python scripts/make_mock_run.py --out runs/mock_v1.jsonl --quality 0.7

Not a substitute for a real run — it is a fixture. Use it to check that your eval
code works before spending money finding out that it doesn't, and to give CI
something deterministic to run against.
"""
import argparse
import json
import random
from pathlib import Path

from insighthub.corpus import get_note, load_gold

BAD_PARAPHRASE = "Clinicians nationally report that {}"
ACTIVITY = "The MSL walked through the mechanism of action deck and shared the reprint."
PROMO = "VELTRAXA is clearly superior to the oral agents in this setting."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/mock_v1.jsonl")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--quality", type=float, default=0.7,
                    help="probability an insight is extracted correctly")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    rows = []
    for g in load_gold(args.split):
        note = get_note(g["note_id"])
        sentences = [s.strip() for s in note.body.replace("\n", " ").split(".")
                     if len(s.strip()) > 25]
        insights = []
        for gi in g["insights"]:
            if rng.random() > args.quality:
                continue                                  # a miss
            span = rng.choice(sentences) if sentences else note.body[:60]
            text = gi["canonical"]
            flags = list(gi["flags"])
            if rng.random() < 0.10:                       # overgeneralisation
                text = BAD_PARAPHRASE.format(text[0].lower() + text[1:])
            if rng.random() < 0.08:                       # unfaithful verbatim
                span = span + " (paraphrased)"
            if rng.random() < 0.15 and flags:             # dropped AE flag
                flags = []
            insights.append({
                "verbatim": span,
                "insight": text,
                "category": (gi["category"] if rng.random() < 0.85
                             else "COMPETITIVE_LANDSCAPE"),
                "sentiment": gi["sentiment"],
                "flags": flags,
                "strategic_priority": gi["strategic_priority"],
                "confidence": round(rng.uniform(0.6, 0.98), 2),
            })
        if rng.random() < 0.18 and sentences:             # spurious extraction
            insights.append({
                "verbatim": rng.choice(sentences),
                "insight": ACTIVITY if rng.random() < 0.7 else PROMO,
                "category": "SUMMARY_NO_INSIGHT",
                "sentiment": "neutral", "flags": [],
                "strategic_priority": "NONE", "confidence": 0.55,
            })
        rows.append({"note_id": g["note_id"], "prompt_version": "mock",
                     "insights": insights,
                     "suspicious": g["contains_injection"], "error": None,
                     "usage": None})

    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} mock extractions "
          f"({sum(len(r['insights']) for r in rows)} insights) to {p}")


if __name__ == "__main__":
    main()
