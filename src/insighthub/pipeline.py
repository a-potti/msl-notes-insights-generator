"""The ingestion workflow. Chapter 4 §4.2.

This is deliberately NOT an agent. Ingestion has a known shape: for each note,
do these five things in this order. There is no decision for a model to make
about the sequence, so giving it one buys nothing and costs money,
non-determinism and debuggability.

The rule: **use a workflow when you know the steps; use an agent when the path
depends on what you find.** Most production "agents" are workflows that someone
made non-deterministic by accident.
"""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import MODEL_FAST, MODEL_WORK, RUNS_DIR
from .corpus import Note
from .extract import Extraction, extract_note
from .guardrails import combined_gate, detect_injection, lexical_gate

PIPELINE_VERSION = "ingest-v1"


@dataclass
class IngestedNote:
    note_id: str
    content_hash: str
    insights: list[dict] = field(default_factory=list)
    flags: dict = field(default_factory=dict)
    routing: list[str] = field(default_factory=list)
    quarantined: bool = False
    errors: list[str] = field(default_factory=list)
    versions: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_s: float = 0.0


@dataclass
class RunStats:
    notes_in: int = 0
    notes_ok: int = 0
    notes_failed: int = 0
    insights: int = 0
    unfaithful_verbatim: int = 0
    pv_routed: int = 0
    quality_routed: int = 0
    medinfo_routed: int = 0
    quarantined: int = 0
    cost_usd: float = 0.0
    wall_s: float = 0.0

    def __str__(self) -> str:
        return (f"notes {self.notes_ok}/{self.notes_in} ok ({self.notes_failed} failed) | "
                f"{self.insights} insights ({self.unfaithful_verbatim} unfaithful) | "
                f"routed pv={self.pv_routed} quality={self.quality_routed} "
                f"medinfo={self.medinfo_routed} | quarantined={self.quarantined} | "
                f"${self.cost_usd:.4f} | {self.wall_s:.1f}s")


def content_hash(text: str) -> str:
    """Key incremental processing on content, not filename. MSLs edit notes."""
    return hashlib.blake2b(text.encode(), digest_size=12).hexdigest()


def ingest_one(note: Note, *, extract_model: str = MODEL_WORK,
               gate_model: str = MODEL_FAST, use_model_gate: bool = True) -> IngestedNote:
    """The five-step DAG for a single note.

    1. hash + injection screen
    2. compliance gate      (deterministic UNION model — never conditional on extraction)
    3. extract insights
    4. verbatim faithfulness check (deterministic, free)
    5. routing decisions
    """
    t0 = time.perf_counter()
    out = IngestedNote(note_id=note.note_id, content_hash=content_hash(note.text))
    out.versions = {"pipeline": PIPELINE_VERSION, "extract_model": extract_model,
                    "gate_model": gate_model}

    # 1 -------------------------------------------------------------------
    injected, hits = detect_injection(note.body)
    out.quarantined = injected
    if injected:
        out.flags["injection_patterns"] = hits

    # 2 -------------------------------------------------------------------
    # Runs on EVERY note, before and independently of extraction. If extraction
    # fails, the AE still gets routed. Ordering is a compliance decision, not a
    # performance one.
    gate = combined_gate(note.body, use_model=use_model_gate, model=gate_model)
    out.flags.update({
        "adverse_event": gate.adverse_event,
        "product_complaint": gate.product_complaint,
        "off_label": gate.off_label,
        "injection_suspected": gate.injection_suspected or injected,
        "reasons": gate.reasons,
    })

    # 3 -------------------------------------------------------------------
    ex: Extraction = extract_note(note, model=extract_model, temperature=0.0)
    if not ex.ok:
        out.errors.append(ex.error or "unknown extraction error")
    out.insights = ex.insights
    if ex.result:
        out.cost_usd += ex.result.cost_usd

    # 4 -------------------------------------------------------------------
    for ins in out.insights:
        ins["verbatim_ok"] = ins.get("verbatim", "") in note.body

    # 5 -------------------------------------------------------------------
    if gate.adverse_event:
        out.routing.append("PHARMACOVIGILANCE_24H")
    if gate.product_complaint:
        out.routing.append("QUALITY_1BD")
    if gate.off_label:
        out.routing.append("MEDICAL_INFORMATION")
    if out.quarantined or gate.injection_suspected:
        out.routing.append("SECURITY_REVIEW")

    out.latency_s = time.perf_counter() - t0
    return out


def ingest(notes: list[Note], *, max_workers: int = 8, use_model_gate: bool = True,
           extract_model: str = MODEL_WORK, out_path: str | Path | None = None,
           progress: bool = True) -> tuple[list[IngestedNote], RunStats]:
    """Parallel fan-out over notes.

    Notes are independent, so this is embarrassingly parallel and threads are
    enough (the work is IO-bound on the API). Parallelise across the outer loop,
    not inside a single note's DAG — the steps there have real dependencies and
    parallelising them is where subtle ordering bugs come from.
    """
    t0 = time.perf_counter()
    stats = RunStats(notes_in=len(notes))
    results: list[IngestedNote] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(ingest_one, n, extract_model=extract_model,
                            use_model_gate=use_model_gate): n for n in notes}
        for i, fut in enumerate(as_completed(futs), 1):
            note = futs[fut]
            try:
                results.append(fut.result())
            except Exception as exc:
                # One note must never take down the run.
                results.append(IngestedNote(note_id=note.note_id,
                                            content_hash=content_hash(note.text),
                                            errors=[f"{type(exc).__name__}: {exc}"]))
            if progress and i % 20 == 0:
                print(f"  ...{i}/{len(futs)}")

    for r in results:
        if r.errors:
            stats.notes_failed += 1
        else:
            stats.notes_ok += 1
        stats.insights += len(r.insights)
        stats.unfaithful_verbatim += sum(1 for i in r.insights
                                         if not i.get("verbatim_ok", True))
        stats.pv_routed += "PHARMACOVIGILANCE_24H" in r.routing
        stats.quality_routed += "QUALITY_1BD" in r.routing
        stats.medinfo_routed += "MEDICAL_INFORMATION" in r.routing
        stats.quarantined += r.quarantined
        stats.cost_usd += r.cost_usd
    stats.wall_s = time.perf_counter() - t0

    results.sort(key=lambda r: r.note_id)
    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            for r in results:
                f.write(json.dumps(asdict(r)) + "\n")
        print(f"wrote {len(results)} records to {p}")
    return results, stats
