"""The eval suite runner. Chapter 5 §5.8.

    python -m insighthub.evals.run --run runs/ch1_dev_v1.jsonl --split dev
    python -m insighthub.evals.run --run runs/ch5_dev_v3.jsonl --compare runs/ch5_dev_v2.jsonl

Design notes:
  * Code evals always run. They are free.
  * Judge evals are opt-in (--judge) because they cost money, and the runner
    refuses to report judge numbers unless the judge has been validated.
  * Every headline number gets a bootstrap confidence interval. A point estimate
    on 60 examples is not a result.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from ..config import RUNS_DIR
from ..corpus import get_note, load_gold
from ..extract import load as load_run
from .code_evals import run_code_evals, summarise
from .matching import corpus_scores, threshold_sensitivity


@dataclass
class EvalReport:
    run_path: str
    split: str
    n_notes: int
    n_insights: int
    code_evals: dict = field(default_factory=dict)
    blocking_failures: list[str] = field(default_factory=list)
    extraction: dict = field(default_factory=dict)
    extraction_ci: dict = field(default_factory=dict)
    threshold_sensitivity: list[dict] = field(default_factory=list)
    judge: dict | None = None

    def to_json(self) -> dict:
        d = asdict(self)
        d["extraction"] = {k: v for k, v in self.extraction.items() if k != "per_note"}
        return d


def bootstrap_metric(per_note, metric: str, n_boot: int = 2000,
                     seed: int = 0) -> tuple[float, float]:
    """Resample NOTES, not insights — insights within a note are correlated, and
    resampling them independently gives you an interval that is too narrow."""
    rng = np.random.default_rng(seed)
    arr = np.array([[m.tp, m.fp, m.fn] for m in per_note], dtype=float)
    vals = []
    for _ in range(n_boot):
        s = arr[rng.integers(0, len(arr), len(arr))].sum(axis=0)
        tp, fp, fn = s
        p = tp / max(tp + fp, 1)
        r = tp / max(tp + fn, 1)
        vals.append({"precision": p, "recall": r,
                     "f1": 2 * p * r / max(p + r, 1e-9)}[metric])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def evaluate_run(run_path: str, split: str | None = None, *, judge: bool = False,
                 judge_n: int = 40) -> EvalReport:
    rows = load_run(run_path)
    gold = {g["note_id"]: g for g in load_gold(split)}
    if split:
        rows = [r for r in rows if r["note_id"] in gold]

    rep = EvalReport(run_path=str(run_path), split=split or "all", n_notes=len(rows),
                     n_insights=sum(len(r["insights"]) for r in rows))

    # --- layer 1: code evals (free) --------------------------------------
    results = run_code_evals(rows)
    rep.code_evals = summarise(results)
    rep.blocking_failures = [
        f"{r.note_id}:{c.name}" for r in results for c in r.blocking_failures]

    # --- layer 2: matching against labels --------------------------------
    scores = corpus_scores(rows, gold)
    rep.extraction = scores
    for m in ("precision", "recall", "f1"):
        lo, hi = bootstrap_metric(scores["per_note"], m)
        rep.extraction_ci[m] = (round(lo, 3), round(hi, 3))
    rep.threshold_sensitivity = threshold_sensitivity(rows, gold)

    # --- layer 3: judge (opt-in, must be validated) ----------------------
    if judge:
        from .judge import JUDGE_V2, correct_pass_rate, judge_one, validate_judge
        val = validate_judge(JUDGE_V2, n=None)
        if not val.usable():
            rep.judge = {"validated": False, "validation": str(val),
                         "note": "judge below usability bar; numbers withheld"}
        else:
            from concurrent.futures import ThreadPoolExecutor
            items = [(r, i) for r in rows for i in r["insights"]][:judge_n]
            with ThreadPoolExecutor(max_workers=6) as pool:
                verdicts = list(pool.map(
                    lambda ri: judge_one(ri[1]["insight"], ri[1]["category"],
                                         source_note=get_note(ri[0]["note_id"]).body),
                    items))
            observed = sum(v.verdict == "PASS" for v in verdicts) / max(len(verdicts), 1)
            modes: dict[str, int] = {}
            for v in verdicts:
                if v.verdict == "FAIL":
                    modes[v.failure_mode] = modes.get(v.failure_mode, 0) + 1
            rep.judge = {
                "validated": True, "validation": str(val),
                "n_judged": len(verdicts),
                "observed_pass_rate": round(observed, 3),
                "corrected_pass_rate": round(
                    correct_pass_rate(observed, val.tpr, val.tnr), 3),
                "failure_modes": modes,
                "cost_usd": round(sum(v.cost_usd for v in verdicts) + val.cost_usd, 4),
            }
    return rep


def print_report(rep: EvalReport) -> None:
    print(f"\n=== {rep.run_path}  [{rep.split}] ===")
    print(f"{rep.n_notes} notes, {rep.n_insights} insights "
          f"({rep.n_insights / max(rep.n_notes,1):.2f}/note)\n")

    print("code evals (pass rate over notes):")
    for name, rate in sorted(rep.code_evals.items(), key=lambda kv: kv[1]):
        mark = "FAIL" if rate < 1.0 else "ok  "
        print(f"  {mark} {name:32s} {rate:6.1%}")
    if rep.blocking_failures:
        print(f"\n  !! {len(rep.blocking_failures)} BLOCKING failures: "
              f"{rep.blocking_failures[:6]}")

    e, ci = rep.extraction, rep.extraction_ci
    print(f"\nextraction vs labels (match threshold {e['threshold']}):")
    print(f"  tp={e['tp']} fp={e['fp']} fn={e['fn']}")
    print(f"  precision {e['precision']:.3f}  95% CI {ci['precision']}")
    print(f"  recall    {e['recall']:.3f}  95% CI {ci['recall']}")
    print(f"  f1        {e['f1']:.3f}  95% CI {ci['f1']}")
    print(f"  category accuracy (matched pairs only) {e['category_accuracy']:.3f}")

    print("\nmatch-threshold sensitivity:")
    for row in rep.threshold_sensitivity:
        print(f"  t={row['threshold']:.2f}  P={row['precision']:.3f} "
              f"R={row['recall']:.3f} F1={row['f1']:.3f}")

    if rep.judge:
        print("\njudge:")
        for k, v in rep.judge.items():
            print(f"  {k}: {v}")


def compare(a: EvalReport, b: EvalReport) -> None:
    """A vs B. The only honest way to read two runs."""
    print(f"\n=== {Path(a.run_path).name}  vs  {Path(b.run_path).name} ===")
    for m in ("precision", "recall", "f1"):
        da, db = a.extraction[m], b.extraction[m]
        print(f"  {m:10s} {da:.3f} {a.extraction_ci[m]}  ->  "
              f"{db:.3f} {b.extraction_ci[m]}   delta {db-da:+.3f}")
    overlap = any(
        a.extraction_ci[m][0] <= b.extraction[m] <= a.extraction_ci[m][1]
        for m in ("f1",))
    print("\n  " + ("Intervals overlap — this difference is NOT established. "
                    "Label more data or make a bigger change."
                    if overlap else
                    "Intervals do not overlap on F1 — the difference is credible."))
    print("  code eval regressions:")
    for name, rate in a.code_evals.items():
        nb = b.code_evals.get(name, 0.0)
        if nb < rate:
            print(f"    {name}: {rate:.1%} -> {nb:.1%}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--judge-n", type=int, default=40)
    ap.add_argument("--compare", default=None)
    ap.add_argument("--save", default=None)
    args = ap.parse_args()

    rep = evaluate_run(args.run, args.split, judge=args.judge, judge_n=args.judge_n)
    print_report(rep)
    if args.compare:
        base = evaluate_run(args.compare, args.split)
        compare(base, rep)
    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(rep.to_json(), indent=2, default=str))
        print(f"\nsaved {args.save}")


if __name__ == "__main__":
    main()
