"""LLM-as-judge, and — the part everyone skips — validating the judge.

Chapter 5 §5.6-§5.7.

An unvalidated judge is a random number generator with good manners. Before you
let a judge's output influence a decision you must know its true-positive and
true-negative rate against human labels, and you must correct its reported pass
rate for those rates.

`data/eval/judge_calibration.jsonl` holds 60 human-labelled examples for exactly
this. It deliberately contains near-misses that a naive judge prompt gets wrong.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from statistics import mean

import numpy as np

from .. import llm
from ..config import EVAL_DIR, MODEL_DEEP
from ..corpus import load_jsonl, taxonomy_prompt_block

# ---------------------------------------------------------------------------
# v1 — the prompt everybody writes first. It will not agree with you.
# ---------------------------------------------------------------------------
JUDGE_V1 = """You evaluate insights extracted from pharmaceutical field medical call
notes. Decide whether each extracted insight is a good insight. Answer PASS or FAIL."""

# ---------------------------------------------------------------------------
# v2 — after error analysis on where v1 disagreed with the human labels.
# Three changes, each traceable to a specific disagreement:
#   * an explicit definition, because "good" was doing all the work
#   * the four named failure modes, because those are the ones humans FAIL on
#   * "judge only what is in front of you", because v1 kept inventing context
# ---------------------------------------------------------------------------
JUDGE_V2 = """You are the quality reviewer for a pharmaceutical Medical Affairs insight
database. You decide whether a single extracted insight should be accepted.

## Accept if ALL of these hold
1. It reports something the HEALTHCARE PROFESSIONAL contributed — an observation,
   question, concern or behaviour — not something the MSL did or presented.
2. It is faithful to the source: no claim beyond what the note supports.
3. It does not generalise one interaction into a statement about a population.
   "He finds onset slower" is fine. "Clinicians nationally find onset slower" is not.
4. The assigned category is the best fit in the taxonomy below.

## Reject if ANY of these hold
- ACTIVITY: describes what the MSL presented, shared or reviewed.
- OVERGENERALISED: extends one clinician's view to prescribers, the specialty, or
  "most" of anyone.
- UNSUPPORTED: adds a claim, number, or causal link the note does not contain.
- MISCATEGORISED: the content is fine but the category is wrong.

## How to judge
Judge only what is in front of you. Do not imagine surrounding context that would make a
borderline case acceptable. If you would need to assume something to accept it, reject it.

Return exactly one failure_mode when rejecting.

