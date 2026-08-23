"""A minimal service around InsightHub. Chapter 6 §6.2.

    uvicorn insighthub.serve:app --reload

Deliberately small. The interesting parts are not the routes:

  * every request gets a trace_id, returned to the caller, so a user complaint
    ("the answer at 14:32 was wrong") maps to a trace in one query;
  * outputs carry the version set that produced them, so "which prompt said
    that?" is answerable;
  * the feedback endpoint is the online quality signal — the single most
    valuable metric in the whole system (§6.3).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import observability as obs
from .agent import run_agent
from .config import MODEL_WORK, RUNS_DIR
from .corpus import get_note
from .guardrails import redact_attribution
from .index import evidence_index, notes_index
from .pipeline import PIPELINE_VERSION, ingest_one
from .tools import default_registry

app = FastAPI(title="InsightHub", version="0.1.0")

_state: dict[str, Any] = {}

VERSIONS = {
    "pipeline": PIPELINE_VERSION,
    "prompt": "extract-v1",
    "taxonomy": "v1",
    "embed_model": "all-MiniLM-L6-v2",
}


@app.on_event("startup")
def _startup() -> None:
    obs.start_tracing(run_id=f"serve-{datetime.now(timezone.utc):%Y%m%d}")
    _state["notes"] = notes_index().build(verbose=False)
    _state["evidence"] = evidence_index().build(verbose=False)
    _state["registry"] = default_registry(_state["notes"], _state["evidence"])
    _state["feedback"] = []


class AskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=2000)
    max_steps: int = Field(default=10, ge=1, le=20)


class AskResponse(BaseModel):
    trace_id: str
    answer: str
    tool_calls: list[str]
    cost_usd: float
    latency_s: float
    stopped_because: str
    versions: dict
    warnings: list[str] = []


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    trace_id = uuid.uuid4().hex[:12]
    run = run_agent(req.question, _state["registry"], model=MODEL_WORK,
                    max_steps=req.max_steps)

    warnings = []
    if run.injections_seen:
        warnings.append("Retrieved content contained suspected prompt injection; "
                        "it was quarantined and reported.")
    if run.stopped_because in ("max_steps", "max_cost"):
        warnings.append(f"Answer is partial: agent stopped on {run.stopped_because}.")

    return AskResponse(
        trace_id=trace_id, answer=run.answer,
        tool_calls=[s.name for s in run.tool_calls],
        cost_usd=round(run.cost_usd, 5), latency_s=round(run.latency_s, 3),
        stopped_because=run.stopped_because, versions=VERSIONS, warnings=warnings)


class IngestRequest(BaseModel):
    note_id: str


@app.post("/ingest")
def ingest(req: IngestRequest) -> dict:
    try:
        note = get_note(req.note_id)
    except KeyError:
        raise HTTPException(404, f"unknown note {req.note_id}")
    out = ingest_one(note)
    return {
        "note_id": out.note_id, "content_hash": out.content_hash,
        "n_insights": len(out.insights), "routing": out.routing,
        "quarantined": out.quarantined, "errors": out.errors,
        "versions": out.versions,
    }


class Feedback(BaseModel):
    trace_id: str
    accepted: bool
    corrected_text: str | None = None
    reason: str | None = None


@app.post("/feedback")
def feedback(fb: Feedback) -> dict:
    """The most valuable endpoint in the service.

    Offline evals tell you how you do on 60 examples you chose. This tells you
    how you do on what users actually asked, and every correction is a free
    labelled example (Chapter 5 §5.9). Design the UI so accepting is one click
    and correcting captures the correction.
    """
    _state["feedback"].append({**fb.model_dump(),
                               "ts": datetime.now(timezone.utc).isoformat()})
    return {"ok": True, "n_feedback": len(_state["feedback"])}


@app.get("/metrics")
def metrics() -> dict:
    m = obs.summary()
    fb = _state["feedback"]
    if fb:
        m["online"] = {
            "n_feedback": len(fb),
            "acceptance_rate": round(sum(f["accepted"] for f in fb) / len(fb), 3),
            "edit_rate": round(sum(1 for f in fb if f["corrected_text"]) / len(fb), 3),
        }
    return m


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "versions": VERSIONS,
            "notes_indexed": len(_state.get("notes").docs) if "notes" in _state else 0}
