# Chapter 3 — Grounding models with data

*You will build: `docs.py`, `embed.py`, `index.py`, `semantic.py`, `themes.py`,
`retrieval_eval.py` — a document pipeline, a vector index written from scratch, hybrid
search, a semantic layer over structured KOL data, a small knowledge graph, and the
evaluation that tells you whether any of it helped.*
*Time: ~6 hours. API spend: ~$2.*

**The skill:** knowing the *menu*. RAG-with-a-vector-store is one item on it. Choosing
the wrong representation for your data is the most expensive mistake in this chapter, and
the one nobody measures because they never built the alternative.

---

## 3.1 The menu, and how to choose from it

Six ways to get information in front of a model. Every real system uses several.

| Technique | Good for | Bad for | Where in InsightHub |
|---|---|---|---|
| **Put it in the prompt** | Small, stable, needed every time | Anything that grows | Taxonomy, fact base, output rules |
| **Vector search** | "Things that mean roughly this" | Exact IDs, numbers, dates, negation | Finding insights across paraphrases |
| **Lexical search (BM25)** | Exact terms, drug names, trial IDs, rare words | Synonyms, paraphrase | `AURORA-2`, `Geboes`, `calprotectin` |
| **Metadata filters** | Time windows, regions, tiers, types | Meaning | "since ECCO", "EMEA tier-1" |
| **Semantic layer over structured data** | Counting, comparing, aggregating, set operations | Free-text nuance | KOL coverage, engagement gaps |
| **Graph** | Relationships and multi-hop questions | Bulk similarity | KOL ↔ theme ↔ evidence links |

The decision procedure, applied to a real question:

> *"Which EMEA tier-1 KOLs have raised concerns about durability since ECCO, and what
> evidence do we have to answer them?"*

Decompose it:
- `EMEA`, `tier-1` → **metadata filter / semantic layer**. An embedding does not know what
  tier 1 is.
- `since ECCO` (2026-02-18) → **date filter**. Embeddings have no concept of "since".
- `concerns about durability` → **vector search**. Notes say "week 104", "year one",
  "every biologic looks good at 52 weeks" — no shared keyword.
- `what evidence do we have` → **search a different corpus** (abstracts/publications), then
  **graph** to link theme → evidence.

Four techniques, one question. Any system built on only one of them answers it badly. The
skill is doing this decomposition automatically.

---

## 3.2 Documents in, LLM-ready text out

`data/raw/` has four inputs chosen because each breaks something.

### HTML: the content is 15% of the file

```python
from insighthub.docs import html_to_text
from insighthub.config import RAW_DIR
print(html_to_text((RAW_DIR / "publication_page.html").read_text()))
```

`html_to_text` strips `script`/`nav`/`footer`, drops elements whose id or class smells of
cookie banners and adverts, and — the part that matters —

```python
for table in soup.find_all("table"):
    rows = [" | ".join(c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"]))
            for tr in table.find_all("tr")]
    table.replace_with("\n[TABLE]\n" + "\n".join(rows) + "\n[/TABLE]\n")
```

**Why the table handling is the important line.** `BeautifulSoup.get_text()` flattens

| Endpoint | Week 52 | Week 104 |
|---|---|---|
| Clinical remission | 68.1% | 61.2% |

into `Endpoint Week 52 Week 104 Clinical remission 68.1% 61.2%`. A model reading that has
no way to bind 61.2% to week 104, and it will confidently guess. In a system whose output
reaches medical directors, a number bound to the wrong timepoint is the single most
damaging error you can ship. Preserve tabular structure or drop tables entirely — never
flatten them.

### PDF: text layer, or vision?

```python
from insighthub.docs import pdf_to_text, looks_like_scan
text = pdf_to_text(RAW_DIR / "ecco2026_abstract_P0412.pdf")
print(looks_like_scan(text, n_pages=1), len(text))
```

