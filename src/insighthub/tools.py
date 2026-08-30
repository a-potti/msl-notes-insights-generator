"""The tool registry the analyst agent can call. Chapter 4 §4.4.

Three rules this file exists to demonstrate:

1. **Tool descriptions are prompt.** The description is the only thing standing
   between the model and calling the wrong tool. Say what the tool is for AND
   what it is not for.
2. **Every tool validates its own arguments.** The model will send you a limit of
   10,000. Clamp it here, not in a code review comment.
3. **Every tool bounds its output.** An unbounded tool result is how you blow the
   context window in one call and how you exfiltrate a database in one call.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from .config import RUNS_DIR
from .corpus import get_note, load_kols
from .index import Index, meta_filter

MAX_RESULT_CHARS = 6000


@dataclass
class Tool:
    schema: dict
    fn: Callable[[dict], Any]
    reads_untrusted: bool = False   # does the result contain third-party text?
    mutates: bool = False           # can this change state or leave the system?

    @property
    def name(self) -> str:
        return self.schema["name"]


def _truncate(payload: Any) -> str:
    s = payload if isinstance(payload, str) else json.dumps(payload, default=str)
    if len(s) <= MAX_RESULT_CHARS:
        return s
    return s[:MAX_RESULT_CHARS] + f"\n...[truncated, {len(s):,} chars total. " \
                                  f"Narrow your query rather than asking for more.]"


# ---------------------------------------------------------------------------
def make_search_notes(index: Index) -> Tool:
    schema = {
        "name": "search_notes",
        "description": (
            "Search MSL call notes for what clinicians have SAID. Use for questions "
            "about opinions, concerns, questions raised, and perceptions. Supports "
            "metadata filters — always use them when the question mentions a region, "
            "KOL tier, date range or interaction type, because the text search cannot "
            "understand those. Do NOT use this to look up published data (use "
            "search_evidence) or to ask who someone is (use query_kols)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "What was said, in the clinician's terms."},
                "k": {"type": "integer",
                      "description": "1 to 25. Defaults to 8."},
                "region": {"type": "string",
                           "enum": ["US-East", "US-West", "US-Central", "EMEA", "APAC"]},
                "kol_tier": {"type": "integer", "enum": [1, 2, 3]},
                "since": {"type": "string", "description": "ISO date, inclusive"},
                "until": {"type": "string", "description": "ISO date, inclusive"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    }

    def run(args: dict) -> Any:
        k = min(int(args.get("k", 8)), 25)
        where = meta_filter(**{key: args[key] for key in
                               ("region", "kol_tier", "since", "until") if key in args})
        hits = index.hybrid_search(args["query"], k, where=where)
        return {"n": len(hits), "results": [
            {"note_id": h.doc.doc_id, "date": h.doc.meta.get("date"),
             "region": h.doc.meta.get("region"), "kol_tier": h.doc.meta.get("kol_tier"),
             "score": round(h.score, 4), "text": h.doc.text[:900]}
            for h in hits]}

    return Tool(schema, run, reads_untrusted=True)


def make_search_evidence(index: Index) -> Tool:
    schema = {
        "name": "search_evidence",
        "description": (
            "Search congress abstracts and publications for PUBLISHED data. Use when "
            "you need a number, an endpoint, a study result, or to check whether "
            "evidence exists to answer something the field is asking. Do NOT use for "
            "clinician opinions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "description": "1 to 15. Defaults to 6."},
                "congress": {"type": "string",
                             "enum": ["UEGW-2025", "ECCO-2026", "DDW-2026"]},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    }

    def run(args: dict) -> Any:
        k = min(int(args.get("k", 6)), 15)
        where = meta_filter(congress=args["congress"]) if "congress" in args else None
        hits = index.hybrid_search(args["query"], k, where=where)
        return {"n": len(hits), "results": [
            {"doc_id": h.doc.doc_id, "title": h.doc.meta.get("title"),
             "section": h.doc.meta.get("section"), "date": h.doc.meta.get("date"),
             "text": h.doc.text[:900]} for h in hits]}

    return Tool(schema, run)


def make_query_kols() -> Tool:
    from .semantic import query_kols_tool, run_query_kols_tool
    return Tool(query_kols_tool(), run_query_kols_tool)


def make_get_note() -> Tool:
    schema = {
        "name": "get_note",
        "description": ("Fetch the full text of one call note by ID. Use after "
                        "search_notes when a snippet is not enough."),
        "input_schema": {
            "type": "object",
            "properties": {"note_id": {"type": "string",
                                       "pattern": "^NOTE-[0-9]{4}$"}},
            "required": ["note_id"],
            "additionalProperties": False,
        },
        "strict": True,
    }

    def run(args: dict) -> Any:
        try:
            n = get_note(args["note_id"])
        except KeyError:
            return {"error": f"no such note: {args['note_id']}"}
        return {"note_id": n.note_id, "date": n.date, "region": n.region,
                "kol_tier": n.kol_tier, "text": n.body}

    return Tool(schema, run, reads_untrusted=True)


def make_run_python() -> Tool:
    """Counting and arithmetic. The model is bad at both; Python is not.

    SECURITY: this executes model-authored code. In this tutorial it runs in your
    process with a tiny allowlist, which is fine for learning and NOT fine for
    production. In production this belongs in a sandbox with no network, no
    filesystem, a memory cap and a wall-clock kill — a container, gVisor, Firecracker
    or a hosted code-execution tool. Chapter 4 §4.9 goes through the threat model.
    """
    schema = {
        "name": "run_python",
        "description": (
            "Run a short Python snippet over a list of dicts named `rows` that you "
            "provide. Use for counting, grouping, percentages and date arithmetic — "
            "never estimate these yourself. Assign your answer to `result`."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "rows": {"type": "array", "items": {"type": "object"}},
                "code": {"type": "string",
                         "description": "Python. `rows` is in scope. Set `result`."},
            },
            "required": ["rows", "code"],
        },
        # No strict mode here: `rows` is an arbitrary-shaped dict the model copies
        # back from earlier tool results, and strict schema's closed-object
        # requirement (additionalProperties: false on every nested object) can't
        # express "object with whatever keys the data happens to have."
    }

    ALLOWED = {"len", "sum", "min", "max", "sorted", "set", "list", "dict", "str",
               "int", "float", "round", "abs", "any", "all", "enumerate", "zip",
               "range", "map", "filter", "tuple", "reversed"}

    def run(args: dict) -> Any:
        import collections
        import datetime
        import statistics
        code = args["code"]
        for bad in ("import ", "open(", "__", "eval(", "exec(", "compile("):
            if bad in code:
                return {"error": f"disallowed construct: {bad.strip()}"}
        env = {"rows": args["rows"], "collections": collections,
               "statistics": statistics, "datetime": datetime,
               "__builtins__": {k: __builtins__[k] if isinstance(__builtins__, dict)
                                else getattr(__builtins__, k) for k in ALLOWED}}
        try:
            exec(code, env)                                   # noqa: S102
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
        return {"result": env.get("result", "<code did not set `result`>")}

    return Tool(schema, run)


# ---------------------------------------------------------------------------
class Registry:
    def __init__(self, tools: list[Tool]):
        self.tools = {t.name: t for t in tools}

    def schemas(self) -> list[dict]:
        return [t.schema for t in self.tools.values()]

    def call(self, name: str, args: dict) -> tuple[str, bool]:
        """Returns (result_string, is_error). Never raises: a tool that throws
        ends the agent loop, and a tool that returns an error lets the model
        recover. Almost always you want the second."""
        tool = self.tools.get(name)
        if tool is None:
            return json.dumps({"error": f"unknown tool {name}"}), True
        try:
            out = tool.fn(args)
        except Exception as exc:
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"}), True
        if isinstance(out, dict) and "error" in out:
            return _truncate(out), True
        return _truncate(out), False

    def reads_untrusted(self, name: str) -> bool:
        t = self.tools.get(name)
        return bool(t and t.reads_untrusted)


def default_registry(notes_index: Index, evidence_index: Index) -> Registry:
    return Registry([
        make_search_notes(notes_index),
        make_search_evidence(evidence_index),
        make_query_kols(),
        make_get_note(),
        make_run_python(),
    ])
