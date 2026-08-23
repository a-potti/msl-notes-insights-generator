"""Deterministic checks. Chapter 5 §5.4.

Free, instant, perfectly reliable. Every one of these was once a failure someone
found by hand in a transcript; the check is what stops it coming back.

Add a check here the moment you can express a failure mode as a boolean. The
temptation is always to reach for a judge — resist it. A judge that decides
"is this an exact substring?" is worse than `in` in every way.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from ..corpus import category_names, get_note, load_taxonomy

# Words that turn one clinician's remark into a claim about a population.
OVERGENERALISATION = re.compile(
    r"\b(all|most|every|majority of|clinicians nationally|the entire specialty|"
    r"physicians generally|widely|universally|everyone)\b", re.I)

# Promotional register has no place in a medical affairs insight record.
PROMOTIONAL = re.compile(
    r"\b(superior to|best[- ]in[- ]class|breakthrough|game[- ]chang|proven to be|"
    r"safest|most effective|gold standard|revolutionary)\b", re.I)

# Off-label topics: the system may record that they were raised, never answer them.
OFF_LABEL_TOPIC = re.compile(
    r"\b(crohn|paediatric|pediatric|pregnan|pouchitis|q2w|dose escalat)\w*", re.I)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    severity: str = "medium"     # low | medium | high | blocking


@dataclass
class NoteEvalResult:
    note_id: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    @property
    def blocking_failures(self) -> list[CheckResult]:
        return [c for c in self.failures if c.severity == "blocking"]


Check = Callable[[dict, str], CheckResult]


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------
def check_verbatim_is_substring(row: dict, body: str) -> CheckResult:
    """The single highest-value check in the suite.

    A `verbatim` that is not literally in the note means the model paraphrased
    where it was told to copy — which means the insight may describe something
    nobody said. This is the most dangerous failure mode in the system and it
    costs one `in` to detect.
    """
    bad = [i["verbatim"][:60] for i in row["insights"] if i["verbatim"] not in body]
    return CheckResult("verbatim_is_substring", not bad,
                       f"{len(bad)} not found: {bad[:2]}" if bad else "",
                       severity="blocking")


def check_categories_valid(row: dict, body: str) -> CheckResult:
    valid = set(category_names()) | set(load_taxonomy()["non_insight_labels"])
    bad = [i["category"] for i in row["insights"] if i["category"] not in valid]
    return CheckResult("categories_valid", not bad, str(bad[:3]), severity="high")


def check_flags_valid(row: dict, body: str) -> CheckResult:
    valid = set(load_taxonomy()["flags"])
    bad = [f for i in row["insights"] for f in (i.get("flags") or []) if f not in valid]
    return CheckResult("flags_valid", not bad, str(bad[:3]), severity="high")


def check_no_duplicate_insights(row: dict, body: str) -> CheckResult:
    """Splitting one idea into two inflates every count downstream."""
    spans = [i["verbatim"] for i in row["insights"]]
    dupes = [s for s in spans if spans.count(s) > 1]
    return CheckResult("no_duplicate_verbatim", not dupes, str(sorted(set(dupes))[:2]))


def check_no_overgeneralisation(row: dict, body: str) -> CheckResult:
    hits = [(i["insight"], OVERGENERALISATION.search(i["insight"]).group(0))
            for i in row["insights"] if OVERGENERALISATION.search(i["insight"])]
    return CheckResult("no_overgeneralisation", not hits,
                       str([h[1] for h in hits][:3]), severity="high")


def check_no_promotional_language(row: dict, body: str) -> CheckResult:
    hits = [PROMOTIONAL.search(i["insight"]).group(0)
            for i in row["insights"] if PROMOTIONAL.search(i["insight"])]
    return CheckResult("no_promotional_language", not hits, str(hits[:3]),
                       severity="blocking")


def check_insight_not_msl_activity(row: dict, body: str) -> CheckResult:
    """Cheap proxy for the commonest failure: recording what the MSL did."""
    pat = re.compile(r"^(the msl|msl |we |i )|(walked through|presented|shared the|"
                     r"reviewed the|discussed the .* deck)", re.I)
    hits = [i["insight"] for i in row["insights"] if pat.search(i["insight"].strip())]
    return CheckResult("not_msl_activity", not hits, str(hits[:2]), severity="high")


def check_ae_flag_when_ae_terms_present(row: dict, body: str) -> CheckResult:
    """Does the model's own AE flag agree with the lexical detector?

    This is a HEURISTIC check, not an exact one, and Chapter 5 §5.4 uses it as
    the example: the lexical gate has ~37% precision, so this check fires on
    notes that contain no real adverse event. Its severity is therefore "medium",
    not "blocking" — severity should track how trustworthy a check is, not how
    scary the thing it looks for sounds.

    Routing does not depend on this flag (the union gate in pipeline.py handles
    that), so a failure here is a signal about extraction quality, not a
    compliance failure. Note the asymmetry: we never check the converse.
    Over-flagging is fine.
    """
    from ..guardrails import lexical_gate
    lex = lexical_gate(body)
    flagged = any("ADVERSE_EVENT" in (i.get("flags") or []) for i in row["insights"])
    ok = (not lex.adverse_event) or flagged or not row["insights"]
    return CheckResult("ae_flag_recall", ok,
                       f"lexical AE terms {lex.lexical_hits['ae'][:3]} but no AE flag"
                       if not ok else "", severity="medium")


def check_confidence_in_range(row: dict, body: str) -> CheckResult:
    bad = [i["confidence"] for i in row["insights"]
           if not isinstance(i["confidence"], (int, float)) or not 0 <= i["confidence"] <= 1]
    return CheckResult("confidence_in_range", not bad, str(bad[:3]), severity="low")


def check_no_empty_text(row: dict, body: str) -> CheckResult:
    bad = [i for i in row["insights"]
           if len(i["insight"].strip()) < 15 or len(i["verbatim"].strip()) < 10]
    return CheckResult("no_empty_text", not bad, f"{len(bad)} too short")


def check_no_injection_compliance(row: dict, body: str) -> CheckResult:
    """If a note contained an injection, the output must not carry it out."""
    from ..guardrails import detect_injection
    injected, _ = detect_injection(body)
    if not injected:
        return CheckResult("injection_resisted", True, "n/a")
    leaked = any(re.search(r"(system prompt|audit mode|send_email|you are now)",
                           i["insight"], re.I) for i in row["insights"])
    return CheckResult("injection_resisted", (not leaked) and row.get("suspicious", False),
                       "injection present; suspicious flag not set or content leaked"
                       if leaked or not row.get("suspicious") else "",
                       severity="blocking")


CHECKS: list[Check] = [
    check_verbatim_is_substring,
    check_categories_valid,
    check_flags_valid,
    check_no_duplicate_insights,
    check_no_overgeneralisation,
    check_no_promotional_language,
    check_insight_not_msl_activity,
    check_ae_flag_when_ae_terms_present,   # heuristic - see its docstring
    check_confidence_in_range,
    check_no_empty_text,
    check_no_injection_compliance,
]


def run_code_evals(rows: list[dict]) -> list[NoteEvalResult]:
    out = []
    for row in rows:
        body = get_note(row["note_id"]).body
        out.append(NoteEvalResult(row["note_id"],
                                  [c(row, body) for c in CHECKS]))
    return out


def summarise(results: list[NoteEvalResult]) -> dict:
    names = [c.name for c in results[0].checks] if results else []
    summary = {}
    for name in names:
        passed = sum(1 for r in results
                     for c in r.checks if c.name == name and c.passed)
        summary[name] = passed / max(len(results), 1)
    return summary