Our abstract has a real text layer, so extraction is right and costs nothing.
`ddw2026_poster_Sa1187.png` has numbers that exist only as pixels in a bar chart, so it
needs vision (Chapter 1 §1.10). The routing rule:

```
extract text -> if < ~120 chars/page, it's a scan -> send the page image to a vision model
             -> if it has figures whose numbers you need -> send those regions too
```

Always try extraction first. It's free, exact, and 10× cheaper in tokens.

### OCR damage: the section where the obvious approach is wrong

`data/raw/ocr_call_note.txt` has classic scanner confusions: `l`→`I`, `0`→`O`, `I`→`|`.

The obvious fix is a substitution list:

```python
text = text.replace("|", "I").replace("O", "0")     # DON'T
```

Try it. `Interaction` becomes `lnteraction`, and the `|` characters that are legitimate
field separators in the header become `I`. You have traded one corruption for another and
made the second one harder to spot.

`repair_ocr` uses three rules in priority order:

1. **A token already in the lexicon is never touched.** This alone prevents most damage.
2. **Schema-shaped tokens are digitised.** `NOTE-Ol4l` → `NOTE-0141`, because we know our
   IDs are `PREFIX-digits`. Knowing your own data beats any general-purpose repair.
3. **Otherwise, a character bigram model** learnt from the clean corpus picks the best
   candidate — *with case preserved*, because the entire signal in `Iooks` is that a
   capital `I` sits before a lowercase letter, which essentially never happens in English.
   Lowercase your corpus and you delete the evidence you were about to use.

```python
from insighthub.docs import repair_ocr
print(repair_ocr((RAW_DIR / "ocr_call_note.txt").read_text()))
```

```
MSL Call Note  |  NOTE-0141
Date: 2026-03-11  |  MSL: A. Ferreira (MSL-04)  |  Region: EMEA
...
every biologic looks good at 52 weeks.
Two of his patients lost response at about month 10.
```

And the check that matters more than the repair:

```python
from insighthub.corpus import load_notes
changed = [n.note_id for n in load_notes() if repair_ocr(n.text) != n.text]
print("false repairs on clean text:", len(changed))     # 0
```

**Always measure a cleaner in both directions.** How much damage did it fix, and how much
did it cause? A cleaner that fixes 90% of errors while corrupting 2% of clean tokens is
usually a net loss, and nobody notices because only the first number gets reported.

### Dirty CSV: clean loudly

```python
from insighthub.docs import clean_crm_export
rows, report = clean_crm_export((RAW_DIR / "crm_export_dirty.csv").read_text())
print(report)     # in=5 out=2 dupes=0 bad_dates=[] empty_text=3 missing_kol=1
```

Three date formats, a `"Ferreira, A."` vs `"A. Ferreira"` name inconsistency, an exact
duplicate row, an `N/A` text field and an impossible date (`2026-13-45`). The
`CleanReport` is the point: **a silent cleaner is a liability.** Chapter 6 alerts when
`empty_text` or `bad_dates` moves, because a spike there means an upstream system
changed and your pipeline is quietly eating data.

---

## 3.3 Chunking

For **call notes**: don't chunk. They're ~95 tokens. One note = one chunk. Splitting a
120-word note produces fragments that are individually meaningless, and the retrieval
literature's chunking advice is written for 40-page documents, not for a paragraph.

*Do the cheapest thing that works.* An enormous amount of RAG complexity is people
applying advice from a different problem shape.

For **abstracts and publications**, `chunk_markdown` splits on headings first and only
then on size, and prefixes each chunk with its heading path:

```
PUB-001#c4  [Two-year maintenance of remission with zoltarimab > Results]
            "...61.2% maintained clinical remission at week 104..."
```

The heading path is the cheapest retrieval improvement available. A chunk that reads
`Results > Histologic remission at week 52 was 33.7%` is findable and interpretable. A
chunk that reads `33.7%` is neither.

