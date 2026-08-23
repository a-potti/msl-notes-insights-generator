#!/usr/bin/env python3
"""Chapter 6 §6.7 — where does the money actually go?

    python scripts/ch6_cost_report.py                     # all traces
    python scripts/ch6_cost_report.py --run-id ingest-1   # one run
    python scripts/ch6_cost_report.py --project           # annualised projection

Make this table before optimising anything. Half of all LLM cost work is spent
on the cheapest part of the system because nobody made this table.
"""
import argparse

from insighthub.observability import load_traces, print_summary, summary

# Annual volumes for the InsightHub deployment described in Chapter 6.
VOLUMES = {
    "extract": 6_000,           # 8 MSLs x 15 notes/week x 50 weeks
    "compliance_gate": 6_000,
    "agent": 5_000,             # ~20 analyst questions/day, several calls each
    "judge": 365 * 200,         # nightly eval suite
    "name_theme": 4 * 40,
    "report_synthesis": 4,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--project", action="store_true")
    args = ap.parse_args()

    rows = load_traces(args.run_id)
    if not rows:
        raise SystemExit("no traces found — call obs.start_tracing() before your run")

    print_summary(rows)
    s = summary(rows)

    if args.project:
        print(f"\nannualised projection at the Chapter 6 volumes:")
        print(f"{'step':22s} {'$/call':>9s} {'calls/yr':>10s} {'$/yr':>10s} {'share':>7s}")
        totals = {}
        for step, m in s["steps"].items():
            per_call = m["cost_usd"] / m["n"]
            vol = VOLUMES.get(step, 0)
            totals[step] = per_call * vol
        grand = sum(totals.values()) or 1.0
        for step, yearly in sorted(totals.items(), key=lambda kv: -kv[1]):
            m = s["steps"][step]
            print(f"{step:22s} {m['cost_usd']/m['n']:9.5f} "
                  f"{VOLUMES.get(step,0):10,d} {yearly:10,.2f} {yearly/grand:6.0%}")
        print(f"{'TOTAL':22s} {'':9s} {'':10s} {grand:10,.2f}")
        print("\nOptimise the top row. If the top row is your eval suite, the lever is")
        print("eval frequency and sampling, not inference cost.")

    # The cheap wins, checked
    print("\nsanity checks:")
    for step, m in s["steps"].items():
        if m["cache_hit_rate"] < 0.5:
            print(f"  ! {step}: cache hit rate {m['cache_hit_rate']:.0%} — is the "
                  f"prefix really byte-identical?")
        if m["truncation_rate"] > 0.01:
            print(f"  ! {step}: {m['truncation_rate']:.0%} of calls hit max_tokens — "
                  f"outputs are silently incomplete")
        if m["retry_rate"] > 0.10:
            print(f"  ! {step}: retry rate {m['retry_rate']:.0%}")


if __name__ == "__main__":
    main()
