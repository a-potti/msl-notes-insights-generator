#!/usr/bin/env python3
"""Chapter 1 §1.6 — same notes, three models. Cost, latency, faithfulness.

The point of this script is NOT to find the best model. It is to show you that
the differences you care about are rarely the ones you expected, and that at low
volume the cost column often does not matter at all.

Costs about $0.10.
"""
import statistics

from insighthub.config import MODEL_DEEP, MODEL_FAST, MODEL_WORK
from insighthub.corpus import get_note, notes_by_split
from insighthub.extract import extract_many

N_NOTES = 20
NOTES_PER_YEAR = 6000   # 8 MSLs x 15 notes/week x 50 weeks


def main() -> None:
    notes = notes_by_split("dev")[:N_NOTES]
    print(f"{'model':34s} {'insights':>8s} {'faithful':>9s} {'p50 lat':>8s} "
          f"{'cost':>9s} {'$/yr':>8s} {'err':>4s}")
    for model in (MODEL_FAST, MODEL_WORK, MODEL_DEEP):
        exs = extract_many(notes, model=model, temperature=0.0, progress=False)
        ok = [e for e in exs if e.ok and e.result]
        total = sum(len(e.insights) for e in ok)
        faithful = sum(
            1 for e in ok for i in e.insights
            if i["verbatim"] in get_note(e.note_id).body
        )
        cost = sum(e.result.cost_usd for e in ok)
        print(f"{model:34s} {total:8d} {faithful/max(total,1):8.1%} "
              f"{statistics.median(e.result.latency_s for e in ok):7.2f}s "
              f"${cost:8.4f} ${cost/N_NOTES*NOTES_PER_YEAR:7.2f} "
              f"{len(exs)-len(ok):4d}")

    print("\nRead the faithfulness column before the cost column.")


if __name__ == "__main__":
    main()