```python
from insighthub.docs import chunk_markdown
from insighthub.corpus import load_publications
d = load_publications()[0]
for c in chunk_markdown(d["doc_id"], d["text"], {"journal": d["journal"]}):
    print(c.chunk_id, "|", c.meta["section"], "|", len(c.text))
```

---

## 3.4 Embeddings, without the magic

An embedding maps text to a vector such that similar meanings land near each other. That
is the whole idea. Look at it directly:

```python
from insighthub.embed import embed_texts
import numpy as np

texts = [
    "He said his first four patients took closer to 8 weeks to improve.",
    "Feels the onset is slower than advertised - 6 to 8 weeks in practice.",
    "PA requires two prior advanced therapy failures at both his major payers.",
    "Parking at the medical centre is a nightmare.",
]
X = embed_texts(texts)
print(X.shape)              # (4, 384)
print(np.round(X @ X.T, 3)) # cosine similarity; vectors are L2-normalised
```

```
[[1.000 0.79  0.21  0.06]
 [0.79  1.000 0.19  0.04]
 [0.21  0.19  1.000 0.11]
 [0.06  0.04  0.11  1.000]]
```

*(Your numbers will differ by model.)* Sentences 0 and 1 share almost no vocabulary —
"four patients", "8 weeks" vs "onset", "advertised" — and score 0.79. That is the thing
BM25 cannot do, and §3.6 shows exactly where it costs us.

Three practical points:

1. **Normalise, then cosine is a dot product.** `embed_texts` returns L2-normalised
   vectors, which is why the search in `index.py` is one line: `self.vectors @ q`.
2. **Cache aggressively.** `embed.py` caches to `index/embed_cache_*.npz` keyed by a hash
   of the text. Re-embedding 6,000 notes on every run is slow and, on a hosted embedding
   API, expensive.
3. **Changing the embedding model invalidates every vector you have.** Vectors from
   different models are not comparable, not even slightly. Version your index by model
   name and rebuild on change — §3.12. This is the RAG bug people lose a day to.

> **A note on the backend.** The default is a small local model
> (`all-MiniLM-L6-v2`, ~90 MB) so you can see this work without another API key. There is
> also `INSIGHTHUB_EMBED_BACKEND=hash`, a deterministic non-semantic embedder used by the
> test suite so CI runs without a model download. If your retrieval numbers look strangely
> bad, check that variable — the whole point of it is that the failure is obvious.

---

## 3.5 A vector index in forty lines

```python
def vector_search(self, query, k=5, where=None):
    q = embed_one(query)
    sims = self.vectors @ q                      # <- the entire algorithm
    sims = np.where(self._allowed(where), sims, -np.inf)
    idx = np.argpartition(-sims, k)[:k]
    return [Hit(self.docs[i], float(sims[i]), "vector")
            for i in idx[np.argsort(-sims[idx])]]
```

That is brute-force exact search. On 6,000 notes × 384 dimensions it is a 2.3M-element
dot product — well under a millisecond. **You do not need a vector database.**

You will need one when: you pass roughly a million chunks (memory), you need
sub-millisecond filtered search under concurrency, you need the index shared across
processes, or you want managed replication. Approximate nearest-neighbour indexes trade a
little recall for a lot of speed — a trade that is free at our scale because we aren't
paying the speed cost.

Build it:

```python
from insighthub.index import notes_index, evidence_index
notes = notes_index().build()
notes.save("notes")
evidence = evidence_index().build()
evidence.save("evidence")

for h in notes.vector_search("clinicians worried about durability past a year", 5):
    print(h, h.doc.text[:80].replace("\n", " "))
```

---

## 3.6 BM25, and the queries that prove you need it

Lexical search is not the thing you outgrew. It is a different tool.

`index.py` implements Okapi BM25 in forty lines:

```
score(q,d) = SUM_t IDF(t) · f(t,d)·(k1+1) / (f(t,d) + k1·(1 − b + b·|d|/avgdl))
```

`k1` saturates term frequency (a word ten times is not ten times as relevant); `b`
controls length normalisation. Leave both at the defaults.

