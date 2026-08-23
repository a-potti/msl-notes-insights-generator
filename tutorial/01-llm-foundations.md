# Chapter 1 — LLM foundations

*You will build: `insighthub/llm.py` and `insighthub/extract.py`, and run your first
extraction over all 60 dev notes.*
*Time: ~4 hours. API spend: ~$1.50.*

**The skill:** understanding how the model tokenizes input and generates output, so you
know when to count on it and when it will fail — and so you can reason about context
budget, cache hits, sampling, knowledge cutoff, reasoning effort and tool calling instead
of guessing.

---

## 1.1 The naive version, so you can watch it fail

Start with the version everyone writes first. Put this in `scratch/naive.py`:

```python
import os, anthropic
from insighthub.corpus import get_note

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
note = get_note("NOTE-0009")          # a long advisory-board debrief

resp = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    messages=[{"role": "user",
               "content": f"Extract the insights from this call note:\n\n{note.text}"}],
)
print(resp.content[0].text)
print("---")
print(resp.usage)
```

```bash
PYTHONPATH=src python scratch/naive.py
```

Read what comes back before reading on.

You will see something like this (yours will differ — that's §1.4's subject):

> Here are the key insights from this call note:
>
> 1. **Durability concerns** — The HCP wants to see week 104 data before committing…
> 2. **Trial burden** — The endoscopy schedule in HORIZON-CD is limiting enrolment…
> 3. **MOA discussion** — The MSL walked through the mechanism of action deck…
>
> Let me know if you'd like me to expand on any of these.

Four things are wrong, and each one maps to a section of this chapter:

| Problem | Why | Fixed in |
|---|---|---|
| It's prose. You cannot count, store, or evaluate prose. | No output contract | §1.5 |
| Item 3 is not an insight — it's what the MSL did | No definition of the task | §1.11 |
| You don't know what it cost or how long it took | No instrumentation | §1.2 |
| Run it again and you get a different list | Sampling | §1.4 |

There's a fifth, subtler one: it included the header, so the model saw the KOL's name and
institution. Whether the model's judgement of an insight shifts when it knows the speaker
is a tier-1 professor is a question you now cannot answer, because you confounded it. We
strip headers from here on (`note.body`, not `note.text`).

---

## 1.2 Tokens: what the model actually sees

The model does not see characters or words. It sees **tokens** — sub-word chunks from a
fixed vocabulary. Everything that matters commercially (cost, latency, context limits,
cache thresholds) is denominated in tokens, so you should be able to estimate them for
your own data without thinking.

There is a free endpoint for exact counts:

```python
from insighthub import llm
from insighthub.corpus import get_note

note = get_note("NOTE-0009")
n = llm.count_tokens(messages=[{"role": "user", "content": note.body}])
print(f"{len(note.body):,} chars -> {n:,} tokens ({len(note.body)/n:.2f} chars/token)")
```

Run it over the whole corpus:

```bash
PYTHONPATH=src python scripts/ch1_token_census.py
```

<details>
<summary><code>scripts/ch1_token_census.py</code> — write this yourself first, then compare</summary>

```python
"""How big is our corpus, really?"""
from insighthub import llm
from insighthub.corpus import load_notes, load_evidence, taxonomy_prompt_block, fact_base

def tok(text):
    return llm.count_tokens(messages=[{"role": "user", "content": text}])

notes = load_notes()
note_tokens = [tok(n.body) for n in notes]
print(f"notes: n={len(notes)} total={sum(note_tokens):,} "
      f"median={sorted(note_tokens)[len(notes)//2]:,} max={max(note_tokens):,}")

ev = load_evidence()
ev_tokens = sum(tok(d["text"]) for d in ev)
print(f"evidence docs: n={len(ev)} total={ev_tokens:,}")

print(f"taxonomy block: {tok(taxonomy_prompt_block()):,}")
print(f"fact base:      {tok(fact_base()):,}")
```
</details>

Roughly what you should see:

```
notes: n=140 total=~15,500 median=~95 max=~430
evidence docs: n=42 total=~14,000
taxonomy block: ~1,150
fact base:      ~640
```

Three habits worth forming right now:

1. **English prose is ~3.5–4.5 characters per token.** Good enough for back-of-envelope
   work. Our telegraphic MSL (`pts`, `w/o`, `b/c`) runs *worse* than average, not better —
   unusual abbreviations fragment into more tokens than the words they replace. Check it:
   compare `NOTE-0003` (telegraphic) with a narrative note of the same character length.
