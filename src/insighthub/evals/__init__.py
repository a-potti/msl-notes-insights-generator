"""Evaluation suite. Chapter 5.

Three layers, cheapest first — and that ordering is the whole methodology:

  code_evals  deterministic, free, instant. Run on every example, every time.
  matching    align predicted insights to labelled ones so recall/precision exist.
  judge       an LLM judge for the fuzzy criteria, VALIDATED against human labels
              before you are allowed to believe it.

If a check can be code, it must be code. An LLM judge for something a substring
test could decide is slower, more expensive, and less correct.
"""
from .code_evals import CHECKS, run_code_evals            # noqa: F401
from .matching import match_insights                      # noqa: F401
