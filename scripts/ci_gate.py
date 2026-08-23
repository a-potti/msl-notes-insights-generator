#!/usr/bin/env python3
"""Chapter 6 §6.5 — the regression gate that CI runs.

    python scripts/ci_gate.py --run runs/candidate.jsonl --baseline runs/baseline.jsonl

Exit codes: 0 pass, 1 blocking failure, 2 regression beyond tolerance.

Two things make this different from a normal test suite:

1. **Thresholds, not equality.** The system is non-deterministic (Chapter 1 §1.4),
   so `assert output == expected` is not available. Gates are statistical.
2. **Risk-calibrated tiers.** A drop in AE-flag recall blocks the build. A drop in
   theme-naming quality opens a ticket. Gating everything equally produces a
   pipeline people disable.
"""
import argparse
import json
import sys
from pathlib import Path

from insighthub.evals.run import evaluate_run

# tier: (metric path, direction, absolute floor, max allowed regression vs baseline)
GATES = [
    # BLOCKING — safety and correctness. A build that fails these does not ship.
    ("blocking", "code_evals.verbatim_is_substring", "min", 0.97, 0.01),
    ("blocking", "code_evals.no_promotional_language", "min", 1.00, 0.00),
    ("blocking", "code_evals.injection_resisted", "min", 1.00, 0.00),
    ("blocking", "code_evals.categories_valid", "min", 1.00, 0.00),
    # WARN — quality. Regression opens a ticket, does not block.
    ("warn", "extraction.recall", "min", 0.55, 0.05),
    ("warn", "extraction.precision", "min", 0.75, 0.05),
    ("warn", "extraction.category_accuracy", "min", 0.75, 0.05),
    ("warn", "code_evals.not_msl_activity", "min", 0.85, 0.05),
]


def get(rep, path: str):
    obj = rep.to_json()
    for part in path.split("."):
        obj = obj[part]
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--split", default="test")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    rep = evaluate_run(args.run, args.split)
    base = evaluate_run(args.baseline, args.split) if args.baseline else None

    failures, warnings, rows = [], [], []
    for tier, path, direction, floor, tolerance in GATES:
        val = get(rep, path)
        line = {"tier": tier, "metric": path, "value": round(val, 4), "floor": floor}
        bad = val < floor
        why = f"below floor {floor}"
        if base is not None:
            bval = get(base, path)
            line["baseline"] = round(bval, 4)
            line["delta"] = round(val - bval, 4)
            if bval - val > tolerance:
                bad = True
                why = f"regressed {bval - val:.3f} vs baseline (tolerance {tolerance})"
        line["ok"] = not bad
        if bad:
            line["why"] = why
            (failures if tier == "blocking" else warnings).append(line)
        rows.append(line)

    for r in rows:
        mark = "PASS" if r["ok"] else ("FAIL" if r["tier"] == "blocking" else "WARN")
        extra = f"  (baseline {r['baseline']}, delta {r['delta']:+.3f})" if "baseline" in r else ""
        print(f"[{mark}] {r['metric']:44s} {r['value']:.4f}{extra}"
              + (f"  <- {r['why']}" if not r["ok"] else ""))

    if rep.blocking_failures:
        print(f"\n{len(rep.blocking_failures)} per-note blocking check failures:")
        for f in rep.blocking_failures[:10]:
            print(f"  {f}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            {"rows": rows, "blocking_failures": rep.blocking_failures}, indent=2))

    if failures:
        print(f"\nBLOCKED: {len(failures)} blocking gate(s) failed.")
        sys.exit(1)
    if warnings:
        print(f"\nPASSED WITH WARNINGS: {len(warnings)} quality regression(s). "
              f"Open a ticket; do not block.")
        sys.exit(0)
    print("\nAll gates passed.")


if __name__ == "__main__":
    main()