2. **Count tokens on real samples, not on a paragraph you made up.** Our notes have
   headers, tables, non-ASCII institution names (`Universitätsklinikum Rheinfeld`) and OCR
   damage. Non-ASCII text is routinely 2–3× the tokens of equivalent English.
3. **Cost is not the interesting number; the ratio is.** Output tokens cost ~5× input
   tokens. A system that reads a lot and writes a little is cheap; one that rewrites its
   input is not. Look at §1.6's table with this in mind.

> ### 🛑 Stop and look
> Find the note with the *worst* chars-per-token ratio and read it. Why is it dense?
> (Hint: look at what OCR did to `data/raw/ocr_call_note.txt` — `l` for `I`, `O` for `0`,
> `|` for `I`. Every one of those corruptions creates rare token sequences.) This is a
> concrete reason document cleanup in Chapter 3 is not busywork: bad OCR costs you money
> *and* accuracy.

---

## 1.3 The context budget — and a result that should surprise you

The received wisdom is "your data doesn't fit in the context window, therefore RAG."
Let's check whether that's true here before we build anything.

- Full note corpus: **~15,500 tokens**
- Full evidence corpus: **~14,000 tokens**
- Taxonomy + fact base: **~1,800 tokens**
- **Total: ~31,000 tokens.** Against a 200k–1M token context window.

*Everything we own fits in a single prompt, roughly six times over.*

So why does Chapter 3 exist? Four honest reasons, in order of when they bite:

1. **Cost per query.** Stuffing 31k tokens into every question at Sonnet's input rate is
   ~$0.06 per question before the model writes a word. A hundred analyst questions a day
   is ~$2,200/year of pure re-reading. Retrieval that sends 3k tokens costs ~$0.006.
2. **Growth.** 8 MSLs × ~15 notes/week × 50 weeks ≈ **6,000 notes/year** ≈ 660k tokens/year
   of notes alone. Our 140 notes are one MSL-month. The architecture you choose now is the
   one you will have at 100×.
3. **Latency.** Time-to-first-token scales with input length. A 31k-token prompt has a
   noticeably worse feel than a 3k-token one, and analysts ask follow-up questions.
4. **Accuracy.** Long contexts degrade — not catastrophically, but measurably — when the
   relevant fact is one line among hundreds of similar-looking lines. Our corpus is
   *adversarial* for this: twenty notes say nearly the same thing about durability in
   twenty different wordings.

**And yet:** for *this* corpus at *this* size, long-context stuffing is a completely
legitimate baseline, and Chapter 3 §3.11 makes you measure retrieval against it. Some
retrieval systems lose to "just send everything." Knowing that, and being willing to
measure it, is what separates an engineer from someone applying a pattern.

The real budgeting decision is not *whether* things fit. It is:

> **What is in the prompt every single time (stable, cacheable), versus what the model
> fetches on demand (variable, query-dependent)?**

For InsightHub:

| Content | Where | Why |
|---|---|---|
| Task instructions | Prompt prefix | Needed every call, never changes |
| Insight taxonomy (~1,150 tok) | Prompt prefix | Needed every call, changes quarterly |
| Product fact base (~640 tok) | Prompt prefix | Needed for grounding; small |
| The note being processed | User message | Varies per call |
| Other notes, abstracts, KOL records | Retrieved (Ch.3) | Only some are relevant to any query |
| Full note corpus | Never in prompt | See growth argument above |

That table is a *decision*, made with numbers, that you should record in `DECISIONS.md`.

---

## 1.4 Sampling: why the same input gives different answers

Run the naive script three times. You will get three different lists.

This is the property Ng identifies as *the* difference between AI software and normal
software, so it is worth watching directly rather than reading about.

The model doesn't emit a token; it emits a probability distribution over the whole
vocabulary, and a sampler picks one. Two knobs:

- **`temperature`** (0–1) scales the distribution before sampling. At 0 you take the most
  likely token every time. At 1 you sample from the distribution as the model produced it.
- **`top_p`** (nucleus sampling) truncates to the smallest set of tokens whose cumulative
  probability exceeds *p*, then samples from those.

Set one or the other, not both. Setting both makes the interaction hard to reason about
and gains you nothing.

Measure the variance on our actual task:

```bash
PYTHONPATH=src python scripts/ch1_sampling.py
```

