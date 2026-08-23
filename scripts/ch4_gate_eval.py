#!/usr/bin/env python3
"""Chapter 4 §4.8 — how good is the compliance gate?

The lexical half is free to evaluate, so start there and understand it before
spending money on the model half.

    python scripts/ch4_gate_eval.py              # lexical only, free
    python scripts/ch4_gate_eval.py --with-model # adds the LLM detector (~$0.15)
"""
import argparse

from insighthub.corpus import load_gold, load_notes
from insighthub.guardrails import combined_gate, detect_injection, lexical_gate


def score(name: str, preds: dict[str, bool], truth: dict[str, bool]) -> None:
    tp = sum(1 for k in preds if preds[k] and truth[k])
    fp = sum(1 for k in preds if preds[k] and not truth[k])
    fn = sum(1 for k in preds if not preds[k] and truth[k])
    tn = sum(1 for k in preds if not preds[k] and not truth[k])
    rec = tp / max(tp + fn, 1)
    prec = tp / max(tp + fp, 1)
    print(f"{name:24s} tp={tp:3d} fp={fp:3d} fn={fn:3d} tn={tn:3d}  "
          f"recall={rec:.3f}  precision={prec:.3f}")
    if fn:
        misses = [k for k in preds if not preds[k] and truth[k]]
        print(f"{'':24s} MISSED: {', '.join(misses)}  <- read these notes")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-model", action="store_true")
    ap.add_argument("--split", default=None)
    args = ap.parse_args()

    notes = [n for n in load_notes() if args.split is None or n.split == args.split]
    gold = {g["note_id"]: g for g in load_gold()}
    truth = {n.note_id: "ADVERSE_EVENT" in gold[n.note_id]["flags"] for n in notes}

    lex = {n.note_id: lexical_gate(n.body).adverse_event for n in notes}
    score("lexical AE gate", lex, truth)

    if args.with_model:
        comb = {n.note_id: combined_gate(n.body).adverse_event for n in notes}
        score("lexical UNION model", comb, truth)

    print("\nPrecision is allowed to be poor here and recall is not. If you are tempted")
    print("to tighten the term list, re-read Chapter 4 §4.8 first.")

    inj_pred = {n.note_id for n in notes if detect_injection(n.body)[0]}
    inj_true = {n.note_id for n in notes if gold[n.note_id]["contains_injection"]}
    print(f"\ninjection: predicted={sorted(inj_pred)} truth={sorted(inj_true)}")


if __name__ == "__main__":
    main()