Now evaluate it on the 30 labelled queries in `data/eval/retrieval_queries.jsonl`:

```bash
PYTHONPATH=src python scripts/ch3_retrieval_eval.py
```

Measured, BM25 only:

| k | recall | precision | MRR | nDCG | recall 95% CI |
|---|---|---|---|---|---|
| 5 | 0.349 | 0.573 | 0.800 | 0.646 | [0.25, 0.45] |
| 10 | 0.468 | 0.417 | 0.806 | 0.599 | [0.36, 0.58] |
| 20 | 0.602 | 0.302 | 0.806 | 0.628 | [0.49, 0.72] |
| 30 | 0.647 | 0.231 | 0.806 | 0.642 | [0.54, 0.75] |

MRR of 0.806 means the *first* relevant note is usually in the top two. But recall at 10
is 0.468 — we're missing half of what's relevant, and for insight aggregation recall is
what matters. Finding one note saying "durability is a concern" is nearly useless; the
job is to find *all twenty* so the theme's size is right.

**Now look at the failures, which is where the actual information is:**

```
Q-011 recall=0.00  n_rel=6   "Interest in extraintestinal manifestations"
Q-027 recall=0.00  n_rel=6   "Device usability problems for older patients"
Q-029 recall=0.03  n_rel=39  "Everything clinicians have asked for that we lack data on"
Q-030 recall=0.12  n_rel=51  "What is driving physicians away toward competitors?"
Q-001 recall=0.13  n_rel=15  "What are physicians saying about how quickly patients respond?"
```

Two distinct failure modes, and they need different fixes:

- **Zero lexical overlap (Q-011, Q-027, Q-001).** The notes say *joint symptoms*,
  *arthralgia*, *autoinjector*, *plunger*, *activation force*, *8 weeks*, *anxious at week
  5*. The queries say *extraintestinal manifestations*, *device usability*, *how quickly*.
  BM25 has nothing to match on. **This is what embeddings are for.**
- **Abstract multi-topic queries (Q-029, Q-030).** "Everything we lack data on" spans four
  themes and 39 notes. No single retrieval call should be expected to answer it. **This
  needs decomposition into sub-queries — which is Chapter 4's agent, not a retrieval
  tuning problem.**

Distinguishing those two is the skill. The first is fixable in the index; the second is
not, and you can burn a week tuning `k1` trying.

> ### 🛑 Stop and look
> Run `evaluate(...).worst(8)` and read the `missed` note IDs for Q-011. Open two of those
> notes. Convince yourself with your own eyes that no keyword system could have found
> them. Then predict — before running it — what vector search will do to Q-011 and to
> Q-029. Write your prediction down. Being able to predict which technique fixes which
> failure is the entire content of this chapter.

---

## 3.7 Hybrid retrieval with Reciprocal Rank Fusion

Add vector search and fuse:

```python
for h in notes.hybrid_search("device problems for older patients", 5):
    print(h)     # Hit(NOTE-0071, 0.0325, bm25+vector)
```

RRF fuses **ranks**, not scores:

```
RRF(d) = SUM over rankers of  1 / (rrf_k + rank_of_d_in_that_ranker)
```

A cosine similarity of 0.42 and a BM25 score of 11.3 are not on comparable scales, and any
weighted sum of them is a fudge factor you will spend a week tuning and then never touch
again. Ranks are always comparable. `rrf_k=60` comes from the original paper and is almost
never worth changing.

Now run the eval for all three retrievers at k=10 and k=20 and fill in your own table:

| retriever | recall@10 | recall@20 | MRR |
|---|---|---|---|
| BM25 | 0.468 | 0.602 | 0.806 |
| vector | *your number* | | |
| hybrid | *your number* | | |

**Do not assume hybrid wins.** RRF fuses whatever you give it, including a bad ranker. If
your vector search underperforms — wrong model, un-normalised vectors, the `hash` backend
left on — hybrid will land *between* the two, worse than BM25 alone. Verify each component
separately before fusing, and if hybrid does not beat both, the fusion is not the problem.

