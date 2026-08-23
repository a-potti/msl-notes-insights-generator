"""Tracing, metrics and drift detection. Chapter 6 §6.1-§6.4.

The whole reason `llm.py` has an observer hook is this file. Turning tracing on
is three lines because we designed for it in Chapter 1; retrofitting it after the
fact means touching every call site, and nobody ever does.

    from insighthub import observability as obs
    obs.start_tracing(run_id="ingest-2026-08-21")
    ...
    print(obs.summary())
"""
from __future__ import annotations

import json
import math
import os
import statistics
import threading
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import llm
from .config import TRACE_DIR

_lock = threading.Lock()
_current: dict = {"run_id": None, "path": None, "records": []}


# ---------------------------------------------------------------------------
# Tracing
# ---------------------------------------------------------------------------
@dataclass
class TraceRecord:
    trace_id: str
    run_id: str
    ts: str
    step: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    latency_s: float
    cost_usd: float
    stop_reason: str | None
    attempts: int
    meta: dict = field(default_factory=dict)


def _observer(result: llm.LLMResult) -> None:
    rec = TraceRecord(
        trace_id=uuid.uuid4().hex[:12],
        run_id=_current["run_id"] or "adhoc",
        ts=datetime.now(timezone.utc).isoformat(),
        step=result.meta.get("step", "unknown"),
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cache_read_tokens=result.cache_read_tokens,
        latency_s=round(result.latency_s, 4),
        cost_usd=round(result.cost_usd, 6),
        stop_reason=result.stop_reason,
        attempts=result.attempts,
        meta={k: v for k, v in result.meta.items() if k != "step"},
    )
    with _lock:
        _current["records"].append(rec)
        path = _current["path"]
    if path:
        with _lock, open(path, "a") as f:
            f.write(json.dumps(asdict(rec)) + "\n")


_installed = False


def start_tracing(run_id: str | None = None, to_disk: bool = True) -> str:
    """Install the trace observer. Idempotent.

    NOTE what is deliberately NOT recorded: prompt and completion text. Call
    notes contain HCP names and clinical detail, and a trace store is a much
    softer target than your primary database. Log identifiers, token counts,
    latency, cost and outcomes; keep the payloads in the system that already has
    the right access controls, and link by ID.
    """
    global _installed
    run_id = run_id or f"run-{int(time.time())}"
    with _lock:
        _current["run_id"] = run_id
        _current["records"] = []
        if to_disk:
            TRACE_DIR.mkdir(parents=True, exist_ok=True)
            _current["path"] = TRACE_DIR / f"{run_id}.jsonl"
        else:
            _current["path"] = None
    if not _installed:
        llm.add_observer(_observer)
        _installed = True
    return run_id


def records() -> list[TraceRecord]:
    with _lock:
        return list(_current["records"])


def load_traces(run_id: str | None = None) -> list[dict]:
    paths = ([TRACE_DIR / f"{run_id}.jsonl"] if run_id
             else sorted(TRACE_DIR.glob("*.jsonl")))
    out = []
    for p in paths:
        if p.exists():
            out += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return out


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return s[int(k)] if lo == hi else s[lo] + (s[hi] - s[lo]) * (k - lo)


def summary(recs: list[dict] | None = None) -> dict:
    """The four numbers you look at first, broken down by step.

    p50 tells you how it feels most of the time. p95 tells you how it feels to
    the person who is about to complain. Report both; a mean hides both.
    """
    rows = recs if recs is not None else [asdict(r) for r in records()]
    if not rows:
        return {"n": 0}
    by_step: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_step[r["step"]].append(r)

    out = {"n": len(rows), "total_cost_usd": round(sum(r["cost_usd"] for r in rows), 4),
           "steps": {}}
    for step, rs in sorted(by_step.items()):
        lat = [r["latency_s"] for r in rs]
        out["steps"][step] = {
            "n": len(rs),
            "cost_usd": round(sum(r["cost_usd"] for r in rs), 4),
            "p50_latency_s": round(percentile(lat, 0.50), 3),
            "p95_latency_s": round(percentile(lat, 0.95), 3),
            "mean_input_tokens": int(statistics.mean(r["input_tokens"] for r in rs)),
            "mean_output_tokens": int(statistics.mean(r["output_tokens"] for r in rs)),
            "cache_hit_rate": round(
                sum(1 for r in rs if r["cache_read_tokens"] > 0) / len(rs), 3),
            "retry_rate": round(sum(1 for r in rs if r["attempts"] > 1) / len(rs), 3),
            "truncation_rate": round(
                sum(1 for r in rs if r["stop_reason"] == "max_tokens") / len(rs), 3),
        }
    return out


