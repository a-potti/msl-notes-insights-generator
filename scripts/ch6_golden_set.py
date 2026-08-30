#!/usr/bin/env python3
"""Chapter 6 §6.9 Exercise 2 — a golden set for model-drift detection.

    python scripts/ch6_golden_set.py --store   # run the 20 fixed notes, save as golden
    python scripts/ch6_golden_set.py --check   # rerun today, diff against golden

Run --check once a day. The day-to-day similarity you see when NOTHING has
changed is your detection floor — a real drift alert only means something if
it clears that floor, not just any nonzero diff.
"""
import argparse
import json
import statistics

from insighthub.config import MODEL_WORK, RUNS_DIR
from insighthub.corpus import notes_by_split
from insighthub.embed import embed_texts
from insighthub.extract import extract_many, save
from insighthub.observability import population_stability_index

GOLDEN_PATH = RUNS_DIR / "ch6_golden_set.jsonl"
GOLDEN_NOTE_IDS = [n.note_id for n in notes_by_split("holdout")[:20]]


def run_golden_set():
    notes = [n for n in notes_by_split("holdout") if n.note_id in GOLDEN_NOTE_IDS]
    exs = extract_many(notes, model=MODEL_WORK, temperature=0.0)
    return exs


def diff_against(golden_rows: list[dict], today_rows: list[dict]) -> dict:
    g_by_note = {r["note_id"]: r for r in golden_rows}
    sims = []
    cat_matches = 0
    cat_total = 0
    count_deltas = []
    for row in today_rows:
        g = g_by_note.get(row["note_id"])
        if not g:
            continue
        g_texts = [i["insight"] for i in g["insights"]]
        t_texts = [i["insight"] for i in row["insights"]]
        count_deltas.append(len(t_texts) - len(g_texts))
        if not g_texts or not t_texts:
            continue
        G = embed_texts(g_texts)
        T = embed_texts(t_texts)
        sim = T @ G.T
        # greedy best-match similarity per predicted insight against golden
        for ti in range(len(t_texts)):
            best_g = int(sim[ti].argmax())
            sims.append(float(sim[ti, best_g]))
            cat_total += 1
            if row["insights"][ti]["category"] == g["insights"][best_g]["category"]:
                cat_matches += 1

    g_cats = [i["category"] for r in golden_rows for i in r["insights"]]
    t_cats = [i["category"] for r in today_rows for i in r["insights"]]
    return {
        "n_notes": len(today_rows),
        "mean_similarity": round(statistics.mean(sims), 4) if sims else None,
        "min_similarity": round(min(sims), 4) if sims else None,
        "category_agreement": round(cat_matches / max(cat_total, 1), 4),
        "category_psi": round(population_stability_index(g_cats, t_cats), 4),
        "mean_count_delta": round(statistics.mean(count_deltas), 3) if count_deltas else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.store:
        exs = run_golden_set()
        save(exs, GOLDEN_PATH)
        print(f"stored {len(exs)} golden notes -> {GOLDEN_PATH}")
        return

    if args.check:
        if not GOLDEN_PATH.exists():
            raise SystemExit("no golden set stored yet — run --store first")
        golden_rows = [json.loads(l) for l in open(GOLDEN_PATH)]
        exs = run_golden_set()
        # Save today's run to a temp path then reload as plain dicts, matching
        # the on-disk record shape golden_rows already uses.
        tmp_path = RUNS_DIR / "_ch6_golden_today.jsonl"
        save(exs, tmp_path)
        today_rows = [json.loads(l) for l in open(tmp_path)]

        report = diff_against(golden_rows, today_rows)
        print(json.dumps(report, indent=2))
        return

    ap.print_help()


if __name__ == "__main__":
    main()