<details>
<summary><code>scripts/ch1_sampling.py</code></summary>

```python
"""How unstable is extraction, and does temperature=0 fix it?"""
import collections
from insighthub.corpus import get_note
from insighthub.extract import extract_note
from insighthub.config import MODEL_FAST

note = get_note("NOTE-0009")   # 6 seeded insights, long note

for temp in (0.0, 0.3, 1.0):
    counts, texts = [], []
    for _ in range(5):
        e = extract_note(note, model=MODEL_FAST, temperature=temp)
        counts.append(len(e.insights))
        texts.append(tuple(sorted(i["category"] for i in e.insights)))
    identical = len(set(texts)) == 1
    print(f"temp={temp}: counts={counts} "
          f"distinct category-sets={len(set(texts))} identical={identical}")
```
</details>

Typical result:

```
temp=0.0: counts=[6, 6, 6, 5, 6]  distinct category-sets=2  identical=False
temp=0.3: counts=[6, 7, 5, 6, 6]  distinct category-sets=4  identical=False
temp=1.0: counts=[7, 5, 8, 6, 6]  distinct category-sets=5  identical=False
```

Two lessons, and the second is the one people get wrong:

1. **Lower temperature reduces variance a lot.** For extraction — a task with a mostly
   correct answer — that is what you want. Use `temperature=0` for extraction,
   classification, structured output and anything you plan to evaluate.
2. **`temperature=0` is not deterministic.** It is *greedy*, which is not the same thing.
   Floating-point non-associativity in batched inference, mixture-of-experts routing that
   depends on what else is in the batch, and infrastructure changes all mean identical
   inputs can produce different outputs. Anyone who tells you to "just set temperature to
   0 for reproducibility" has not measured it.

**The engineering consequence is the important part.** Because you cannot get
determinism, you cannot write assertion-style tests (`assert output == expected`). You
need *statistical* tests: run N examples, compute a metric, compare against a threshold
with a confidence interval. That is Chapter 5, and this measurement is why it has to
exist.

When *should* you raise temperature? When you want diversity on purpose: generating
candidate hypotheses, brainstorming eval cases, or the synthesis step in Chapter 4 that
proposes theme names. Not for extraction.

> ### 🛑 Stop and look
> Run the temp=1.0 case and diff two of the outputs by hand. Are the disagreements about
> *which* insights exist, or about *how they're worded*? In our runs it is usually the
> latter plus one borderline item that appears in half the runs. That borderline item is
> almost always a genuinely ambiguous case — the model's instability is pointing at a gap
> in your task definition. **Instability is a diagnostic, not just a nuisance.**

---

## 1.5 Structured output: three levels, pick the third

You cannot evaluate prose. You need JSON. There are three ways to get it, and they are
not equally good.

**Level 1 — ask nicely.** `"Respond with JSON matching this shape: ..."` Works ~90% of
the time. The other 10% is markdown fences, a preamble ("Here is the JSON:"), a trailing
comma, or a truncated object because you hit `max_tokens`. You end up writing a
regex-and-`try/except` parser, and its failure rate becomes a hidden term in every metric
you report.

**Level 2 — prefill the assistant turn.** Add `{"role": "assistant", "content": "{"}` so
the model must continue a JSON object. Removes the preamble problem. Doesn't guarantee
schema conformance.

**Level 3 — use the tool schema as your output contract.** Define a tool whose
`input_schema` *is* your output schema, force it with `tool_choice`, and read
`tool_use.input`. With `"strict": true` the output is guaranteed to match the schema —
enums are real enums, required fields are present, types are types.

Level 3 is what `insighthub/extract.py` does. The tool is never "executed"; it exists
purely as a typed output contract:

```python
tool_choice={"type": "tool", "name": "record_insights"}
```

Three schema-design decisions worth copying:

- **Enums over free strings.** `category` is an enum built from the taxonomy YAML. If
  someone adds a category to the YAML, the schema changes automatically and you can never
  get a category that isn't in your taxonomy. This deletes an entire class of downstream
  bug.
- **A `verbatim` field.** Every insight must carry the exact source span it came from.
  This is the highest-leverage line in the whole schema: it makes faithfulness
  *deterministically checkable* (`verbatim in note.body` — no LLM judge needed, no cost,
  no ambiguity). Design your schemas so that the thing you most need to verify is
  mechanically verifiable.