---

## 3.8 Filters: what embeddings fundamentally cannot do

```python
from insighthub.index import meta_filter
f = meta_filter(region="EMEA", kol_tier=1, since="2026-02-18")
for h in notes.hybrid_search("durability concerns", 10, where=f):
    print(h.doc.doc_id, h.doc.meta["date"], h.doc.meta["region"])
```

Embeddings encode meaning. They do not encode *since February 18th*, *tier 1*, or *not*.
Three consequences worth internalising:

- **Negation is invisible.** "Patients who did NOT respond" and "patients who responded"
  embed almost identically. If negation matters, filter or ask the model, don't search.
- **Numbers and dates are noise.** `week 52` and `week 104` are near-identical vectors.
  If your query hinges on which number, use lexical search or structured fields.
- **Filter before you search, not after.** Retrieving top-10 then filtering to EMEA can
  leave you with two results. `index.py` masks before the top-k selection.

---

## 3.9 A semantic layer over structured data — and why not text-to-SQL

*"Which tier-1 EMEA KOLs on a guideline committee have we not seen since ECCO?"*

That is a query, not a search. `semantic.py` answers it:

```python
from insighthub.semantic import KolQuery, query_kols
print(query_kols(KolQuery(tier=1, region="EMEA", guideline_committee=True,
                          not_seen_since="2026-02-18", order_by="influence_score")))
```

The tempting alternative is to let the model write SQL. In a Medical Affairs system,
don't:

- SQL injection stops being a metaphor once a model composes the string, and the string
  can come from a call note (see the injection in Chapter 4 §4.9).
- A model that can express *any* query can express `SELECT * FROM kols`. Bulk KOL
  extraction is precisely the exfiltration path governance exists to prevent.
- You cannot write tests for "all the SQL the model might emit". You can write tests for
  fourteen named parameters.

A **semantic layer** is a small vocabulary of business terms — dimensions, measures,
flags — mapped onto columns and predicates, exposed as a parameterised tool:

```python
DIMENSIONS = {"region": "region", "tier": "tier", ...}
MEASURES   = {"interaction_count": "number of call notes recorded with this KOL", ...}
FLAGS      = {"guideline_committee": "sits on a guideline committee", ...}
```

Three things you get, in order of importance: **the query space is enumerable** (so
testable, so auditable); **the blast radius is bounded** (`limit` is clamped to 40 in
`run_query_kols_tool`, and no free text is returned); and — the surprise — **the model is
better at it**. The parameter names and descriptions *are* the semantics. The model no
longer has to infer that `tier` means influence, or that "haven't seen" means
`MAX(date) < X`. You told it.

This generalises well beyond KOLs. Any time you're tempted by text-to-SQL over a database
you care about, ask what the twenty questions people actually ask are, and expose those as
parameters instead.

---

## 3.10 A graph, where a graph earns its place

Vector indexes answer "what is similar to this". They cannot answer "which people raised
*both* of these things" — that's a relationship question.

`themes.Graph` is forty lines of dict-of-sets over `(kol → theme)` and
`(theme → evidence)`:

```python
g.co_occurring_themes("T-004", min_shared=2)
# [('T-011', 5), ('T-002', 3)]
g.unsupported_themes()
# themes with no linked evidence -> the medical strategy gap list
```

Two questions this makes trivial and a vector index makes impossible:

- *"The KOLs worried about durability — are they the same ones asking for therapeutic drug
  monitoring?"* If yes, that is one strategic story (uncertainty about long-term
  management), not two, and it changes what the medical plan should do.
- *"Which themes have no supporting evidence in our publication set?"* That list is
  literally the evidence-generation plan for next year. It is the highest-value output of
  the entire system and it comes from a set difference.

**When to reach for a real graph database:** variable-length paths, transitive closure,
shortest-path or centrality over a large graph, or a graph too big for memory. Two-hop
questions over ten thousand nodes are a dict.

