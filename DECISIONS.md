# Decision log

The most valuable artefact in this repository. Every chapter adds entries; the format is
always the same, and the last line — *what I chose NOT to do* — is the one that pays off
six months later.

```
### D-0XX — <short title>
**Date:** YYYY-MM-DD | **Chapter:** N

**Observed.**   What the data actually showed. Numbers, not impressions.
**Hypothesised.** Why you think it happened.
**Changed.**    Exactly one thing.
**Result.**     The number, with its confidence interval. "Didn't move" is a result.
**Decided.**    Keep / revert / defer, and why. Then: what you chose NOT to do, and why.
```

---

## Per-note insight lists (scratch — Chapter 0 step 2)

*(Read each note, write down every insight you think it contains, in your own words,
numbered. Do this for all ten before writing the definition below.)*

### NOTE-0004
1. Positioning is post anti-TNF and post JAK — he admits this is inertia, not evidence.
2. Requested removal from the newsletter distribution list.
3. Open study list is owed to him once cleared — outstanding follow-up.

### NOTE-0011
1. Interested in target trough testing
2. Monitoring patients is important
3. Follow-up requested

### NOTE-0019
1. Formal response needed from Medical Information for his question
2. Their trial site date algorithm gives a different output than ours
3. Analytical - open to change if data supports

### NOTE-0023
1. KOL with advisory board interest depending on schedule availability
2. Three-infusion induction for each new UC start is not sustainable when units run at capacity --> need a solution to handle this issue.
3. Busy, schedules managed by assistant

### NOTE-0031
1. Two year durability is of high interest
2. His viewpoint is that Decision point for US biologis is 18 months instead of 12.
3. Authorization paperwork may be too long and complicated (2 denials in the quarter so far)

### NOTE-0038
1. Two year durability is of high interest
2. His viewpoint is that Decision point for US biologis is 18 months instead of 12.
3. Feels onset is slower than advertised

### NOTE-0042
1. MSL has to deal with parking issues
2. KOL not interested in newsletter - sees no value; asked to be removed
3. Wants to see OLE data past 100 weeks to position it as long term agent

### NOTE-0047
1. KOL not interested in newsletter - sees no value; asked to be removed
2. IV induction competes with Oncology for infusion spots which pushes him towards orla options
3. Interested in trial site list and reprint (to be sent via Medical Information)

### NOTE-0053
1. Two year durability is of high interest
2. His viewpoint is that Decision point for US biologis is 18 months instead of 12.
3. Route the question to Medical Information for a formal response.

### NOTE-0058
1. Not interested in newsletter; asked to be removed
2. Wants to know if arthralgia improvement of his 2 patients was coincidence or real.
3. Re-connect at congress

---

## My insight definition (v0)

*(Chapter 0 §0.5 — write yours here, in 60 words or fewer, BEFORE you write any code.
Do not edit it later; add a v1 in Chapter 5 §5.3 and keep both so you can see the gap.)*

>

---

## Entries

### D-000 — Example, so the format is unambiguous
**Date:** 2026-08-21 | **Chapter:** 0

**Observed.** Reading ten dev notes by hand, I produced 23 insights. Re-reading the first
three after finishing, I would now label two of them differently — I had silently changed
my own rule partway through.

**Hypothesised.** My definition of "insight" has no rule for granularity: when one remark
has two consequences, I sometimes split it and sometimes didn't.

**Changed.** Added a granularity rule to the definition: one insight per distinct thing
the company could act on differently.

**Result.** Re-labelled the same ten notes: 19 insights, and my second pass over the first
three agreed with my first. No independent check yet — n=1 annotator.

**Decided.** Keep the rule. **Not** doing: refining the definition further before I have
seen model output — I would be guessing at problems I haven't observed. Revisit in Ch.5
§5.3 after error analysis.

---

### D-001 — Model routing for extraction: faithfulness signal is noisy, not yet trustworthy
**Date:** 2026-08-23 | **Chapter:** 1

**Observed.** Ch.1 model bake-off (20 dev notes, temp=0.0): Haiku 4.5 100% verbatim-faithful
(44 insights), Sonnet 5 95.9% (49 insights), Opus 5 100% (57 insights) — the reverse of the
tutorial's indicative numbers, where Haiku was the unfaithful one. Re-running the identical
20-note Sonnet 5 extraction at temp=0.0 a second time produced 0 unfaithful insights out of
~49; a third run reproduced exactly one, in NOTE-0010: claimed verbatim
`"asked whether AURORA - 2 captured histologic remission."` vs. actual text
`"asked whether AURORA-2 captured histologic remission."` — spaces inserted around the
hyphen, and the paired `insight` field also fragmented `AURORA` and `histologic` mid-word.

