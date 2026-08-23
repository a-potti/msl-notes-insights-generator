"""Paths, model routing and environment checks. Provided for you — no TODOs here."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
NOTES_DIR = DATA / "call_notes"
CONGRESS_DIR = DATA / "congress"
PUBS_DIR = DATA / "publications"
KOL_DIR = DATA / "kols"
EVAL_DIR = DATA / "eval"
ML_DIR = DATA / "ml"
RAW_DIR = DATA / "raw"
TAXONOMY_PATH = DATA / "taxonomy" / "insight_taxonomy.yaml"
FACT_BASE_PATH = DATA / "product" / "veltraxa_fact_base.md"

INDEX_DIR = ROOT / "index"
RUNS_DIR = ROOT / "runs"
TRACE_DIR = Path(os.getenv("INSIGHTHUB_TRACE_DIR", ROOT / "traces"))

# Three tiers, deliberately. Chapter 1 §1.7 explains the routing policy;
# Chapter 6 §6.7 measures what it saves.
MODEL_FAST = os.getenv("MODEL_FAST", "claude-haiku-4-5-20251001")
MODEL_WORK = os.getenv("MODEL_WORK", "claude-sonnet-5")
MODEL_DEEP = os.getenv("MODEL_DEEP", "claude-opus-5")

# USD per million tokens. Check the pricing page before trusting these in a
# budget conversation — they move.
PRICING = {
    "claude-haiku-4-5-20251001": {"in": 1.00, "out": 5.00},
    "claude-sonnet-5": {"in": 2.00, "out": 10.00},
    "claude-opus-5": {"in": 5.00, "out": 25.00},
}
# Cached input reads are billed at a fraction of the base input rate, and cache
# writes at a premium. Chapter 1 measures the real numbers from your own usage
# fields rather than trusting a constant here.


def cost_usd(model: str, in_tokens: int, out_tokens: int,
             cache_read: int = 0, cache_write: int = 0) -> float:
    """Rough cost estimate. Cache reads ~0.1x input, 5m cache writes ~1.25x input."""
    p = PRICING.get(model)
    if p is None:
        return float("nan")
    return (
        in_tokens * p["in"]
        + cache_read * p["in"] * 0.10
        + cache_write * p["in"] * 1.25
        + out_tokens * p["out"]
    ) / 1_000_000


def check() -> None:
    """Fail loudly and usefully if the environment is not ready."""
    problems = []
    if not os.getenv("ANTHROPIC_API_KEY"):
        problems.append("ANTHROPIC_API_KEY is not set (copy .env.example to .env)")
    if not NOTES_DIR.exists() or not any(NOTES_DIR.glob("NOTE-*.txt")):
        problems.append("data/call_notes is empty — run scripts/gen/generate.py")
    if not TAXONOMY_PATH.exists():
        problems.append("taxonomy missing — run scripts/gen/generate.py")
    try:
        import anthropic  # noqa: F401
    except ImportError:
        problems.append("anthropic not installed — pip install -r requirements.txt")

    if problems:
        raise SystemExit("Setup problems:\n  - " + "\n  - ".join(problems))
    n = len(list(NOTES_DIR.glob("NOTE-*.txt")))
    print(f"OK. {n} call notes, models: {MODEL_FAST} / {MODEL_WORK} / {MODEL_DEEP}")