""" + taxonomy_prompt_block()


JUDGE_TOOL = {
    "name": "judge_insight",
    "description": "Accept or reject one extracted insight.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
            "failure_mode": {"type": "string",
                             "enum": ["NONE", "ACTIVITY", "OVERGENERALISED",
                                      "UNSUPPORTED", "MISCATEGORISED"]},
            "rationale": {"type": "string", "description": "One sentence."},
        },
        "required": ["verdict", "failure_mode", "rationale"],
    },
    "strict": True,
}


@dataclass
class Verdict:
    verdict: str
    failure_mode: str
    rationale: str
    cost_usd: float = 0.0


def judge_one(candidate: str, assigned_category: str, *, source_note: str = "",
              system: str = JUDGE_V2, model: str = MODEL_DEEP) -> Verdict:
    user = (f"Extracted insight: {candidate}\n"
            f"Assigned category: {assigned_category}\n")
    if source_note:
        user += f"\nSource note:\n<note>\n{source_note}\n</note>"
    res = llm.call(
        model=model, max_tokens=512, temperature=0.0,
        system=[{"type": "text", "text": system,
                 "cache_control": {"type": "ephemeral"}}],
        tools=[JUDGE_TOOL], tool_choice={"type": "tool", "name": "judge_insight"},
        messages=[{"role": "user", "content": user}],
        meta={"step": "judge"},
    )
    uses = res.tool_uses()
    if not uses:
        return Verdict("FAIL", "NONE", "judge produced no verdict", res.cost_usd)
    p = uses[0].input
    return Verdict(p["verdict"], p["failure_mode"], p["rationale"], res.cost_usd)


# ---------------------------------------------------------------------------
# Validating the judge
# ---------------------------------------------------------------------------
@dataclass
class JudgeValidation:
    n: int
    tpr: float          # P(judge says PASS | human says PASS)
    tnr: float          # P(judge says FAIL | human says FAIL)
    accuracy: float
    kappa: float
    cost_usd: float
    disagreements: list[dict]

    def __str__(self) -> str:
        return (f"n={self.n} accuracy={self.accuracy:.3f} TPR={self.tpr:.3f} "
                f"TNR={self.tnr:.3f} kappa={self.kappa:.3f} ${self.cost_usd:.3f}")

    def usable(self) -> bool:
        """A judge below these thresholds should not gate anything. The numbers
        are a judgement call — but having a documented bar at all puts you ahead
        of most teams."""
        return self.kappa >= 0.6 and self.tpr >= 0.8 and self.tnr >= 0.8


def cohens_kappa(a: list[str], b: list[str]) -> float:
    """Agreement corrected for chance. Raw agreement on a 70/30 split can be 70%
    from coin-flipping alone; kappa tells you how much of the agreement is real.
    Rough reading: <0.4 poor, 0.4-0.6 moderate, 0.6-0.8 substantial, >0.8 strong."""
    labels = sorted(set(a) | set(b))
    idx = {l: i for i, l in enumerate(labels)}
    n = len(a)
    m = np.zeros((len(labels), len(labels)))
    for x, y in zip(a, b):
        m[idx[x], idx[y]] += 1
    po = np.trace(m) / n
    pe = float((m.sum(0) @ m.sum(1)) / (n * n))
    return float((po - pe) / (1 - pe)) if pe < 1 else 1.0


def load_calibration() -> list[dict]:
    return load_jsonl(EVAL_DIR / "judge_calibration.jsonl")


def validate_judge(system: str = JUDGE_V2, *, model: str = MODEL_DEEP,
                   n: int | None = None, max_workers: int = 6) -> JudgeValidation:
    from concurrent.futures import ThreadPoolExecutor

    rows = load_calibration()[:n]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        verdicts = list(pool.map(
            lambda r: judge_one(r["candidate_insight"], r["assigned_category"],
                                system=system, model=model), rows))

    human = [r["human_label"] for r in rows]
    machine = [v.verdict for v in verdicts]
    tp = sum(1 for h, m in zip(human, machine) if h == "PASS" and m == "PASS")
    fn = sum(1 for h, m in zip(human, machine) if h == "PASS" and m == "FAIL")
    tn = sum(1 for h, m in zip(human, machine) if h == "FAIL" and m == "FAIL")
    fp = sum(1 for h, m in zip(human, machine) if h == "FAIL" and m == "PASS")

    dis = [{"example_id": r["example_id"], "human": r["human_label"],
            "judge": v.verdict, "human_why": r["human_rationale"],
            "judge_why": v.rationale, "candidate": r["candidate_insight"][:120]}
           for r, v in zip(rows, verdicts) if r["human_label"] != v.verdict]

    return JudgeValidation(
        n=len(rows),
        tpr=tp / max(tp + fn, 1),
        tnr=tn / max(tn + fp, 1),
        accuracy=(tp + tn) / max(len(rows), 1),
        kappa=cohens_kappa(human, machine),
        cost_usd=sum(v.cost_usd for v in verdicts),
        disagreements=dis,
    )


def correct_pass_rate(observed: float, tpr: float, tnr: float) -> float:
    """Recover the true pass rate from a judge with known error rates.

        observed = true·TPR + (1-true)·(1-TNR)
      => true = (observed - (1-TNR)) / (TPR + TNR - 1)

    If your judge has TPR 0.85 and TNR 0.80 and reports 70% passing, the true
    rate is about 77%. Reporting the uncorrected 70% is reporting your judge's
    bias as if it were your system's quality.
    """
    denom = tpr + tnr - 1
    if abs(denom) < 1e-6:
        return float("nan")
    return float(np.clip((observed - (1 - tnr)) / denom, 0.0, 1.0))