**Hypothesised.** Two separate things, not one: (1) temp=0.0 is greedy, not deterministic —
faithfulness rate varies run to run with nothing else changed, so a single bake-off run
isn't a reliable model comparison (this is §1.4's lesson showing up again, one section
later); (2) the specific failure isn't paraphrasing, which is what the tutorial assumes —
it looks like a token-boundary/spacing artifact around hyphenated alphanumeric terms
(`AURORA-2`), which an exact-substring faithfulness check will always flag as unfaithful
even though nothing was semantically changed.

**Changed.** Nothing yet — logging this as a hypothesis per §1.6, not acting on it.

**Result.** N/A — no change made to measure.

**Decided.** Defer adopting the tutorial's routing table (Sonnet 5 for extraction) as-is.
Before trusting any faithfulness number for a routing decision: (a) run the bake-off N≥5
times per model and report a rate with a range, not a single-run percentage; (b) check
whether unfaithful spans cluster around hyphenated/compound terms specifically, since that
would mean the *check* is miscalibrated, not the model. **Not** doing: rewriting the
extraction prompt to fix "paraphrasing" — that would be fixing a problem I haven't
confirmed exists.

---

### D-002 — Extended thinking on extraction: no benefit on 5/6 borderline notes, one reliability regression
**Date:** 2026-08-23 | **Chapter:** 1

**Observed.** Compared extraction with vs. without thinking (Haiku 4.5, `budget_tokens=2000`,
`max_tokens=4096`) on the 6 dev notes flagged `contains_suspicious_content` in the §1.11 run
— chosen as the closest available proxy for "borderline." First finding, structural: the API
rejects `thinking` combined with a forced `tool_choice`, so the comparison had to run thinking
under `tool_choice: "auto"` instead of the strict forced-tool setup `extract.py` normally
uses. Content result on 5/6 notes: identical insight counts, near-identical text; NOTE-0019
differed only in category label for the same idea (`GUIDELINES_PRACTICE_PATTERNS` vs.
`PATIENT_SELECTION_POSITIONING`), and re-running the no-thinking side alone reproduced that
same instability without thinking involved. NOTE-0054 (the one note containing an actual
prompt-injection attempt) was the outlier: one run of the thinking condition hit
`stop_reason=max_tokens` and returned **no tool call at all** — a dropped extraction, not
just different wording. A second identical run succeeded with a well-reasoned, correct
extraction. The no-thinking condition succeeded on every run.

**Hypothesised.** Extraction is mostly a copying/categorisation task, matching §1.9's claim
that thinking helps judgement, not lookup — hence no gain on 5/6 notes. The NOTE-0054 failure
is a budget problem, not a quality problem: a 2000-token thinking budget against a 4096
`max_tokens` ceiling isn't reliably "comfortably larger" (the tutorial's own phrase) once a
note pushes the model into longer reasoning — e.g. explicitly working through whether to
comply with an injected instruction. Because thinking length itself varies run to run at the
same settings, this is a probabilistic failure mode: it will pass most bake-off runs and fail
silently in production on the notes that most need to be handled correctly.

**Changed.** Nothing — `extract.py` still uses forced `tool_choice`, no thinking, as before.

**Result.** N/A — no code change made to measure.

**Decided.** Do not enable thinking for the extraction step. The case against it isn't just
"no measured benefit," it's a concrete reliability regression on exactly the note category
(prompt-injection attempts) where a silent dropped extraction is most costly. If thinking is
revisited for a judgement-heavy step (faithfulness judging, Ch.5; synthesis, Ch.4), budget it
generously above the observed variance, not at the tutorial's example ratio, and treat forced
`tool_choice` and thinking as mutually exclusive when designing that call. **Not** doing:
tuning `budget_tokens`/`max_tokens` to try to make thinking work here — extraction doesn't
need it in the first place, so there's no upside to chase.

---

### D-003 — Context strategy: chose retrieval despite the whole corpus fitting in context
**Date:** 2026-08-23 | **Chapter:** 1

**Observed.** Full token census (§1.2/1.3, `ch1_token_census.py`): 140 notes = 20,059 tokens,
42 evidence docs = 17,111 tokens, taxonomy block = 950 tokens, fact base = 1,043 tokens.
**Total: 39,163 tokens** — comfortably inside a 200k–1M context window, roughly 5-6× over.

