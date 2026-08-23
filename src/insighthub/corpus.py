"""Loading the corpus. Boring on purpose — provided for you.

The only interesting decision here is `Note.body`: we strip the header before
sending text to the model, because the header contains the KOL's name and
institution, and we do not want the model to condition its judgement of an
insight on who said it. Attribution is attached back structurally, afterwards.
That separation is what makes the Medical/Commercial firewall enforceable.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .config import (CONGRESS_DIR, EVAL_DIR, FACT_BASE_PATH, KOL_DIR, NOTES_DIR,
                     PUBS_DIR, TAXONOMY_PATH)


@dataclass
class Note:
    note_id: str
    date: str
    msl_id: str
    msl_name: str
    region: str
    kol_id: str
    kol_name: str
    institution: str
    kol_tier: int
    interaction_type: str
    split: str
    text: str

    @property
    def body(self) -> str:
        """The note without its identifying header block."""
        lines = self.text.splitlines()
        for i, ln in enumerate(lines):
            if ln.strip().lower().startswith(("interaction type", "objective")):
                return "\n".join(lines[i + 1:]).strip()
        return self.text.strip()


@lru_cache(maxsize=1)
def load_notes() -> list[Note]:
    rows = list(csv.DictReader(open(NOTES_DIR / "manifest.csv")))
    out = []
    for r in rows:
        text = (NOTES_DIR / f"{r['note_id']}.txt").read_text()
        out.append(Note(
            note_id=r["note_id"], date=r["date"], msl_id=r["msl_id"],
            msl_name=r["msl_name"], region=r["region"], kol_id=r["kol_id"],
            kol_name=r["kol_name"], institution=r["institution"],
            kol_tier=int(r["kol_tier"]), interaction_type=r["interaction_type"],
            split=r["split"], text=text,
        ))
    return out


def notes_by_split(split: str | None = None) -> list[Note]:
    notes = load_notes()
    return [n for n in notes if split is None or n.split == split]


def get_note(note_id: str) -> Note:
    for n in load_notes():
        if n.note_id == note_id:
            return n
    raise KeyError(note_id)


@lru_cache(maxsize=1)
def load_taxonomy() -> dict:
    return yaml.safe_load(TAXONOMY_PATH.read_text())


def category_names() -> list[str]:
    return list(load_taxonomy()["categories"])


def taxonomy_prompt_block() -> str:
    """The taxonomy rendered for a prompt. Stable text => cacheable prefix."""
    t = load_taxonomy()
    lines = ["## Insight categories (choose exactly one per insight)"]
    for name, meta in t["categories"].items():
        lines.append(f"- **{name}** — {meta['description']}")
    lines += ["", "## Not-an-insight labels"]
    for name, meta in t["non_insight_labels"].items():
        lines.append(f"- **{name}** — {meta['description']}")
    lines += ["", "## Compliance flags (apply all that are present)"]
    for name, meta in t["flags"].items():
        lines.append(f"- **{name}** — {meta['description']}")
    lines += ["", "## Medical strategy priorities"]
    for k, v in t["strategic_priorities"].items():
        lines.append(f"- **{k}** — {v}")
    return "\n".join(lines)


@lru_cache(maxsize=1)
def fact_base() -> str:
    return FACT_BASE_PATH.read_text()


@lru_cache(maxsize=1)
def load_kols() -> list[dict]:
    rows = list(csv.DictReader(open(KOL_DIR / "kols.csv")))
    for r in rows:
        for k in ("tier", "publications", "is_trial_investigator",
                  "guideline_committee", "advisory_board_member"):
            r[k] = int(r[k])
        r["influence_score"] = float(r["influence_score"])
    return rows


FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


def _load_md_dir(path: Path, id_field: str) -> list[dict]:
    docs = []
    for f in sorted(path.glob("*.md")):
        raw = f.read_text()
        m = FRONTMATTER.match(raw)
        meta = yaml.safe_load(m.group(1)) if m else {}
        body = raw[m.end():] if m else raw
        meta["doc_id"] = meta.get(id_field, f.stem)
        meta["text"] = body.strip()
        meta["path"] = str(f)
        docs.append(meta)
    return docs


@lru_cache(maxsize=1)
def load_congress() -> list[dict]:
    return _load_md_dir(CONGRESS_DIR, "abstract_id")


@lru_cache(maxsize=1)
def load_publications() -> list[dict]:
    return _load_md_dir(PUBS_DIR, "publication_id")


def load_evidence() -> list[dict]:
    """Congress abstracts + publications, the external evidence corpus."""
    return load_congress() + load_publications()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def load_gold(split: str | None = None) -> list[dict]:
    """Ground truth. Chapter 5 tells you when you are allowed to use this."""
    rows = load_jsonl(EVAL_DIR / "gold_insights.jsonl")
    return [r for r in rows if split is None or r["split"] == split]