---

## 3.11 The experiment you must run: retrieval vs just sending everything

Chapter 1 §1.3 established that our whole corpus is ~31k tokens and fits in context. So
before believing in retrieval, measure it.

```bash
PYTHONPATH=src python scripts/ch3_longcontext_vs_rag.py --n 12
```

The script answers ten analyst questions three ways and asks a judge to score groundedness
and completeness:

| Condition | Input tokens/query | Cost/query | p50 latency | Quality |
|---|---|---|---|---|
| All 140 notes in the prompt | ~16,000 | *yours* | *yours* | *yours* |
| Hybrid retrieval, k=10 | ~1,200 | *yours* | *yours* | *yours* |
| Hybrid retrieval, k=30 | ~3,400 | *yours* | *yours* | *yours* |

Likely outcome at *this* corpus size: long-context is competitive or slightly better on
quality and roughly 12× more expensive. Which means the honest justification for retrieval
here is **not** accuracy — it is the growth argument from Chapter 1 (6,000 notes/year), the
cost curve, and latency.

Say that out loud, because a lot of RAG in production exists for no reason anybody ever
measured. And note the corollary: **as context windows grow, the accuracy argument for
retrieval keeps weakening while the cost argument does not.** Design accordingly — keep
retrieval behind an interface so that "retrieve k=10" and "send the last 200 notes" are
one config change apart.

> **A word of caution before you trust your first run of this script.** Our first attempt
> showed `all-140-notes` scoring *far* worse than either retrieval condition (near-floor on
> both groundedness and completeness) — the opposite of "competitive." The cause wasn't
> retrieval at all: the script's `answer()` call used a fixed `max_tokens` too small for
> this model tier's adaptive thinking, which counts against that budget and can consume all
> of it on a large context before any answer text is emitted — silently producing an empty
> answer that the judge correctly scored at the floor. After fixing `max_tokens`, the result
> flipped to match this section's expected direction (long-context wins on quality; real
> cost ratios were ~2-4x, not exactly 12x). If your own long-context condition looks
> unreasonably bad, check `stop_reason` on that call before concluding anything about
> retrieval. Full trace in D-024 (`DECISIONS.md`).

---

## 3.12 Keeping data fresh

Ingestion is a pipeline with four properties that are annoying to retrofit:

1. **Incremental.** Process new notes only. Key on a content hash, not a filename — MSLs
   edit notes after the fact.
2. **Idempotent.** Re-running must not duplicate. Chunk IDs are derived
   (`{doc_id}#c{n}`), never auto-incremented.
3. **Versioned.** Store the embedding model name, prompt version and taxonomy version with
   every record. When you change the embedding model you must rebuild; if you can't tell
   which vectors came from which model, you have to rebuild everything, and you will
   discover this at the worst time.
4. **Observable.** Emit counts at every stage — notes in, chunks out, rows dropped and
   why. Chapter 6 alerts on the ratios.

```python
INDEX_VERSION = {
    "embed_model": "all-MiniLM-L6-v2",
    "chunker": "chunk_markdown@1400/150",
    "taxonomy": "v1",
    "prompt": "extract-v1",
}
```

Store that dict alongside the index. When retrieval quality changes overnight, the first
question is "what version is running?", and you want it to take five seconds to answer.

---

## 3.13 From insights to themes

Now assemble Chapter 2 §2.10's idea with real embeddings:

```python
from insighthub.themes import cluster, choose_k, name_themes
from insighthub.extract import load
from insighthub.embed import embed_texts

rows = load("runs/ch1_dev_v1.jsonl")
items = [(f"{r['note_id']}#{i}", ins["insight"])
         for r in rows for i, ins in enumerate(r["insights"])]
ids, texts = zip(*items)

X = embed_texts(list(texts))
for k, sil in choose_k(X, 4, 20):
    print(k, round(sil, 3))                  # read the curve, don't obey it

themes = cluster(list(texts), list(ids), method="agglom")   # threshold-based, no k
themes = name_themes(themes)                                # the LLM's one job

for t in themes[:10]:
    print(f"[{t.size:3d}] {t.name}")
    print(f"      {t.summary}")
    if not t.meta.get("coherent", True):
        print(f"      ⚠ model says this cluster is incoherent: {t.meta['outlier_idx']}")
```