- **An explicit escape hatch.** `insights: []` is a valid, expected answer, and the
  instructions say so. Schemas that make "nothing here" awkward to express get filled with
  garbage.

Look at the counterpart in `extract.py`:

```python
"verbatim": {"type": "string",
             "description": "Exact contiguous substring of the note."},
```

The `description` fields are not documentation. They are prompt — the model reads them.
Write them as instructions to the model, not notes to yourself.

---

## 1.6 Choosing a model: measure, don't vibe

Three tiers are configured in `.env`. Which should extraction use?

```bash
PYTHONPATH=src python scripts/ch1_model_bakeoff.py
```

<details>
<summary><code>scripts/ch1_model_bakeoff.py</code></summary>

```python
"""Same 20 notes, three models. Cost, latency, and a cheap quality proxy."""
import statistics
from insighthub.config import MODEL_FAST, MODEL_WORK, MODEL_DEEP
from insighthub.corpus import notes_by_split
from insighthub.extract import extract_many

notes = notes_by_split("dev")[:20]

for model in (MODEL_FAST, MODEL_WORK, MODEL_DEEP):
    exs = extract_many(notes, model=model, temperature=0.0, progress=False)
    ok = [e for e in exs if e.ok]
    n_ins = [len(e.insights) for e in ok]
    # Cheap deterministic quality proxy: does every verbatim actually appear?
    from insighthub.corpus import get_note
    faithful = sum(
        1 for e in ok for i in e.insights
        if i["verbatim"] in get_note(e.note_id).body
    )
    total = sum(n_ins)
    print(f"{model:32s} insights={total:3d} "
          f"faithful={faithful/max(total,1):.1%} "
          f"lat_p50={statistics.median(e.result.latency_s for e in ok):.2f}s "
          f"cost=${sum(e.result.cost_usd for e in ok):.4f} "
          f"errors={len(exs)-len(ok)}")
```
</details>

Indicative numbers from our runs on 20 dev notes (yours will vary):

| Model | Insights found | Verbatim faithful | p50 latency | Cost / 20 notes | Cost / 6,000 notes/yr |
|---|---|---|---|---|---|
| Haiku 4.5 | 47 | 94% | 1.6 s | $0.011 | ~$3.30 |
| Sonnet 5 | 44 | 99% | 2.4 s | $0.024 | ~$7.20 |
| Opus 5 | 43 | 100% | 4.1 s | $0.061 | ~$18.30 |

Now think like an engineer rather than a benchmark-chaser:

- The annual cost difference between the cheapest and most expensive option is **fifteen
  dollars**. At this volume, model cost is not a consideration and you should pick on
  quality alone. Say that out loud, because half of all model-selection debates are about
  savings that round to zero.
- The interesting column is **faithfulness**, not count. Haiku finds *more* insights and
  gets 6% of its verbatim spans wrong — it is paraphrasing where it was told to copy. More
  output is not better output.
- Where cost *would* matter is the agent in Chapter 4: a single analyst question can burn
  15 model calls with growing context. That is the workload to route carefully.

**The routing policy we adopt**, and the reasoning behind each line:

| Step | Model | Why |
|---|---|---|
| Extraction, classification | Sonnet 5 | High volume, needs precision on `verbatim`; Haiku's paraphrasing is disqualifying |
| Dedup / near-duplicate check | Haiku 4.5 | Narrow, well-specified, huge volume |
| Analyst agent loop | Sonnet 5 | Long horizon, tool use, needs to hold a plan |
| Theme naming, report synthesis | Opus 5 | Low volume, high visibility, judgement-heavy |
| LLM-as-judge (Ch.5) | Opus 5 | A weak judge is worse than no judge — never economise here |

Every one of those is revisited with data in Chapter 6 §6.7. Write it in `DECISIONS.md`
now as a hypothesis, not a conclusion.

> **On fine-tuning and self-hosting.** Both are real tools and both are premature here.
> Fine-tuning makes sense when you have thousands of labelled examples, a narrow stable
> task, and a prompt you've already optimised — Chapter 6 §6.7 shows the point at which
> distilling *this* extractor into a small model starts to pay. Self-hosting makes sense
> when data residency forbids an external API (a real constraint in pharma) or when
> volume is so high that GPU amortisation wins. Reaching for either before you have evals
> means you cannot tell whether it helped.

---

## 1.7 Prompt caching: the optimisation to do first

