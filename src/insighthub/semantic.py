"""A semantic layer over the structured KOL / interaction data. Chapter 3 §3.7.

The question "which tier-1 EMEA KOLs on a guideline committee have we not seen
since ECCO?" is not a semantic search problem. It is a query. Embeddings cannot
count, cannot compare dates and cannot do set difference.

The tempting move is to let the model write SQL. Don't, not here:

  * SQL injection stops being a metaphor once the model composes the string.
  * A model that can express any query can express `SELECT * FROM kols`, and in
    a Medical Affairs system, bulk KOL extraction is exactly the exfiltration
    path that governance exists to prevent.
  * You cannot write a test for "all the SQL the model might emit."

A semantic layer is the alternative: a small set of named, parameterised
operations over a vocabulary of business terms. The model chooses from a menu
instead of writing code. Every possible query is enumerable, testable and
auditable — and the model finds it *easier*, because the menu encodes what the
columns mean.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from .corpus import load_kols, load_notes

# --- the business vocabulary ----------------------------------------------
# This dict is the semantic layer. It maps words medical affairs people use onto
# columns and predicates. Change a column name and you change it here, once.
DIMENSIONS = {
    "region": "region",
    "tier": "tier",
    "specialty": "specialty",
    "institution": "institution",
}
MEASURES = {
    "interaction_count": "number of call notes recorded with this KOL",
    "last_interaction_date": "date of the most recent interaction",
    "distinct_msls": "how many different MSLs have met this KOL",
    "influence_score": "internal influence score, 0-100",
    "publications": "publication count",
}
FLAGS = {
    "is_trial_investigator": "has been an investigator on one of our studies",
    "guideline_committee": "sits on a guideline committee",
    "advisory_board_member": "has attended one of our advisory boards",
}


@dataclass
class KolQuery:
    """The one shape of question the layer answers. Every field is optional."""
    region: str | list[str] | None = None
    tier: int | list[int] | None = None
    specialty: str | None = None
    institution_contains: str | None = None
    is_trial_investigator: bool | None = None
    guideline_committee: bool | None = None
    advisory_board_member: bool | None = None
    min_interactions: int | None = None
    max_interactions: int | None = None
    seen_since: str | None = None
    not_seen_since: str | None = None
    order_by: Literal["influence_score", "interaction_count", "publications",
                      "last_interaction_date"] = "influence_score"
    descending: bool = True
    limit: int = 20


def _kol_frame() -> pd.DataFrame:
    kols = pd.DataFrame(load_kols())
    notes = pd.DataFrame([{"kol_id": n.kol_id, "date": n.date, "msl_id": n.msl_id}
                          for n in load_notes()])
    agg = notes.groupby("kol_id").agg(
        interaction_count=("date", "size"),
        last_interaction_date=("date", "max"),
        distinct_msls=("msl_id", "nunique"),
    ).reset_index()
    df = kols.merge(agg, on="kol_id", how="left")
    df["interaction_count"] = df["interaction_count"].fillna(0).astype(int)
    df["distinct_msls"] = df["distinct_msls"].fillna(0).astype(int)
    df["last_interaction_date"] = df["last_interaction_date"].fillna("")
    return df


def query_kols(q: KolQuery) -> pd.DataFrame:
    df = _kol_frame()

    def isin(col, want):
        return df[col].isin(want if isinstance(want, (list, tuple, set)) else [want])

    if q.region is not None:
        df = df[isin("region", q.region)]
    if q.tier is not None:
        df = df[isin("tier", q.tier)]
    if q.specialty is not None:
        df = df[df["specialty"].str.contains(q.specialty, case=False, na=False)]
    if q.institution_contains:
        df = df[df["institution"].str.contains(q.institution_contains, case=False,
                                               na=False)]
    for flag in ("is_trial_investigator", "guideline_committee",
                 "advisory_board_member"):
        want = getattr(q, flag)
        if want is not None:
            df = df[df[flag] == int(want)]
    if q.min_interactions is not None:
        df = df[df["interaction_count"] >= q.min_interactions]
    if q.max_interactions is not None:
        df = df[df["interaction_count"] <= q.max_interactions]
    if q.seen_since:
        df = df[df["last_interaction_date"] >= q.seen_since]
    if q.not_seen_since:
        df = df[(df["last_interaction_date"] < q.not_seen_since)
                | (df["last_interaction_date"] == "")]

    df = df.sort_values(q.order_by, ascending=not q.descending)
    return df.head(q.limit).reset_index(drop=True)


# --- the tool schema the agent sees (Chapter 4) ---------------------------
def query_kols_tool() -> dict:
    return {
        "name": "query_kols",
        "description": (
            "Query the KOL roster with structured filters. Use this for questions "
            "about WHO — coverage, tiering, engagement gaps, geography, committee "
            "membership — never for questions about WHAT people said, which need "
            "search_notes. Returns aggregated rows, never free text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {"type": "array", "items": {
                    "type": "string",
                    "enum": ["US-East", "US-West", "US-Central", "EMEA", "APAC"]}},
                "tier": {"type": "array", "items": {"type": "integer",
                                                    "enum": [1, 2, 3]}},
                "specialty": {"type": "string"},
                "institution_contains": {"type": "string"},
                "is_trial_investigator": {"type": "boolean"},
                "guideline_committee": {"type": "boolean"},
                "advisory_board_member": {"type": "boolean"},
                "min_interactions": {"type": "integer", "description": "0 or more."},
                "max_interactions": {"type": "integer", "description": "0 or more."},
                "seen_since": {"type": "string",
                               "description": "ISO date; KOLs seen on or after"},
                "not_seen_since": {"type": "string",
                                   "description": "ISO date; KOLs NOT seen since"},
                "order_by": {"type": "string",
                             "enum": ["influence_score", "interaction_count",
                                      "publications", "last_interaction_date"]},
                "limit": {"type": "integer", "description": "1 to 40."},
            },
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    }


def run_query_kols_tool(args: dict[str, Any]) -> dict:
    """Adapter from tool arguments to the typed query. Note the hard limit —
    a tool that can return the entire KOL roster is an exfiltration primitive."""
    args = dict(args)
    args["limit"] = min(int(args.get("limit", 20)), 40)
    q = KolQuery(**{k: v for k, v in args.items()
                    if k in KolQuery.__dataclass_fields__})
    df = query_kols(q)
    cols = ["kol_id", "name", "institution", "region", "specialty", "tier",
            "publications", "influence_score", "interaction_count",
            "last_interaction_date", "guideline_committee", "is_trial_investigator"]
    return {"n_rows": len(df), "rows": df[cols].to_dict("records")}
