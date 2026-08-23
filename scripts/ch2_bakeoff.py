#!/usr/bin/env python3
"""Chapter 2 §2.9 — classical text classification vs an LLM with zero training data.

    python scripts/ch2_bakeoff.py --n 150

Run the classical rows first (free, instant), look at the 1.00 macro-F1, find out
why it is a lie, and only then spend money on the LLM row.
"""
import argparse
import json
import time

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import (StratifiedGroupKFold, StratifiedKFold,
                                     cross_val_score)
from sklearn.pipeline import make_pipeline

from insighthub import llm
from insighthub.config import MODEL_FAST, MODEL_WORK, ML_DIR
from insighthub.corpus import category_names, load_taxonomy, taxonomy_prompt_block

LABELS = None  # filled at runtime


def classical(d: pd.DataFrame) -> None:
    pipe = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
        LogisticRegression(max_iter=2000, C=5),
    )
    naive = cross_val_score(
        pipe, d.text, d.label,
        cv=StratifiedKFold(5, shuffle=True, random_state=0), scoring="f1_macro")
    by_variant = cross_val_score(
        pipe, d.text, d.label,
        cv=StratifiedGroupKFold(5, shuffle=True, random_state=0),
        groups=d.variant_group, scoring="f1_macro")
    by_topic = cross_val_score(
        pipe, d.text, d.label,
        cv=StratifiedGroupKFold(3, shuffle=True, random_state=0),
        groups=d.topic_group, scoring="f1_macro")
    print(f"TF-IDF + LogReg, naive StratifiedKFold : {naive.mean():.3f}   <- too good")
    print(f"TF-IDF + LogReg, grouped by variant    : {by_variant.mean():.3f}")
    print(f"TF-IDF + LogReg, grouped by topic      : {by_topic.mean():.3f}")


def embeddings_row(d: pd.DataFrame) -> None:
    """Fill in the middle row of the table. Needs Chapter 3's embedder."""
    try:
        from insighthub.embed import embed_texts
        X = embed_texts(d.text.tolist())
    except Exception as exc:
        print(f"embeddings row skipped ({type(exc).__name__}: {exc}) "
              f"— come back after Chapter 3")
        return
    clf = LogisticRegression(max_iter=3000, C=10)
    by_variant = cross_val_score(
        clf, X, d.label, cv=StratifiedGroupKFold(5, shuffle=True, random_state=0),
        groups=d.variant_group, scoring="f1_macro")
    by_topic = cross_val_score(
        clf, X, d.label, cv=StratifiedGroupKFold(3, shuffle=True, random_state=0),
        groups=d.topic_group, scoring="f1_macro")
    print(f"Embeddings + LogReg, grouped by variant: {by_variant.mean():.3f}")
    print(f"Embeddings + LogReg, grouped by topic  : {by_topic.mean():.3f}")


CLASSIFY_TOOL = {
    "name": "assign_category",
    "description": "Assign the single best category to the insight text.",
    "input_schema": {
        "type": "object",
        "properties": {"category": {"type": "string"}},
        "required": ["category"],
    },
    "strict": True,
}


def llm_row(d: pd.DataFrame, model: str, n: int) -> None:
    labels = sorted(d.label.unique())
    tool = json.loads(json.dumps(CLASSIFY_TOOL))
    tool["input_schema"]["properties"]["category"]["enum"] = labels

    sample = d.sample(n, random_state=0)
    system = [{
        "type": "text",
        "text": ("Assign each insight sentence from a pharma field-medical call note to "
                 "exactly one category.\n\n" + taxonomy_prompt_block()),
        "cache_control": {"type": "ephemeral"},
    }]

    preds, cost, lats = [], 0.0, []
    for text in sample.text:
        t0 = time.perf_counter()
        r = llm.call(model=model, max_tokens=256, temperature=0.0, system=system,
                     tools=[tool], tool_choice={"type": "tool", "name": "assign_category"},
                     messages=[{"role": "user", "content": f"Sentence:\n{text}"}])
        lats.append(time.perf_counter() - t0)
        cost += r.cost_usd
        uses = r.tool_uses()
        preds.append(uses[0].input["category"] if uses else "SUMMARY_NO_INSIGHT")

    f1 = f1_score(sample.label, preds, average="macro", zero_division=0)
    print(f"LLM zero-shot ({model[:22]:22s}): macro-F1 {f1:.3f}  "
          f"${cost/n*1000:.2f}/1k  p50 {np.median(lats):.2f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150, help="LLM sample size")
    ap.add_argument("--skip-llm", action="store_true")
    args = ap.parse_args()

    d = pd.read_csv(ML_DIR / "insight_text_archive.csv")
    print(f"{len(d)} labelled sentences, {d.label.nunique()} classes, "
          f"{d.variant_group.nunique()} variant groups, {d.topic_group.nunique()} topics\n")
    classical(d)
    embeddings_row(d)
    if not args.skip_llm:
        print()
        llm_row(d, MODEL_FAST, args.n)
        llm_row(d, MODEL_WORK, args.n)

    print("\nNow write the crossover rule in DECISIONS.md: at what number of labelled")
    print("examples per class would you switch back to the classical model?")


if __name__ == "__main__":
    main()