Our system prompt (instructions + taxonomy + fact base) is ~1,800 tokens and **identical
on every one of the 6,000 extraction calls per year**. Paying full input price to re-read
it every time is waste.

Caching marks a prefix so subsequent calls within the TTL read it at ~10% of input price.

```python
system=[{
    "type": "text",
    "text": INSTRUCTIONS + "\n\n" + taxonomy_prompt_block(),
    "cache_control": {"type": "ephemeral"},          # 5-minute TTL, default
}]
```

Verify it works — this is the part people skip and then wonder why nothing got cheaper:

```python
from insighthub import llm
from insighthub.corpus import notes_by_split
from insighthub.extract import extract_note
from insighthub.config import MODEL_WORK

for note in notes_by_split("dev")[:3]:
    e = extract_note(note, model=MODEL_WORK)
    print(e.result.summary())
```

```
claude-sonnet-5 | in 2,043 (cache r/w 0/1,812) | out 310 | 2.41s | $0.00764
claude-sonnet-5 | in 210  (cache r/w 1,812/0)  | out 288 | 2.11s | $0.00325
claude-sonnet-5 | in 198  (cache r/w 1,812/0)  | out 301 | 2.05s | $0.00341
```

Call 1 *writes* the cache (a ~25% premium). Calls 2 and 3 *read* it. Steady-state cost
drops by more than half.

Five rules that will save you an afternoon each:

1. **The cached prefix must be byte-identical.** A timestamp, a note ID, or a shuffled
   list in your "stable" block silently destroys every cache hit. If your `cache_read` is
   always 0, this is why. Diff two consecutive prompts.
2. **Order is everything.** Cache breakpoints apply to a *prefix*. Stable content first,
   variable content after. Putting the note before the taxonomy makes caching impossible.
3. **There is a minimum.** Prefixes below the model's minimum (512–4,096 tokens depending
   on model) are not cached at all — silently. Our taxonomy alone (~1,150 tokens) is
   *below Haiku 4.5's 4,096-token minimum*: on Haiku it caches nothing. That is a real,
   non-obvious reason our routing prefers Sonnet, whose minimum is 1,024.
4. **The 5-minute TTL refreshes on each hit.** A steady stream of calls keeps it warm for
   free. A batch job that runs hourly will miss every time — that's what the `"ttl": "1h"`
   option (at 2× write price) is for. Do the arithmetic for your actual call pattern
   before paying for it.
5. **Cache before you optimise anything else.** It is a one-line change with no quality
   risk. Prompt-shortening, in contrast, trades quality for money and needs evals to
   justify.

Check `data/taxonomy/insight_taxonomy.yaml`'s size against your model's minimum before
assuming this helped. Then look at `cache_read_input_tokens`. Always look.

---

## 1.8 Knowledge cutoff: why grounding is not optional

Ask the model about our product with nothing in context:

```python
from insighthub import llm
r = llm.call(messages=[{"role": "user", "content":
    "What is the approved maintenance dosing for VELTRAXA (zoltarimab) in "
    "ulcerative colitis, and what was the week 52 clinical remission rate in AURORA-2?"}])
print(r.text)
```

A good model tells you it has no information about that product. A model under pressure to
be helpful may produce something that *reads* exactly like a correct answer — plausible
dosing, a plausible percentage, a plausible trial description. In Medical Affairs, a
fabricated remission rate that reaches a clinician is not an embarrassment, it is an
incident.

Two distinct failure sources that people conflate:

- **Knowledge cutoff** — the model's training data ends at a date. Anything after it
  (including our fictional 2025 approval) is unknown.
- **Private data** — VELTRAXA has never existed anywhere. No cutoff extension would help.
  It must come from your documents.

Everything in Chapter 3 exists to close that gap, and the fact base in the system prompt
(`include_fact_base=True`) is your first, crudest grounding move. Try the same question
with the fact base included and watch the answer become correct and citable.

---

## 1.9 Reasoning effort: spend it where judgement lives

Some models expose extended/adaptive thinking — the model works through a problem before
answering, at the cost of extra output tokens and latency.

The rule that holds up in practice: **reasoning effort helps where the difficulty is
multi-step judgement, and does nothing where the difficulty is knowledge or format.**

| InsightHub step | Worth extra reasoning? |
|---|---|
| Extracting a verbatim span | No. It's copying. Thinking adds cost, not accuracy. |
| Assigning a category | Rarely. Marginal cases only. |
| Deciding whether two insights are the same underlying thing (Ch.3) | Sometimes |
| Judging whether an insight is faithful and non-generalised (Ch.5) | **Yes** |
| Synthesising a quarterly narrative from 60 themes (Ch.4) | **Yes** |

