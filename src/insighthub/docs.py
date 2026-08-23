"""Documents in, LLM-ready text out. Chapter 3 §3.2 and §3.3.

Nobody's favourite module, and the one that decides whether your retrieval works.
Garbage in this file is garbage everywhere downstream, invisibly.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
BOILERPLATE_TAGS = ("script", "style", "nav", "footer", "header", "aside", "form")
BOILERPLATE_IDS = ("cookie", "banner", "ad", "advert", "subscribe", "newsletter",
                   "sidebar", "related", "share", "comment")


def html_to_text(html: str) -> str:
    """Strip chrome, keep structure. Tables become pipe-delimited rows.

    The table handling matters more than it looks: a results table flattened into
    prose ('Clinical remission 68.1% 61.2%') loses the column headers, and an LLM
    reading that will confidently attribute the week-52 number to week 104.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(list(BOILERPLATE_TAGS)):
        tag.decompose()
    for el in soup.find_all(attrs={"id": True}):
        if any(b in el.get("id", "").lower() for b in BOILERPLATE_IDS):
            el.decompose()
    for el in soup.find_all(attrs={"class": True}):
        classes = " ".join(el.get("class", [])).lower()
        if any(b in classes for b in BOILERPLATE_IDS):
            el.decompose()

    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if cells:
                rows.append(" | ".join(cells))
        table.replace_with("\n[TABLE]\n" + "\n".join(rows) + "\n[/TABLE]\n")

    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        h.insert_before("\n\n")
        h.insert_after("\n")

    text = soup.get_text("\n")
    return normalise_whitespace(text)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def pdf_to_text(path: str | Path) -> str:
    """Text layer only. If this returns near-nothing, the PDF is a scan —
    route it to a vision model instead (Chapter 1 §1.10)."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(p.extract_text() or "") for p in reader.pages]
    return normalise_whitespace("\n\n".join(pages))


def looks_like_scan(text: str, n_pages: int = 1) -> bool:
    """Cheap heuristic: fewer than ~120 characters of text per page."""
    return len(text.strip()) < 120 * max(n_pages, 1)


# ---------------------------------------------------------------------------
# OCR damage
# ---------------------------------------------------------------------------
# The naive approach is a list of regex substitutions: I->l, |->I, O->0.
# Try it and watch 'Interaction' become 'lnteraction' and the '|' field
# separators in the header turn into 'I'. Blind substitution trades one kind of
# corruption for another.
#
# The approach that works is lexicon-guided: only accept a substitution if it
# turns an unknown token into a known one. Your own clean corpus is the lexicon.

CONFUSIONS = {"I": ["l", "1"], "l": ["I", "1"], "|": ["I", "l"],
              "O": ["0"], "0": ["O", "o"], "1": ["l", "I"],
              "5": ["S"], "S": ["5"], "8": ["B"], "rn": ["m"]}

_WORD = re.compile(r"[A-Za-z0-9|'\-]+")


def build_lexicon(texts: list[str]) -> set[str]:
    """Vocabulary from documents you trust. Case-folded."""
    lex: set[str] = set()
    for t in texts:
        lex.update(w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'\-]+", t))
    return lex


def default_lexicon() -> set[str]:
    """Every word in every document we consider clean, plus the system dictionary
    if this machine has one. Bigger lexicon = more repairs, but also more chances
    to "repair" a rare correct word into a common wrong one. Measure it (§3.2)."""
    from .corpus import (fact_base, load_evidence, load_notes,
                         taxonomy_prompt_block)
    texts = [n.text for n in load_notes()]
    texts += [d["text"] for d in load_evidence()]
    texts += [fact_base(), taxonomy_prompt_block()]
    lex = build_lexicon(texts)
    for path in ("/usr/share/dict/words", "/usr/dict/words"):
        p = Path(path)
        if p.exists():
            lex.update(w.strip().lower() for w in p.read_text(errors="ignore").split()
                       if len(w.strip()) > 2)
            break
    return lex


def _candidates(token: str, max_edits: int = 3) -> list[str]:
    """All strings reachable by applying up to max_edits confusion swaps."""
    frontier = {token}
    seen = {token}
    for _ in range(max_edits):
        nxt = set()
        for cand in frontier:
            for i, ch in enumerate(cand):
                for rep in CONFUSIONS.get(ch, ()):
                    new = cand[:i] + rep + cand[i + 1:]
                    if new not in seen:
                        seen.add(new)
                        nxt.add(new)
        frontier = nxt
    return list(seen)


_DIGITISE = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "|": "1", "S": "5"})

# Identifiers in this corpus are PREFIX-digits. Knowing your own schema beats any
# general-purpose repair: 'NOTE-Ol4l' is unambiguous once you know the shape.
ID_TOKEN = re.compile(r"^([A-Z]{2,6})-([A-Za-z0-9|]{1,6})$")


def _fix_numeric(token: str) -> str | None:
    """'2O26' and 'NOTE-Ol4l' — tokens that should be digits."""
    m = ID_TOKEN.match(token)
    if m:
        suffix = m.group(2).translate(_DIGITISE)
        if re.fullmatch(r"\d+", suffix):
            return f"{m.group(1)}-{suffix}"
        return None
    if not re.search(r"\d", token):
        return None
    mapped = token.translate(_DIGITISE)
    return mapped if mapped != token and re.fullmatch(r"[\d\-/.]+", mapped) else None


# --- character bigram model ------------------------------------------------
# A word list will never contain every correct word, and a domain lexicon
# contains almost no ordinary English. So back the lexicon with a character
# bigram model learnt from the clean corpus: 'Io' is vanishingly rare in real
# text, 'lo' is common, so 'Iooks' -> 'looks' without any dictionary at all.
# NOTE: case is deliberately preserved. The whole signal in 'Iooks' is that a
# capital I sits between word-start and a lowercase letter, which essentially
# never happens in real text. Lowercase the corpus and you delete the evidence.
_bigram_cache: dict[str, dict] = {}


def _bigram_model(texts: list[str] | None = None) -> dict:
    if "default" in _bigram_cache and texts is None:
        return _bigram_cache["default"]
    if texts is None:
        from .corpus import fact_base, load_evidence, load_notes
        texts = ([n.text for n in load_notes()]
                 + [d["text"] for d in load_evidence()] + [fact_base()])
    counts: dict[str, int] = {}
    total = 0
    for t in texts:
        for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", t):
            s = f"^{w}$"
            for a, b in zip(s, s[1:]):
                counts[a + b] = counts.get(a + b, 0) + 1
                total += 1
    model = {"counts": counts, "total": max(total, 1), "V": max(len(counts), 1)}
    if texts is not None:
        _bigram_cache["default"] = model
    return model


def _bigram_score(word: str, model: dict) -> float:
    import math
    s = f"^{word}$"
    c, tot, V = model["counts"], model["total"], model["V"]
    return sum(math.log((c.get(a + b, 0) + 1) / (tot + V)) for a, b in zip(s, s[1:]))


def repair_ocr(text: str, lexicon: set[str] | None = None,
               min_gain: float = 2.0) -> str:
    """Repair look-alike character damage. Three rules, in priority order:

      1. A token already in the lexicon is never touched. This is what stops
         'Interaction' from becoming 'lnteraction'.
      2. Schema-shaped tokens (IDs, dates) are digitised.
      3. Otherwise, prefer a confusion-candidate that is in the lexicon; failing
         that, one that scores at least `min_gain` better under a character
         bigram model learnt from the clean corpus.

    `min_gain` is a precision/recall dial. Raise it to repair less and corrupt
    less. §3.2's exercise asks you to measure both directions.
    """
    if lexicon is None:
        lexicon = default_lexicon()
    model = _bigram_model()

    def fix(m: re.Match) -> str:
        tok = m.group(0)
        core = tok.strip("'-")
        if not core or core.lower() in lexicon:
            return tok
        num = _fix_numeric(core)
        if num is not None:
            return tok.replace(core, num)
        cands = [c for c in _candidates(core) if c != core]
        for cand in sorted(cands, key=len):
            if cand.lower() in lexicon:
                return tok.replace(core, cand)
        if not cands or not re.fullmatch(r"[A-Za-z|]{3,}", core):
            return tok
        base = _bigram_score(core, model)
        best = max(cands, key=lambda c: _bigram_score(c, model))
        if _bigram_score(best, model) - base >= min_gain:
            return tok.replace(core, best)
        return tok

    return _WORD.sub(fix, text)


# ---------------------------------------------------------------------------
# Dirty CSV
# ---------------------------------------------------------------------------
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d")


def parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def normalise_person(raw: str) -> str:
    """'Ferreira, A.' and 'A. Ferreira' are the same person."""
    raw = (raw or "").strip().rstrip(".")
    if not raw:
        return ""
    if "," in raw:
        last, first = (p.strip() for p in raw.split(",", 1))
        return f"{first.rstrip('.')}. {last}" if first else last
    return raw


@dataclass
class CleanReport:
    rows_in: int = 0
    rows_out: int = 0
    duplicates: int = 0
    bad_dates: list[str] = field(default_factory=list)
    empty_text: int = 0
    missing_kol: int = 0

    def __str__(self) -> str:
        return (f"in={self.rows_in} out={self.rows_out} dupes={self.duplicates} "
                f"bad_dates={self.bad_dates} empty_text={self.empty_text} "
                f"missing_kol={self.missing_kol}")


def clean_crm_export(csv_text: str) -> tuple[list[dict], CleanReport]:
    """Deduplicate, normalise dates and names, and REPORT what you dropped.

    The report is the point. A silent cleaner that drops 4% of rows for a reason
    nobody logged is how data pipelines rot. Chapter 6 alerts on these counts.
    """
    rep = CleanReport()
    seen: set[tuple] = set()
    out: list[dict] = []
    for row in csv.DictReader(io.StringIO(csv_text)):
        rep.rows_in += 1
        note_id = (row.get("note_id") or "").strip()
        text = (row.get("notes") or "").strip()
        if text.upper() in ("", "N/A", "NA", "NONE", "-"):
            rep.empty_text += 1
            continue
        d = parse_date(row.get("date", ""))
        if d is None:
            rep.bad_dates.append(row.get("date", ""))
            continue
        kol = (row.get("kol") or "").strip()
        if not kol:
            rep.missing_kol += 1
        key = (note_id, d.isoformat(), text)
        if key in seen:
            rep.duplicates += 1
            continue
        seen.add(key)
        out.append({"note_id": note_id, "date": d.isoformat(),
                    "msl": normalise_person(row.get("msl", "")),
                    "kol": kol, "text": text})
    rep.rows_out = len(out)
    return out, rep


# ---------------------------------------------------------------------------
# Whitespace / chunking
# ---------------------------------------------------------------------------
def normalise_whitespace(text: str) -> str:
    text = text.replace(" ", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(l.rstrip() for l in text.split("\n")).strip()


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    meta: dict = field(default_factory=dict)


HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.M)


def chunk_markdown(doc_id: str, text: str, meta: dict | None = None,
                   max_chars: int = 1400, overlap_chars: int = 150) -> list[Chunk]:
    """Section-aware chunking: split on headings first, only then on size.

    Every chunk keeps its heading path prefixed to the text. This is the cheapest
    retrieval improvement available: a chunk that reads
    'Results > Histologic remission at week 52 was 33.7%' is findable; a chunk that
    reads '33.7%' is not.
    """
    meta = dict(meta or {})
    positions = [(m.start(), len(m.group(1)), m.group(2).strip())
                 for m in HEADING.finditer(text)]
    sections: list[tuple[str, str]] = []
    if not positions:
        sections = [("", text)]
    else:
        if positions[0][0] > 0:
            sections.append(("", text[: positions[0][0]]))
        for i, (start, level, title) in enumerate(positions):
            end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
            body = text[start:end]
            body = HEADING.sub("", body, count=1).strip()
            path = title
            for j in range(i - 1, -1, -1):
                if positions[j][1] < level:
                    path = f"{positions[j][2]} > {path}"
                    level = positions[j][1]
            sections.append((path, body))

    chunks: list[Chunk] = []
    n = 0
    for path, body in sections:
        body = body.strip()
        if not body:
            continue
        prefix = f"{path}\n" if path else ""
        for piece in _split_by_size(body, max_chars - len(prefix), overlap_chars):
            n += 1
            chunks.append(Chunk(
                chunk_id=f"{doc_id}#c{n}", doc_id=doc_id,
                text=(prefix + piece).strip(),
                meta={**meta, "section": path},
            ))
    return chunks


def _split_by_size(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    paras = re.split(r"\n\s*\n", text)
    out, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= max_chars:
            cur = f"{cur}\n\n{p}" if cur else p
        else:
            if cur:
                out.append(cur)
            if len(p) <= max_chars:
                cur = (out[-1][-overlap:] + "\n\n" + p) if out and overlap else p
            else:
                for i in range(0, len(p), max_chars - overlap):
                    out.append(p[i:i + max_chars])
                cur = ""
    if cur:
        out.append(cur)
    return [o.strip() for o in out if o.strip()]