Three design choices worth arguing with:

- **Agglomerative with a distance threshold, not k-means.** Insight themes have wildly
  uneven sizes: 40 notes about durability, 2 about pouchitis. k-means forces equal-ish,
  round clusters and will split the big theme while burying the singleton. And the
  singleton may be the most valuable thing in the quarter — a genuinely novel observation
  from one KOL. **An algorithm that must assign everything to a cluster destroys exactly
  the signal you most want.**
- **The LLM is a quality gate, not just a namer.** `name_theme` returns `coherent` and
  `outliers`. When the model says a cluster isn't one thing, believe it and re-cluster —
  a false theme in a quarterly report is worse than a missing one, because it gets acted
  on.
- **Theme *names* carry substance.** "Efficacy" is a category. "Onset slower in practice
  than AURORA-1 curves imply" is a finding. A medical director should be able to read
  twelve theme names and know what each is without opening it.

---

## 3.14 Decision log

- **D-015 Chunking.** Notes unchunked (~95 tokens each); evidence chunked by section with
  heading paths prefixed. Rationale: chunking advice written for 40-page PDFs does not
  apply to a paragraph.
- **D-016 Retrieval.** Hybrid RRF over BM25 + vectors, with metadata pre-filtering.
  BM25-only recall@10 = 0.468, failing completely on paraphrase queries (Q-011, Q-027 at
  0.00).
- **D-017 Structured data.** Semantic layer, not text-to-SQL. Reasons: enumerable query
  space, bounded blast radius, better model accuracy.
- **D-018 Long context.** Measured retrieval against sending all 140 notes. *(Record your
  numbers.)* Retrieval justified on cost and growth, not accuracy, at this corpus size.
- **D-019 Clustering.** Agglomerative with a distance threshold over k-means, to preserve
  singleton insights. LLM names clusters and gates coherence; it does not find them.
- **D-020 Index versioning.** Embedding model, chunker config, taxonomy and prompt version
  stored with the index; changing the embedding model forces a rebuild.

---

## 3.15 Exercises

1. **Predict, then measure.** Before running vector search on Q-011 and Q-029, write down
   what you expect. Run it. Where were you wrong, and what does that tell you about your
   mental model of embeddings?
2. **Query expansion.** For Q-029 ("everything we lack data on"), have an LLM decompose it
   into 4 sub-queries, retrieve each, and union the results. How much recall do you gain?
   Is this cheaper or more expensive than raising k to 40? (This is a preview of Chapter
   4 — decomposition is an agent behaviour, not a retrieval parameter.)
3. **Break the cleaner.** Add `1`→`l` to `CONFUSIONS` and re-run the false-repair check on
   the 140 clean notes. How many correct tokens does it now corrupt? Plot repairs gained
   against corruptions introduced as you raise `min_gain` from 0 to 6.
4. **The table trap.** Feed a model the flattened (non-`[TABLE]`) version of the
   publication HTML and ask "what was the clinical remission rate at week 104?" Run it ten
   times. How often does it answer 68.1%?
5. **Fill in Chapter 2 §2.9.** Embeddings + logistic regression, grouped CV, on
   `insight_text_archive.csv`. Where does it sit between TF-IDF and the LLM?
6. **Index versioning, the hard way.** Build the index with one embedding model, then
   change `INSIGHTHUB_EMBED_MODEL` and query *without* rebuilding. Look at the results.
   This failure is silent and it is the reason for D-020.

---

**Next:** [Chapter 4 — Building agentic systems](04-agentic-systems.md) — where the
workflow stops being a straight line, and something starts reading your notes back to you.