def print_summary(recs: list[dict] | None = None) -> None:
    s = summary(recs)
    if not s.get("n"):
        print("no traces")
        return
    print(f"{s['n']} calls, ${s['total_cost_usd']}")
    print(f"{'step':22s} {'n':>5s} {'$':>8s} {'p50':>7s} {'p95':>7s} "
          f"{'in tok':>8s} {'cache':>6s} {'retry':>6s} {'trunc':>6s}")
    for step, m in s["steps"].items():
        print(f"{step:22s} {m['n']:5d} {m['cost_usd']:8.4f} "
              f"{m['p50_latency_s']:6.2f}s {m['p95_latency_s']:6.2f}s "
              f"{m['mean_input_tokens']:8,d} {m['cache_hit_rate']:6.0%} "
              f"{m['retry_rate']:6.0%} {m['truncation_rate']:6.0%}")


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------
def population_stability_index(expected: list[str], actual: list[str],
                               eps: float = 1e-4) -> float:
    """PSI over a categorical distribution.

        PSI = SUM (a_i - e_i) * ln(a_i / e_i)

    Rules of thumb from credit risk, which is where it comes from:
      < 0.10  no meaningful shift
      0.10-0.25  moderate shift, investigate
      > 0.25  significant shift, act

    For InsightHub the natural application is the category mix. A congress
    happens, the field starts asking about a biomarker, and DIAGNOSTIC_MONITORING
    triples. That is not a bug — but you want to know within a day, not next
    quarter, and it is the same signal you would see if a prompt change silently
    broke categorisation.
    """
    e_counts, a_counts = Counter(expected), Counter(actual)
    keys = set(e_counts) | set(a_counts)
    ne, na = max(len(expected), 1), max(len(actual), 1)
    psi = 0.0
    for k in keys:
        e = max(e_counts.get(k, 0) / ne, eps)
        a = max(a_counts.get(k, 0) / na, eps)
        psi += (a - e) * math.log(a / e)
    return float(psi)


def drift_report(baseline_rows: list[dict], current_rows: list[dict]) -> dict:
    """Compare two ingestion runs on the signals that move when something breaks."""
    def cats(rows):
        return [i["category"] for r in rows for i in r.get("insights", [])]

    def per_note(rows):
        return [len(r.get("insights", [])) for r in rows]

    def flag_rate(rows, flag):
        n = sum(1 for r in rows if flag in (r.get("flags") or {})
                and r["flags"].get(flag))
        return n / max(len(rows), 1)

    b_cats, c_cats = cats(baseline_rows), cats(current_rows)
    return {
        "category_psi": round(population_stability_index(b_cats, c_cats), 4),
        "insights_per_note": {
            "baseline": round(statistics.mean(per_note(baseline_rows) or [0]), 3),
            "current": round(statistics.mean(per_note(current_rows) or [0]), 3),
        },
        "empty_extraction_rate": {
            "baseline": round(sum(1 for x in per_note(baseline_rows) if x == 0)
                              / max(len(baseline_rows), 1), 3),
            "current": round(sum(1 for x in per_note(current_rows) if x == 0)
                             / max(len(current_rows), 1), 3),
        },
        "ae_flag_rate": {
            "baseline": round(flag_rate(baseline_rows, "adverse_event"), 3),
            "current": round(flag_rate(current_rows, "adverse_event"), 3),
        },
        "unfaithful_verbatim_rate": {
            "baseline": _unfaithful(baseline_rows),
            "current": _unfaithful(current_rows),
        },
    }


def _unfaithful(rows: list[dict]) -> float:
    total = sum(len(r.get("insights", [])) for r in rows)
    bad = sum(1 for r in rows for i in r.get("insights", [])
              if not i.get("verbatim_ok", True))
    return round(bad / max(total, 1), 4)


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------
@dataclass
class Alert:
    name: str
    severity: str
    value: float
    threshold: float
    message: str


DEFAULT_THRESHOLDS = {
    # (metric, comparison, threshold, severity)
    "unfaithful_verbatim_rate": (">", 0.03, "page"),
    "empty_extraction_rate": (">", 0.25, "ticket"),
    "category_psi": (">", 0.25, "ticket"),
    "p95_latency_s": (">", 12.0, "ticket"),
    "retry_rate": (">", 0.10, "ticket"),
    "truncation_rate": (">", 0.02, "page"),
    "ae_flag_rate_drop": (">", 0.40, "page"),
}


def check_alerts(drift: dict, metrics: dict,
                 thresholds: dict | None = None) -> list[Alert]:
    """Alert on the things that indicate silent breakage, not on everything.

    An alert nobody acts on trains people to ignore alerts. Two severities:
    `page` means a human is woken; `ticket` means it is looked at tomorrow. If
    you cannot say which, it is a dashboard metric, not an alert.
    """
    th = thresholds or DEFAULT_THRESHOLDS
    out: list[Alert] = []

    def add(name, value, key=None):
        key = key or name
        if key not in th:
            return
        _, limit, sev = th[key]
        if value > limit:
            out.append(Alert(name, sev, value, limit,
                             f"{name}={value:.3f} exceeds {limit}"))

    add("unfaithful_verbatim_rate", drift["unfaithful_verbatim_rate"]["current"])
    add("empty_extraction_rate", drift["empty_extraction_rate"]["current"])
    add("category_psi", drift["category_psi"])

    # A DROP in the AE flag rate is the dangerous direction: it means we may be
    # missing reportable events. A rise is merely expensive.
    b = drift["ae_flag_rate"]["baseline"] or 1e-9
    c = drift["ae_flag_rate"]["current"]
    if b > 0:
        add("ae_flag_rate_drop", max(0.0, (b - c) / b), key="ae_flag_rate_drop")

    for step, m in metrics.get("steps", {}).items():
        add(f"{step}.p95_latency_s", m["p95_latency_s"], key="p95_latency_s")
        add(f"{step}.retry_rate", m["retry_rate"], key="retry_rate")
        add(f"{step}.truncation_rate", m["truncation_rate"], key="truncation_rate")
    return out
