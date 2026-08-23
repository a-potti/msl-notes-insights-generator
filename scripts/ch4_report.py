#!/usr/bin/env python3
"""Chapter 4 §4.10 — build the quarterly Field Medical Insight Report.

    python scripts/ch4_report.py --top 6 --run runs/ch4_ingest_dev.jsonl

Fan out one sub-agent per theme, fan in to one writer. Costs ~$1.50 for 6 themes.
"""
import argparse
import json
from pathlib import Path

from insighthub.config import MODEL_DEEP, MODEL_WORK
from insighthub.corpus import get_note
from insighthub.index import evidence_index, notes_index
from insighthub.report import build_report
from insighthub.themes import build_graph, cluster, name_themes
from insighthub.tools import default_registry


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="runs/ch4_ingest_dev.jsonl")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--out", default="runs/quarterly_report.md")
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.run).read_text().splitlines() if l.strip()]
    items = [(f"{r['note_id']}#{i}", ins["insight"])
             for r in rows for i, ins in enumerate(r["insights"])]
    if not items:
        raise SystemExit(f"no insights in {args.run} — run the Chapter 4 §4.2 ingest first")
    ids, texts = zip(*items)
    print(f"{len(items)} insights from {len(rows)} notes")

    themes = cluster(list(texts), list(ids), method="agglom")
    themes = [t for t in themes if t.size >= 2]
    print(f"{len(themes)} themes (sizes: {[t.size for t in themes[:12]]})")
    themes = name_themes(themes[: args.top], model=MODEL_DEEP)

    notes_ix = notes_index().build()
    ev_ix = evidence_index().build()
    registry = default_registry(notes_ix, ev_ix)

    graph = build_graph(themes, {i: get_note(i.split("#")[0]).kol_id for i in ids},
                        evidence_index=ev_ix)
    gaps = graph.unsupported_themes()
    if gaps:
        print(f"themes with no linked evidence: {gaps}")

    report = build_report(themes, registry, top_n=args.top,
                          worker_model=MODEL_WORK, writer_model=MODEL_DEEP)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report.markdown())
    print(f"\nwrote {args.out}  (${report.cost_usd:.3f})")
    print("\nNow read it as a medical director would. Is any number unsupported?")
    print("Is any HCP named? Is any off-label question answered rather than routed?")


if __name__ == "__main__":
    main()