Test it rather than believing me. Take five borderline notes, run extraction with and
without thinking enabled, and compare on your own labels:

```python
r = llm.call(
    model="claude-haiku-4-5-20251001",
    max_tokens=4096,
    thinking={"type": "enabled", "budget_tokens": 2000},
    messages=[...],
)
```

Note the constraint: thinking needs `max_tokens` comfortably larger than
`budget_tokens`, since the budget is spent from the output allowance. And check the
current model docs for which models support `thinking` versus adaptive reasoning — the
support matrix moves.

If a step gets *worse* with more reasoning, that is a strong signal your instructions are
ambiguous: given room to deliberate, the model deliberates its way somewhere you didn't
intend. Fix the prompt, don't remove the thinking.

---

## 1.10 Multimodal, briefly

`data/raw/ddw2026_poster_Sa1187.png` is a congress poster — a bar chart with numbers that
appear nowhere in text. Models read images natively:

```python
import base64
from insighthub import llm
from insighthub.config import RAW_DIR

img = base64.standard_b64encode(
    (RAW_DIR / "ddw2026_poster_Sa1187.png").read_bytes()).decode()

r = llm.call(
    model="claude-sonnet-5",
    messages=[{"role": "user", "content": [
        {"type": "image",
         "source": {"type": "base64", "media_type": "image/png", "data": img}},
        {"type": "text", "text": "Extract every quantitative claim on this poster as "
                                 "JSON. If a number is read off a chart rather than "
                                 "printed, mark it estimated:true."},
    ]}],
)
print(r.text)
```

The decision this raises — and it's a real one for Chapter 3 — is *when* to use vision.
Sending an image costs roughly 1.2k–1.6k tokens per megapixel, versus ~200 tokens for the
same content as extracted text. So:

- **Use vision** when layout carries meaning that text extraction destroys: charts,
  posters, complex tables, forms, scanned documents with no text layer.
- **Use text extraction** when the PDF has a real text layer and the content is prose.
  Chapter 3 §3.2 does exactly this for `ecco2026_abstract_P0412.pdf`.
- **Use both** when you need the numbers *and* the prose: extract text, and send the
  figure regions as images.

---

## 1.11 Assemble the real extractor

You now have every piece. `insighthub/extract.py` in this repo is the assembled version —
read it top to bottom before running it. The parts to notice:

1. `system_blocks()` — stable content, cache breakpoint, nothing variable.
2. `extraction_tool()` — the schema built *from the taxonomy YAML*, so the two can never
   drift apart.
3. `INSTRUCTIONS` — a definition of "insight", three negative examples, the verbatim rule,
   the high-recall flag rule, and an injection-resistance rule.
4. `extract_note()` — never raises on model misbehaviour. It returns an `Extraction` with
   `error` set. Chapter 5 needs to *count* failures; a system that crashes on the 40th of
   140 notes cannot be evaluated.
5. `extract_many()` — thread-pool fan-out. The calls are IO-bound; 8 workers takes the dev
   set from ~4 minutes to ~40 seconds.

Run it on the dev set:

```bash
PYTHONPATH=src python - <<'PY'
from insighthub.corpus import notes_by_split
from insighthub.extract import extract_many, save
from insighthub.config import MODEL_WORK

notes = notes_by_split("dev")
exs = extract_many(notes, model=MODEL_WORK, temperature=0.0)
save(exs, "runs/ch1_dev_v1.jsonl")

tot = sum(len(e.insights) for e in exs)
print(f"{len(exs)} notes, {tot} insights, {tot/len(exs):.2f} per note")
print(f"errors: {sum(1 for e in exs if not e.ok)}")
print(f"cost:   ${sum(e.result.cost_usd for e in exs if e.result):.4f}")
print(f"suspicious content flagged in: "
      f"{[e.note_id for e in exs if e.suspicious]}")
```

---

## 1.12 🛑 Stop and look — the part that actually teaches you

Do not skip this. Twenty minutes.

```bash
PYTHONPATH=src python scripts/ch1_review.py runs/ch1_dev_v1.jsonl --n 20
```

<details>
<summary><code>scripts/ch1_review.py</code> — a two-minute hand-review tool</summary>

