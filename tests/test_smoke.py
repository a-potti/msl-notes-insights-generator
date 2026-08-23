"""Deterministic tests — no API key, no network, no model download.

    INSIGHTHUB_EMBED_BACKEND=hash pytest tests -q

These cover the parts of the system that CAN be tested with equality assertions.
Everything involving a model is tested statistically by the eval suite instead
(Chapter 5), which is the distinction the whole tutorial is about.
"""
import os

os.environ.setdefault("INSIGHTHUB_EMBED_BACKEND", "hash")

import pytest  # noqa: E402

from insighthub import corpus, docs, guardrails  # noqa: E402
from insighthub.evals.code_evals import run_code_evals  # noqa: E402
from insighthub.evals.matching import match_insights  # noqa: E402
from insighthub.index import BM25, meta_filter, notes_index, tokenize  # noqa: E402
from insighthub.semantic import KolQuery, query_kols, run_query_kols_tool  # noqa: E402


# --- corpus ---------------------------------------------------------------
def test_corpus_loads():
    notes = corpus.load_notes()
    assert len(notes) == 140
    assert all(n.note_id.startswith("NOTE-") for n in notes)
    assert {n.split for n in notes} == {"dev", "test", "holdout"}


def test_note_body_strips_identifying_header():
    n = corpus.get_note("NOTE-0001")
    assert n.kol_name not in n.body
    assert n.institution not in n.body


def test_taxonomy_and_schema_stay_in_sync():
    from insighthub.extract import extraction_tool
    tool = extraction_tool()
    enum = tool["input_schema"]["properties"]["insights"]["items"][
        "properties"]["category"]["enum"]
    assert set(corpus.category_names()) <= set(enum)


# --- documents ------------------------------------------------------------
def test_html_preserves_table_structure():
    html = corpus.load_notes and (corpus.FACT_BASE_PATH if False else None)
    from insighthub.config import RAW_DIR
    text = docs.html_to_text((RAW_DIR / "publication_page.html").read_text())
    assert "[TABLE]" in text
    assert "Clinical remission | 68.1% | 61.2%" in text
    assert "Accept all" not in text          # cookie banner gone
    assert "Subscribe today" not in text     # advert gone


def test_ocr_repair_fixes_damage_without_corrupting_clean_text():
    from insighthub.config import RAW_DIR
    fixed = docs.repair_ocr((RAW_DIR / "ocr_call_note.txt").read_text())
    assert "NOTE-0141" in fixed
    assert "biologic looks good" in fixed
    assert "Interaction type" in fixed        # not turned into 'lnteraction'
    # and it must be a no-op on text that was never damaged
    changed = [n.note_id for n in corpus.load_notes()[:40]
               if docs.repair_ocr(n.text) != n.text]
    assert changed == []


def test_crm_cleaner_reports_what_it_dropped():
    from insighthub.config import RAW_DIR
    rows, rep = docs.clean_crm_export((RAW_DIR / "crm_export_dirty.csv").read_text())
    assert rep.rows_in == 5
    assert rep.rows_out < rep.rows_in
    assert rep.empty_text >= 1
    assert all(r["date"].count("-") == 2 for r in rows)


def test_chunking_prefixes_heading_path():
    d = corpus.load_publications()[0]
    chunks = docs.chunk_markdown(d["doc_id"], d["text"])
    assert len(chunks) > 1
    assert any("Results" in c.meta["section"] for c in chunks)
    assert all(c.chunk_id.startswith(d["doc_id"]) for c in chunks)


# --- retrieval ------------------------------------------------------------
def test_bm25_ranks_the_obvious_document_first():
    ix = notes_index().build(verbose=False)
    hits = ix.keyword_search("prior authorisation step edit payer", 5)
    assert hits
    top = " ".join(h.doc.text.lower() for h in hits[:3])
    assert any(t in top for t in ("authoris", "payer", "step edit", "pa require"))


def test_filters_are_applied_before_topk():
    ix = notes_index().build(verbose=False)
    where = meta_filter(region="EMEA", since="2026-03-01")
    for h in ix.hybrid_search("durability", 10, where=where):
        assert h.doc.meta["region"] == "EMEA"
        assert h.doc.meta["date"] >= "2026-03-01"


