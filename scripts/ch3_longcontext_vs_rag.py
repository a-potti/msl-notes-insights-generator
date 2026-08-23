#!/usr/bin/env python3
"""Chapter 3 §3.11 — is retrieval actually better than sending everything?

Our whole note corpus is ~16k tokens. It fits. So measure the alternative
instead of assuming the pattern.

    python scripts/ch3_longcontext_vs_rag.py --n 10

Costs roughly $0.60 for 10 questions across 3 conditions.
"""
import argparse
import json
import statistics

from insighthub import llm
from insighthub.config import MODEL_WORK
from insighthub.corpus import load_notes
from insighthub.index import notes_index
from insighthub.retrieval_eval import load_queries

ANSWER_SYSTEM = """You answer questions for a pharmaceutical medical affairs team using
ONLY the field call notes provided. Rules:
- Every claim must be supported by a note you were given. Cite note IDs in brackets.
- If the notes do not support an answer, say so. Do not use outside knowledge.
- Report how many distinct notes support each point — the team needs to know whether
  something is one person's view or a pattern."""

JUDGE_TOOL = {
    "name": "score_answer",
    "description": "Score an answer against the notes that were available.",
    "input_schema": {
        "type": "object",
        "properties": {
            "grounded": {"type": "integer", "minimum": 1, "maximum": 5,
                         "description": "5 = every claim traceable to a cited note; "
                                        "1 = substantial unsupported content."},
            "complete": {"type": "integer", "minimum": 1, "maximum": 5,
                         "description": "5 = covers the relevant material; "
                                        "1 = misses most of it."},
            "rationale": {"type": "string"},
        },
        "required": ["grounded", "complete", "rationale"],
    },
    "strict": True,
}


def answer(question: str, notes_block: str) -> llm.LLMResult:
    return llm.call(
        model=MODEL_WORK, max_tokens=1200, temperature=0.0,
        system=[{"type": "text", "text": ANSWER_SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user",
                   "content": f"<notes>\n{notes_block}\n</notes>\n\n"
                              f"Question: {question}"}],
    )


def judge(question: str, ans: str, gold_notes: str) -> dict:
    r = llm.call(
        model="claude-opus-5", max_tokens=800, temperature=0.0,
        tools=[JUDGE_TOOL], tool_choice={"type": "tool", "name": "score_answer"},
        messages=[{"role": "user", "content":
                   f"Question: {question}\n\nAnswer under review:\n{ans}\n\n"
                   f"The notes that are actually relevant:\n{gold_notes}"}],
    )
    uses = r.tool_uses()
    return uses[0].input if uses else {"grounded": 0, "complete": 0, "rationale": "no tool"}


def block(notes) -> str:
    return "\n\n".join(f"[{n.note_id}] {n.body}" for n in notes)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()

    all_notes = load_notes()
    by_id = {n.note_id: n for n in all_notes}
    ix = notes_index().build()
    queries = load_queries()[: args.n]

    conditions = {
        "all-140-notes": lambda q: all_notes,
        "hybrid-k10": lambda q: [by_id[h.doc.doc_id] for h in ix.hybrid_search(q, 10)],
        "hybrid-k30": lambda q: [by_id[h.doc.doc_id] for h in ix.hybrid_search(q, 30)],
    }

    results: dict[str, list] = {c: [] for c in conditions}
    for q in queries:
        gold = block([by_id[i] for i in q["relevant_note_ids"][:15]])
        for cname, select in conditions.items():
            notes = select(q["query"])
            res = answer(q["query"], block(notes))
            scores = judge(q["query"], res.text, gold)
            results[cname].append({
                "query_id": q["query_id"], "tokens": res.total_input,
                "cost": res.cost_usd, "latency": res.latency_s,
                "grounded": scores["grounded"], "complete": scores["complete"],
            })
            print(f"  {q['query_id']} {cname:16s} in={res.total_input:6,d} "
                  f"g={scores['grounded']} c={scores['complete']}")

    print(f"\n{'condition':18s} {'tok/q':>8s} {'$/q':>9s} {'p50 lat':>8s} "
          f"{'grounded':>9s} {'complete':>9s}")
    for cname, rows in results.items():
        print(f"{cname:18s} {statistics.mean(r['tokens'] for r in rows):8,.0f} "
              f"${statistics.mean(r['cost'] for r in rows):8.4f} "
              f"{statistics.median(r['latency'] for r in rows):7.2f}s "
              f"{statistics.mean(r['grounded'] for r in rows):9.2f} "
              f"{statistics.mean(r['complete'] for r in rows):9.2f}")

    with open("runs/ch3_longcontext_vs_rag.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nIf long-context wins on quality, say so in DECISIONS.md and justify")
    print("retrieval on cost and growth instead. Do not launder the result.")


if __name__ == "__main__":
    main()