**Hypothesised.** "Fits in context" and "should be stuffed into every prompt" are different
questions. At 8 MSLs × ~15 notes/week × 50 weeks ≈ 6,000 notes/year, the corpus this small
today is one MSL-month; re-reading all of it on every query doesn't scale, even though
nothing forces that today.

**Changed.** Decision, not code: adopted the split from §1.3's table — task instructions,
taxonomy, and fact base stay in the cached prompt prefix; individual notes go in the user
message; the rest of the corpus is retrieved (Ch.3), never stuffed.

**Result.** N/A — architectural decision, not yet measured against the alternative.

**Decided.** Build retrieval in Ch.3, but treat "just send everything" as a real baseline to
beat, not a strawman — §3.11 measures retrieval against long-context stuffing explicitly,
since at this corpus size stuffing is a legitimate option some retrieval systems lose to.
**Not** doing: skipping the baseline comparison because retrieval "obviously" wins — that
would be assuming the answer to the thing Ch.3 exists to measure.

---

### D-004 — Temperature: 0 for extraction, and confirmed it isn't determinism
**Date:** 2026-08-23 | **Chapter:** 1

**Observed.** Measured variance on NOTE-0009 across temp=0.0/0.3/1.0, 5 runs each
(`ch1_sampling.py`, after fixing the anthropic 1.x `temperature` kwarg removal — see D-005).
Insight *counts* held at 6/6/6/6/6 across all three temperatures in one run; a second run
gave the same count-stability. Wording and category-set variance grew with temperature
(distinct texts 4→5→5, distinct category-sets 1→2→2/3 across reruns). Directly observed
non-determinism at temp=0 itself: re-running the identical Sonnet 5 faithfulness check
twice produced 0 unfaithful insights, then 1 (D-006); re-running the identical Haiku
no-thinking NOTE-0019 extraction gave 1 insight once and 2 insights the next time.

**Hypothesised.** Temperature reshapes the token probability distribution but doesn't
flatten it — confident (low-entropy) decisions like "how many distinct ideas are here"
survive resampling almost every time, while close calls (wording, category assignment
between near-synonymous options) are where temperature actually has room to flip the
outcome. temp=0 is greedy (always take the top token), which is a different property from
deterministic (infrastructure-level non-associativity still varies the result run to run).

**Changed.** Adopted temperature=0.0 for extraction (already the default in `extract_note`).
No prompt or schema change made from this entry alone.

**Result.** Confirmed qualitatively, not yet with a formal statistical test — that's Ch.5's
job. The practical consequence: assertion-style tests (`assert output == expected`) are not
viable for this pipeline; only statistical tests (N examples, a metric, a threshold with a
confidence interval) are meaningful.

**Decided.** Keep temp=0.0 for extraction, classification, and anything evaluated against a
fixed answer. **Not** doing: treating temp=0 as a substitute for real reproducibility
tooling (e.g. caching model responses in tests) — that would quietly reintroduce the belief
this entry just disproved.

---

### D-005 — Output contract: strict tool schema, and two undocumented strict-mode requirements
**Date:** 2026-08-23 | **Chapter:** 1

**Observed.** `extract.py`'s `record_insights` tool uses `strict: true`, enums generated
from the taxonomy YAML (so category drift is structurally impossible), and a mandatory
`verbatim` field for mechanical faithfulness checking. As shipped, the schema 400'd on
every call: `"For 'object' type, 'additionalProperties' must be explicitly set to false"`,
then (after fixing that) `"For 'number' type, properties maximum, minimum are not
supported"`. Neither requirement is mentioned in §1.5's description of Level-3 structured
output.

**Hypothesised.** Strict-mode schema validation has tightened since this tutorial file was
written: `additionalProperties: false` is now required on *every* nested object, not just
the top-level schema, and numeric bound keywords (`minimum`/`maximum`) are no longer
supported at all under `strict: true`. This is model/API-version drift, not a bug in the
tutorial's design.

**Changed.** Added `"additionalProperties": false` to both the top-level `input_schema` and
the nested `insights[].items` object; removed `minimum`/`maximum` from the `confidence`
field, keeping it a plain `number` with a description instead.

**Result.** Extraction went from 100% `no_tool_call`/`api_error` failures to 0 errors across
every subsequent run (60-note dev run, model bake-off, thinking comparison — all clean).

**Decided.** Keep the fix; it's required for the schema to function at all under the
currently-installed SDK/API, not optional hardening. **Not** doing: relaxing `strict: true`
to work around the validation instead — that would trade away the exact guarantee (enums
are real enums, required fields present) this design decision exists for.

---