def test_index_roundtrip():
    from insighthub.index import Index
    ix = notes_index().build(verbose=False)
    ix.save("pytest")
    again = Index.load("pytest")
    assert len(again.docs) == len(ix.docs)
    assert again.vector_search("durability", 3)


def test_bm25_scores_are_nonnegative():
    b = BM25([tokenize("alpha beta"), tokenize("beta gamma gamma")])
    assert (b.scores("gamma") >= 0).all()


# --- semantic layer -------------------------------------------------------
def test_kol_query_filters_compose():
    df = query_kols(KolQuery(region="EMEA", tier=1))
    assert (df["region"] == "EMEA").all()
    assert (df["tier"] == 1).all()


def test_kol_tool_clamps_limit():
    out = run_query_kols_tool({"limit": 10_000})
    assert out["n_rows"] <= 40


# --- guardrails -----------------------------------------------------------
def test_ae_gate_is_high_recall():
    gold = {g["note_id"]: g for g in corpus.load_gold()}
    notes = corpus.load_notes()
    tp = fn = 0
    for n in notes:
        truth = "ADVERSE_EVENT" in gold[n.note_id]["flags"]
        pred = guardrails.lexical_gate(n.body).adverse_event
        tp += pred and truth
        fn += (not pred) and truth
    recall = tp / max(tp + fn, 1)
    assert recall >= 0.85, f"AE gate recall dropped to {recall:.3f}"


def test_injection_detection_finds_the_planted_notes():
    gold = {g["note_id"]: g for g in corpus.load_gold()}
    found = {n.note_id for n in corpus.load_notes()
             if guardrails.detect_injection(n.body)[0]}
    planted = {nid for nid, g in gold.items() if g["contains_injection"]}
    assert planted <= found


def test_redaction_removes_named_hcps():
    names = [k["name"] for k in corpus.load_kols()[:3]]
    text = f"{names[0]} said the onset was slow."
    assert names[0] not in guardrails.redact_attribution(text, names)


# --- evals ----------------------------------------------------------------
def test_code_evals_catch_a_bad_verbatim():
    row = {"note_id": "NOTE-0001", "suspicious": False, "insights": [{
        "verbatim": "this string is definitely not in the note",
        "insight": "A clinician raised a concern about durability of response.",
        "category": "EFFICACY_REAL_WORLD", "sentiment": "neutral",
        "flags": [], "strategic_priority": "SP1", "confidence": 0.9}]}
    res = run_code_evals([row])[0]
    assert any(c.name == "verbatim_is_substring" and not c.passed for c in res.checks)
    assert res.blocking_failures


def test_code_evals_catch_overgeneralisation():
    row = {"note_id": "NOTE-0001", "suspicious": False, "insights": [{
        "verbatim": corpus.get_note("NOTE-0001").body[:40],
        "insight": "All clinicians nationally report slower onset than expected.",
        "category": "EFFICACY_REAL_WORLD", "sentiment": "negative",
        "flags": [], "strategic_priority": "SP1", "confidence": 0.9}]}
    res = run_code_evals([row])[0]
    assert any(c.name == "no_overgeneralisation" and not c.passed for c in res.checks)


def test_matching_is_one_to_one():
    gold = [{"seed_id": "S01", "canonical": "onset is slower than expected"},
            {"seed_id": "S02", "canonical": "durability beyond one year is unclear"}]
    m = match_insights(["onset is slower than expected",
                        "onset is slower than expected"], gold, threshold=0.5)
    assert m.tp <= len(gold)
    assert len(m.matched) == len({g for _, g, _ in m.matched})


# --- observability --------------------------------------------------------
def test_psi_is_zero_for_identical_distributions():
    from insighthub.observability import population_stability_index
    a = ["x"] * 10 + ["y"] * 5
    assert population_stability_index(a, a) == pytest.approx(0.0, abs=1e-6)
    assert population_stability_index(a, ["y"] * 15) > 0.25