```python
"""Print extractions next to their source note for human review."""
import argparse, json, random
from insighthub.corpus import get_note
from insighthub.extract import load

ap = argparse.ArgumentParser()
ap.add_argument("path")
ap.add_argument("--n", type=int, default=20)
ap.add_argument("--seed", type=int, default=0)
args = ap.parse_args()

rows = load(args.path)
random.Random(args.seed).shuffle(rows)

for row in rows[:args.n]:
    note = get_note(row["note_id"])
    print("=" * 78)
    print(note.body)
    print("-" * 78)
    if not row["insights"]:
        print("  (no insights extracted)")
    for i in row["insights"]:
        verbatim_ok = "OK " if i["verbatim"] in note.body else "!! "
        print(f"  {verbatim_ok}[{i['category']:<30s}] {i['insight']}")
        print(f"       verbatim: {i['verbatim'][:90]!r}")
    input("\n[enter for next] ")
```
</details>

As you go, keep a tally on paper of every way the output is wrong. Do not try to fix
anything yet. Just name the failure modes. You should end up with something like:

- extracted the MSL's activity as an insight
- split one idea into two insights
- merged two ideas into one insight
- `verbatim` is a paraphrase, not a copy
- category is defensible but not what I'd have picked
- generalised "he said" into "clinicians say"
- missed an insight entirely
- flagged an AE that isn't one / missed an AE that is one

That list is a **failure taxonomy**, and it is the seed of Chapter 5. Write it into
`DECISIONS.md` with a rough count next to each. The counts matter more than the list: you
will want to work on the one with the biggest number, not the one that annoyed you most.

Also check specifically:

```bash
# Did anything trip the injection defence?
PYTHONPATH=src python -c "
from insighthub.extract import load
rows = load('runs/ch1_dev_v1.jsonl')
print([r['note_id'] for r in rows if r['suspicious']])"
```

One of the dev notes contains a planted prompt injection. Did your extractor notice? Did
it comply? Look at that note's output in detail — you'll return to it in Chapter 4 §4.9.

---

## 1.13 Decision log

Write these entries in `DECISIONS.md` before moving on:

- **D-001 Context strategy.** Whole corpus fits in context (~31k tokens); chose
  retrieval anyway on cost-at-scale and growth grounds, with an explicit commitment to
  measure retrieval against long-context stuffing in Ch.3 §3.11.
- **D-002 Temperature.** 0 for extraction. Measured variance at 0/0.3/1.0; documented that
  temp 0 is not deterministic, so tests must be statistical.
- **D-003 Output contract.** Tool schema with `strict`, enums generated from the taxonomy
  YAML, mandatory `verbatim` field to make faithfulness deterministically checkable.
- **D-004 Model routing.** Sonnet for extraction over Haiku, on verbatim faithfulness
  (99% vs 94%), not cost — annual delta is ~$4. Revisit in Ch.6 with real evals.
- **D-005 Caching.** Stable prefix cached; measured cache_read to confirm. Noted Haiku's
  4,096-token minimum makes our prefix uncacheable there.
- **D-006 Failure taxonomy v0.** *(your list from §1.12, with counts)*

---

## 1.14 Exercises

1. **Token forensics.** Which MSL's notes cost the most per insight extracted? Is
   telegraphic style cheaper or more expensive per note? Explain the result in terms of
   tokenization.
2. **Prompt ablation.** Remove the three negative examples from `INSTRUCTIONS`, re-run 20
   dev notes, and hand-count how many MSL-activity items come back as insights. This is
   your first controlled experiment — change one thing.
3. **Break the schema.** Set `"strict"` to `False` and add a free-text `category_notes`
   field. Run 20 notes. What comes back that couldn't before?
4. **Cache arithmetic.** At 6,000 notes/year in a nightly batch, does the 1-hour cache TTL
   pay for itself against the 5-minute one? Show the calculation. (Hint: it depends
   entirely on whether the batch is dense enough to keep a 5-minute window warm.)
5. **Confidence calibration, informally.** Bucket extracted insights by the model's
   self-reported `confidence` and hand-check 10 from the top bucket and 10 from the
   bottom. Is the model's confidence informative? (Most people are surprised. Keep the
   answer — Chapter 2 contrasts it with a *properly calibrated* probability.)

---

**Next:** [Chapter 2 — Machine learning foundations](02-ml-foundations.md) — where the
boring model beats the LLM, and you learn to prove it.