### D-006 — Model routing: real bake-off reversed the tutorial's expected faithfulness ranking
**Date:** 2026-08-23 | **Chapter:** 1

**Observed.** See D-001 for full detail. Summary: our 20-note bake-off measured Haiku 4.5 at
100% verbatim-faithful, Sonnet 5 at 95.9%, Opus 5 at 100% — the reverse of this chapter's
own indicative numbers (which have Haiku as the *unfaithful* one at 94%, justifying Sonnet
for extraction). Re-running the faithfulness check on Sonnet 5 alone gave 0% and then a
different single unfaithful case across repeated runs, and that one case looked like a
tokenization/spacing artifact on a hyphenated term (`AURORA-2`), not paraphrasing.

**Hypothesised.** Single-run bake-offs are not a reliable way to rank models, given temp=0
is non-deterministic (D-004) — the tutorial's own indicative table is presumably also a
single run, so treating it as ground truth to imitate would just be copying someone else's
noise instead of measuring your own.

**Changed.** Nothing — routing decision deferred, not adopted, pending D-001's proposed
N≥5-runs-per-model re-measurement.

**Result.** N/A.

**Decided.** Do not adopt "Sonnet 5 for extraction" on the strength of one bake-off run,
ours or the tutorial's. Revisit with the measurement plan in D-001 before Ch.6 §6.7 asks for
a routing decision backed by real evals. **Not** doing: switching extraction to Haiku on the
strength of our one favorable run either — that would repeat the exact mistake this entry
is about, just in the other direction.

---

### D-007 — Caching: confirmed cache_read, and Haiku's minimum makes our prefix uncacheable there
**Date:** 2026-08-23 | **Chapter:** 1

**Observed.** §1.7 verification (`extract_note` × 3 on Sonnet 5, real `.env` key): all three
calls showed `cache_read=2,706, cache_write=0` — including the *first* call, because the
cache was already warm from prior Sonnet 5 activity in the same session (5-minute TTL,
refreshed by the steady stream of earlier bake-off/debugging calls). Separately, our actual
token census (§1.2) measured the taxonomy block at 950 tokens — below Haiku 4.5's
4,096-token minimum cacheable prefix, so on Haiku this prefix would not be cached at all.

**Hypothesised.** Nothing to hypothesise on the read/write mechanics — directly confirmed.
The Haiku-minimum finding matters because it's a second, independent reason (beyond
faithfulness, D-006) that routing extraction to Haiku isn't free: even if Haiku won on
faithfulness, it would lose the caching discount entirely on this prefix size.

**Changed.** Nothing — `system_blocks()` already uses `cache_control: {"type": "ephemeral"}`
correctly ordered (stable content first, cache breakpoint before anything variable).

**Result.** Confirmed cache reads are consistent and byte-stable across notes (same
`cache_read` count on every call), which itself validates the stable prefix really is
byte-identical.

**Decided.** Keep the current caching setup as-is. Note the Haiku-minimum finding as a real
constraint on any future Haiku-for-extraction proposal (D-006), not just a theoretical one.
**Not** doing: shrinking the taxonomy block to fit under Haiku's minimum — that would be
optimizing the prompt to fit a model choice we haven't actually decided to make yet.

---

### D-008 — Failure taxonomy v0 — STUB, pending full 20-note review
**Date:** 2026-08-23 | **Chapter:** 1

**Observed.** Partial only — full §1.12 20-note hand review not yet complete. Two concrete
findings so far from spot-checking the 6 `suspicious`-flagged notes: (1) 5 of 6 flags are
false positives — only NOTE-0054 (the planted injection attempt) actually contains
suspicious content; NOTE-0016/0018/0019/0032/0038 are ordinary notes. (2) NOTE-0038's
`insight` field silently upgraded "the week 4 numbers **he remembers** from the label" (the
verbatim, epistemic-hedged) into "the week 4 onset **reflected in** the label" (the insight
text, stated as fact) — a faithfulness drift the mechanical `verbatim in note.body` check
cannot catch, since it only validates the copied span, not the summary.

**Hypothesised.** TBD — pending full review.

**Changed.** Nothing yet.

**Result.** N/A.

**Decided.** Deferred. Complete the full 20-note review (`ch1_review.py`), tally every
failure mode with counts, and replace this stub. **Not** doing: finalizing this entry from
a 6-note spot-check — the tutorial is explicit that the counts, not the list, are what
matter for prioritization in Ch.5.

---

<!-- Chapter 2 -->

<!-- Chapter 3 -->

<!-- Chapter 4 -->

<!-- Chapter 5 -->

<!-- Chapter 6 -->
