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

### D-009 — Text-classification bake-off: LLM wins decisively, and the classical learning curve is flat, not rising
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** `ch2_bakeoff.py` crashed on the same strict-schema bug as D-005
(`additionalProperties` missing on `CLASSIFY_TOOL`'s `input_schema`) — a second, separate
tool definition in this file that never got the Chapter 1 fix. Patched identically. Full
results on 508 labelled sentences, 14 classes: TF-IDF naive CV 1.00 (a lie — near-duplicate
leakage), TF-IDF grouped-by-variant 0.080, TF-IDF grouped-by-topic 0.028, embeddings
grouped-by-variant 0.404, embeddings grouped-by-topic 0.164, LLM zero-shot Haiku 4.5 macro-F1
0.662 ($1.65/1k, p50 0.97s), LLM zero-shot Sonnet 5 macro-F1 0.756 ($1.27/1k, p50 3.00s).
Sonnet is simultaneously *more accurate and cheaper per 1k* than Haiku here — no cost/quality
tradeoff at all, unlike D-006's extraction bake-off. Separately measured a genuine learning
curve for embeddings+logreg on unseen-topic generalization (train on N randomly-sampled
topics, test on the rest, 5 seeds per point, `topic_group`-grouped to prevent leakage):
macro-F1 stayed flat between 0.057 and 0.090 across training sizes from 61 to 424 examples
(effectively the whole dataset) — no upward trend at any point in that range.

**Hypothesised.** The LLM-wins result matches the tutorial's stated rule (few labels,
lexically diverse text, evolving taxonomy → LLM). The flat learning curve is the more
important finding: it suggests the gap to the LLM isn't merely "not enough data yet" in a
way a bit more labelling would close. A linear classifier over generic sentence embeddings
may not generalise to genuinely novel topics at all within any data volume we could plausibly
collect soon — the failure looks structural (representation/model capacity for this specific
generalisation), not a data-volume shortfall the way TF-IDF's vocabulary-memorisation problem
was. Sonnet's cost/accuracy dominance over Haiku is unexplained — plausibly fewer failed tool
calls falling back to a default label, or a cache-economics difference — not yet investigated.

**Changed.** Fixed `ch2_bakeoff.py`'s `CLASSIFY_TOOL` schema (added
`"additionalProperties": false`). No modelling change made.

**Result.** Bake-off runs clean end-to-end now. Learning-curve experiment is new evidence
beyond what the tutorial asks for — it directly attempts the "at what N would you switch
back to classical" question the script's closing line poses, and the honest answer is **we
cannot estimate a crossover point from this evidence**, because there is no rising trend to
extrapolate from, not merely "it's a big number."

**Decided.** Do not plan around a classical-model crossover for topic-level categorisation
using this embeddings+logreg approach — the current evidence gives no reason to expect one at
any data volume incrementally larger than what we have. If Chapter 6 §6.7 revisits
distillation economics, treat this as a red flag to test with a stronger classical approach
(e.g. a better embedding model, or a small fine-tuned transformer) before assuming more
labelled data alone would close the gap. **Not** doing: investigating why Sonnet beats Haiku
on cost here — noted as an open question, not chased now, since it doesn't change the
chapter's core routing decision (LLM for classification at current data volume either way).

---

### D-010 — Metric: P@40, derived from the actual review-queue capacity
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** Review capacity is 40 insights/week (`REVIEW_CAPACITY_PER_WEEK` in
`triage.py`). logreg scores P@40=0.575 vs. rules baseline 0.475 vs. majority 0.300.
ROC-AUC (0.768) reported alongside but not used for the decision — PR-AUC (0.468) is the
honest secondary, since ROC-AUC flatters at this ~16-20% base rate (§1's D-006 made the
same point about LLM faithfulness numbers looking better than they are in isolation).

**Hypothesised.** Accuracy or F1 would optimise for a decision nobody is making — the real
decision is always "which 40 does a human read this week," so the metric has to be
precision at exactly that cutoff, not a threshold-free aggregate.

**Changed.** Adopted P@40 as the primary reported metric for this model, PR-AUC secondary,
ROC-AUC informational only.

**Result.** N/A — metric choice, not a modelling result.

**Decided.** Keep P@40 as primary. **Not** doing: reporting accuracy at all — with an
83.6%-negative base rate it would be actively misleading even as a footnote.

---

### D-011 — Split: temporal, not random, and it surfaced a real base-rate shift
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** `temporal_split` (train = older rows, test = newer): train n=1,396, base rate
14.1%; test n=604, base rate 20.5% — a 6.4-point shift, exactly reproducing the tutorial's
numbers.

**Hypothesised.** This is genuine label drift (recent insights get selected more often), not
noise — a random split would have averaged it away and hidden a real property of the
deployment setting: the model will be scored on data with a different base rate than it was
trained on, every time, forever, because "newer" is always the deployment condition.

**Changed.** Adopted temporal splitting everywhere in this chapter; never random.

**Result.** Confirmed the shift is real and reproducible, not a fluke of one split.

**Decided.** Keep temporal splitting as the standing rule for this dataset and any future
InsightHub tabular model. **Not** doing: correcting for the shift by reweighting or
re-sampling — that would hide it, and the model *should* be evaluated under the honest
condition it'll actually face in production.

---

### D-012 — Feature exclusion (`days_since_captured`): the tutorial's predicted leak did not reproduce
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** Re-added `days_since_captured` to `NUMERIC` (removing it from `EXCLUDED`) and
re-fit logreg. Tutorial claims this should make PR-AUC "jump." Measured result: PR-AUC
0.4685 → 0.4690 (noise), ROC-AUC 0.7675 → 0.7679 (noise), P@40 identical at 0.575. Only
Brier moved meaningfully (0.1418 → 0.1396, a mild improvement). Verified the feature really
was included (checked the actual column list fed to the pipeline) and checked its raw
correlation with the label within each split: -0.021 (train), -0.041 (test) — essentially
zero.

**Hypothesised.** The base-rate shift between train/test (D-011) is a shift in the *overall*
proportion, not a per-row signal this feature carries — with near-zero within-split
correlation, a linear model has nothing to exploit for ranking, even though the feature
literally encodes the thing that's shifting. The leak this exercise is meant to demonstrate
is real in principle (a time-position feature can leak) but doesn't manifest as a ranking
metric jump on this particular generated dataset for this particular model.

**Changed.** Nothing — `EXCLUDED` still drops `days_since_captured`. Confirmed the exclusion
is correct in principle regardless of whether this dataset demonstrates the failure mode
dramatically.

**Result.** No PR-AUC jump observed; the exercise doesn't reproduce as written on this data.

**Decided.** Keep excluding the feature — the *reasoning* (it doesn't have the same meaning
at prediction time, and its value would be 0 for every genuinely new row in production) holds
regardless of whether this particular dataset shows a dramatic metric jump when you violate
it. **Not** doing: treating the muted result as evidence the exclusion doesn't matter — the
production-time argument doesn't depend on the synthetic data cooperating.

---

### D-013 — Model: plain logistic regression, chosen on PR-AUC and Brier together
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** logreg: PR-AUC 0.468, Brier 0.142. logreg_balanced: PR-AUC 0.457, Brier 0.204
(44% worse). GBM: PR-AUC 0.387, Brier 0.153 — worse than plain logreg on every metric with
1,396 training rows and 12 features. All numbers reproduced exactly against the tutorial's
table.

**Hypothesised.** `class_weight="balanced"` re-weights the loss to fight the ~16-20% base
rate, which distorts output probabilities for no ranking gain (P@40 identical to plain
logreg) — a "should help" reflex that measurably doesn't. GBM overfits at this row count;
the flexible model needs more data than we have to earn its complexity.

**Changed.** Selected plain `logreg` (no class weighting) as the shipped model.

**Result.** Confirmed across every reported metric, not just one.

**Decided.** Ship plain logistic regression. Ship the *ranking* (sorted score), not a fixed
probability threshold — §2.7's capacity-vs-EV conflict (D-015) means any fixed threshold
will be wrong the moment the business changes review capacity. **Not** doing: reaching for
GBM or any more complex model until there's evidence more data actually helps it win.

---

### D-014 — Significance: the P@40 advantage over rules is not yet proven
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** Bootstrap (`ch2_bootstrap.py`): logreg P@40 = 0.589, 95% CI [0.425, 0.750];
rules P@40 = 0.491, 95% CI [0.325, 0.675]; paired difference +0.099, 95% CI
[-0.100, +0.275], P(diff > 0) = 0.82. The CI on the difference includes zero. At wider k the
advantage holds and grows (k=100: 0.480 vs 0.430; k=200: 0.415 vs 0.325).

**Hypothesised.** At n=40 (our actual operating point), test-set noise is large enough that
an 8-9 point P@40 edge isn't distinguishable from chance with 82% confidence, not 95%+. The
consistency across k=40/100/200 is more convincing evidence than any single point estimate,
because it's not the kind of pattern noise alone tends to produce.

**Changed.** Nothing — logreg remains the shipped ranker regardless, since it's still the
better bet even without proof, and there's no cost to using it over rules.

**Result.** N/A — this entry is about honestly characterising the confidence in D-013's
result, not changing it.

**Decided.** Do not claim "the model beats the rules baseline" as a proven fact in any
report or presentation — say "an ~8 point improvement, not yet statistically significant at
our operating point, consistent at wider k" instead. **Not** doing: collecting more data
right now purely to firm up this one comparison — noted as the honest caveat, revisit if the
distinction becomes decision-relevant.

---

### D-015 — Capacity finding: EV-optimal threshold wants ~7.5x current review capacity
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** `sweep_thresholds` (logreg, cost_false_negative=2.0, cost_false_positive=0.15):
expected value is maximised at threshold 0.1154, flagging 302 of 604 test items (tp=101,
fp=201, fn=23, precision=0.334, recall=0.815, EV=24.85) — reproduced exactly against the
tutorial. Actual capacity is 40/week.

**Hypothesised.** The EV calculation is a real signal, not a modelling artefact: given the
stated cost ratio (a miss costs ~13x a wasted read), the review queue is under-resourced
relative to what would be optimal, not just relative to what the model would like to flag.

**Changed.** Nothing about the model. This is a business-facing finding, not an engineering
fix.

**Decided.** Do not silently pick whatever threshold happens to produce ~40 flagged items
and call the problem solved — that would hide the actual finding. Take the real number to
the business: at capacity 40, ~18% of relevant insights get caught; doubling capacity to 80
would remain well short of EV-optimal but would materially improve recall. **Not** doing:
shipping a fixed threshold at all — ship the ranked list and let review capacity be a
business-set parameter, per D-013.

---

### D-016 — Text classification: LLM zero-shot over classical, and the classical learning
curve gives no reason to expect a near-term crossover
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** See D-009 for full detail and numbers (TF-IDF, embeddings, and both LLM rows).
Summary: LLM zero-shot (Sonnet 5, macro-F1 0.756) beats the best classical row (embeddings,
grouped-by-topic, 0.164) by roughly 4.6x, with zero labelled training examples against the
classical rows' 400. A dedicated learning-curve experiment (embeddings+logreg, unseen-topic
generalisation, 61-424 training examples) showed no upward trend at all — flat between 0.057
and 0.090 across the whole range.

**Hypothesised.** This is stronger and more specific than "the tutorial's stated rule
(few labels → LLM) applies here" — it's direct evidence that more labelled data in the range
we could plausibly collect soon would not close the gap, because the classical approach
isn't demonstrating any learning in that range to begin with.

**Changed.** Nothing — text classification stays LLM-based (Sonnet 5) for now.

**Result.** Confirmed via the learning-curve experiment, not assumed from the tutorial's
general rule.

**Decided.** Revisit only after the review stream (Ch.5) has produced substantially more
than the ~36 examples/class we tested up to here — and even then, test with a stronger
classical approach (better embeddings, or a small fine-tuned model) before assuming volume
alone fixes it, per D-009. **Not** doing: setting a specific "labels per class" revisit
number — D-009 already showed a specific number would be fabricated precision given the flat
curve.

---

### D-017 — Label bias: `selected_for_review` reflects historical reviewer behaviour, not ground truth
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** `selected_for_review` records what strategists historically chose to spend
review time on (§2.2), not an independently verified importance label. Error analysis
(§2.8) found confident false negatives clustering in `PATIENT_SELECTION_POSITIONING`,
`COMPETITIVE_LANDSCAPE`, and `EFFICACY_REAL_WORLD` (21 total, vs. only 4 confident false
positives spread thinly across other categories) — a plausible signature of the model
learning a real historical under-selection pattern in those categories rather than making
an error of its own.

**Hypothesised.** If reviewers historically under-prioritised certain categories for reasons
unrelated to actual importance (e.g. harder to act on quickly, requires cross-functional
buy-in), a model trained on their choices will reproduce and appear to validate that
pattern, entrenching it rather than correcting it.

**Changed.** Nothing to the model — this is a known-limitation finding, not a fixable bug.

**Decided.** Document this as a standing caveat on every presentation of model output: it
predicts what a strategist would historically choose to review, not what is objectively most
important. **Not** doing: attempting to "debias" the label without deeper input from the
medical strategy team on which categories are actually under-served — that's an
organisational question, not a modelling one.

---

### D-018 — §2.13 Exercise 1: deployment-time leak simulation also shows no collapse
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** Fit logreg with `days_since_captured` included (as in D-012), then scored the
test set twice: once with real values, once with every row's value forced to 0 (simulating
what a genuinely new insight looks like in production). PR-AUC 0.4690 → 0.4683, ROC-AUC
0.7679 → 0.7670, P@40 unchanged at 0.575 — no collapse, consistent with D-012.

**Hypothesised.** Follows directly from D-012: a feature the model assigned near-zero
practical weight to (because it carries near-zero within-split correlation with the label)
can't hurt the ranking much when zeroed out either. The exercise's premise is sound in
general — a time-position feature *can* collapse a model that actually relies on it — it
just doesn't apply to this specific generated dataset and this specific linear model.

**Changed.** Nothing.

**Decided.** No new action — reinforces D-012's decision to exclude the feature on the
production-time-meaning argument, independent of whether this dataset dramatizes the
consequence. **Not** doing: treating "it didn't collapse this time" as evidence the general
caution is unnecessary elsewhere.

---

### D-019 — §2.13 Exercise 2: `cost_false_negative` cannot bring the EV-optimal threshold near capacity — only `cost_false_positive` can
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** Full threshold sweep (not just the 25-point quantile grid `sweep_thresholds`
searches) at `cost_false_negative` from 10.0 down to 0.001: EV-optimal flagged count never
dropped below ~299, even at near-zero miss cost. Swept `cost_false_positive` instead (fixing
`cost_false_negative=2.0`): flagged count fell from 450 (cfp=0.15) to 26 (cfp=4.0), crossing
near capacity=40 around cfp≈3.6-4.0 (ratio `cost_false_negative/cost_false_positive`≈0.5-0.55)
— and at that crossover, expected value is deeply negative (~-220 to -235).

**Hypothesised.** Structural, not a quirk of this data: the marginal condition for "is
flagging item i profitable" reduces to `p_i > cost_false_positive / (value_true_positive +
cost_false_negative + cost_false_positive)` — `cost_false_negative` only appears in a term
that *raises* the profitable-to-flag bar as it shrinks toward the value_true_positive+cfp
sum, pushing toward flagging *more*, never less. Only `cost_false_positive` can shrink the
optimal flagged set. The exercise's framing (sweep `cost_false_negative` to find where the
optimum reaches capacity) has no answer as posed.

**Changed.** Nothing to the model.

**Result.** A specific, falsifiable business claim: reaching capacity=40 via cost tuning
alone requires believing false positives cost *more* than misses (inverted from D-015's
current 13x-misses-cost-more assumption), and even then the policy is EV-negative under its
own accounting.

**Decided.** Do not attempt to "tune costs until the threshold matches capacity" as a way to
avoid the D-015 capacity conversation — this exercise shows that path requires an
economically incoherent set of beliefs (false positives costing more than misses) to even
reach 40, and produces a value-destroying policy when it does. The real lever is capacity
itself (D-015), not the cost parameters. **Not** doing: proposing a specific
`cost_false_positive` value for production — these are illustrative, not measured, business
costs.

---

### D-020 — §2.13 Exercise 3: fairness-ish audit finds a real, unexplained EMEA disparity
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** In the single global top-40 ranking (the actual deployment mechanism), recall
of each region's true positives: APAC 0.258, US-West 0.250, US-East 0.185, US-Central 0.111,
**EMEA 0.083** — EMEA insights are ~3x less likely to reach the shared weekly list than
APAC's or US-West's. EMEA is the largest region in the raw corpus (60/140 notes, §0.4), so
this isn't a thin-sample artefact. EMEA also has the lowest precision *among its own top-40
entries* (0.333, worse than every other region) — yet scores respectably on an independent
per-region P@40 (0.475, better than US-Central's 0.300 and US-West's 0.350). So EMEA insights
rank reasonably well against each other but poorly when competing against other regions in
the shared ranking.

**Hypothesised.** Two live explanations, not distinguished by this data alone: (1) EMEA
differs systematically on an input feature (KOL tier mix, novelty score distribution,
category mix) that the model weights heavily, deflating EMEA's scores relative to
comparable-quality insights elsewhere; (2) EMEA insights were historically under-selected by
reviewers for reasons unrelated to importance (the D-017 label-bias risk, now with a
specific, checkable regional signature rather than a general caveat).

**Changed.** Nothing to the model — this is a finding requiring investigation, not a fix.

**Decided.** Flag this to the medical strategy team before any deployment — a 3x
cross-region recall disparity is not a minor footnote. **Not** doing: guessing which of the
two hypotheses is correct or attempting a fix (reweighting, a region feature, a fairness
constraint) without first checking the feature-distribution question above; acting on the
wrong hypothesis could entrench the label bias rather than correct it.

---

### D-021 — §2.13 Exercise 4: the triage model has a real (diminishing-returns) learning curve, unlike the classification task in D-016
**Date:** 2026-08-24 | **Chapter:** 2

**Observed.** Retrained logreg on 10/25/50/75/100% of the temporal-split training set:
PR-AUC 0.362 → 0.434 → 0.456 → 0.451 → 0.468 (n=139→349→698→1,047→1,396). Sharp gain from
10%→25% (+0.072), then flattening (25%→100% only adds +0.034 total, with a slight dip at
75% likely sampling noise).

**Hypothesised.** Classic diminishing-returns shape — most of what these 8 numeric + 2
categorical features can teach a linear model, they're already teaching it by ~350-700 rows.
More data still helps marginally, but the model is closer to feature-limited than
data-limited at current volume. This is a genuinely different shape from D-016's flat
classification-learning-curve (0.057-0.090, no trend at all) — proof the flatness there was
specific to that harder cross-topic generalisation problem, not a general property of "ML on
this data."

**Changed.** Nothing.

**Decided.** More triage-model training data is worth collecting opportunistically (real,
if modest, expected gain) — unlike D-016's classification task, where the evidence argues
against expecting a data-volume fix at all. Keep both curves as the reference examples when
Chapter 5 asks "how many eval examples do I need" (§2.13's own stated connection). **Not**
doing: projecting a specific target row count from a 5-point curve — the shape (diminishing
but not flat) is the actionable signal, not a precise extrapolated number.

---

### D-022 — `repair_ocr` bug: clean numbers were being corrupted into dictionary words
**Date:** 2026-08-24 | **Chapter:** 3

**Observed.** §3.2's own "measure the cleaner in both directions" check
(`repair_ocr(n.text) != n.text` across all 140 clean notes) found 3 false repairs
(`NOTE-0005`, `NOTE-0042`, `NOTE-0050`), against the tutorial's expected `0`. Diffed each:
all three had a clean `"100"` (as in "OLE data past 100 weeks") silently rewritten to
`"loo"`. Traced the mechanism: `_fix_numeric("100")` correctly returns `None` (nothing to
digitise), but the code then fell through unconditionally into letter-confusion candidate
generation (`_candidates`), which reaches `"loo"` from `"100"` via three digit->letter
swaps (`1->l`, `0->o`, `0->o`). Because this machine has `/usr/share/dict/words` installed
and `"loo"` is a real English word, the lexicon-match branch accepted it — that branch has
no confidence threshold at all, unlike the bigram-scoring fallback, which requires
`min_gain=2.0`.

**Hypothesised.** The `re.fullmatch(r"[A-Za-z|]{3,}", core)` guard existed in the function
but was positioned *after* the lexicon-match loop, so it only protected the bigram-scoring
path, not the (unconditional, unthresholded) lexicon-match path. A purely numeric token has
no letter-shaped OCR ambiguity to begin with — there was never a reason to run it through
letter-confusion repair at all.

**Changed.** Moved the letter-shape guard earlier in `docs.py`'s `fix()` closure, right
after the `_fix_numeric` check, so a non-letter-shaped token (e.g. already-clean digits)
returns unchanged before candidate generation ever runs — closing the gap for both the
lexicon-match and bigram-scoring paths at once.

**Result.** False repairs on clean text: 3 -> 0, matching the tutorial's expected output.
Verified the real OCR-damage repair (`ocr_call_note.txt`) still works correctly afterward
(IDs, dates, and words like `Iooks`->`looks` all still repair as intended).

**Decided.** Keep the fix. This is the kind of failure the section's own two-directional
measurement discipline is designed to catch — and it did, on the first check. **Not**
doing: removing `/usr/share/dict/words` from the lexicon to avoid this class of accident
generally — the fix targets the actual defect (letter-repair running on non-letter tokens),
not the coincidence that exposed it. Two smaller, separate case-preservation imperfections
noticed in the same output (`OBJECT|VE`->`oBJECTIVE`, `AIdric's` not fully corrected to
`Aldric's`) were flagged but not investigated — logged here as a pointer, not fixed.

---

### D-023 — Hybrid search (RRF) can bury the single best match; compound queries expose a second, separate embedding weakness
**Date:** 2026-08-24 | **Chapter:** 3

**Observed.** Investigated Q-027 ("Device usability problems for older patients," 6 gold
notes) after it scored recall=0.00 at hybrid@10 in the §3.6 eval. `NOTE-0018` (explicitly
about elderly patients unable to use an autoinjector) is vector-rank **1** (similarity
0.377) but BM25-rank ~41 (near-zero lexical overlap) and lands at hybrid-rank 18-23
depending on exact query wording — outside top-10 despite being the standout semantic
match. Traced why: RRF sums *per-ranker* rank contributions
(`1/(rrf_k+rank)`), so several notes ranking only moderately on *both* BM25 and vector
(e.g. vec#12 + bm25#1) out-accumulate a note that is rank-1 on exactly one ranker and
absent from the other. Separately, the other 5 gold notes for Q-027 all contain the
identical, unambiguous device-usability sentence ("the pen is stiff... the cap was
extremely hard to remove") but never mention patient age — and rank weakly (40-115) on
*both* signals, not just BM25. These notes satisfy the gold label's relevance criterion
(device usability, full stop) without containing the query's second concept (age), and a
single dense query embedding represents both concepts jointly, diluting similarity for any
document matching only one.

**Hypothesised.** Two distinct, independent failure mechanisms, not one: (1) RRF's
additive-per-ranker design structurally favours "moderately good on every signal" over "the
single best match on exactly one signal" — a property of the fusion method itself, not a
bug, but one the tutorial's "do not assume hybrid wins" caution doesn't specifically name.
(2) Compound queries (two concepts joined in one string) are a genuine blind spot for
single-vector embedding similarity: a document satisfying only one concept is
under-ranked even when the *actual* relevance criterion (as encoded in the gold labels)
only required that one concept.

**Changed.** Nothing to the retrieval code — these are diagnosed failure modes, not yet
fixed.

**Result.** Confirmed via direct rank inspection (not aggregate metrics) — the aggregate
hybrid numbers (recall@10=0.479, best of all three retrievers) fully hid both of these
mechanisms; only reading a specific failing query's component ranks surfaced them.

**Decided.** Do not treat Q-027-style zero-recall failures as "needs better embeddings" by
default — check component ranks first, because the fix differs by mechanism: mechanism (1)
might warrant a higher `pool` or a rank-boost for single-ranker top-1 hits; mechanism (2)
is better addressed by decomposing compound queries into a semantic sub-query plus a
metadata/keyword filter (per §3.8's filter guidance) rather than expecting one embedding to
carry two concepts. **Not** doing: tuning `rrf_k` or `pool` reactively to fix this one
query — that risks overfitting the fusion to a single eval case; the decomposition approach
generalises, a parameter tweak here likely wouldn't.

---

### D-024 — §3.11 long-context-vs-RAG result was an artifact of an undersized `max_tokens`; corrected numbers match the tutorial's framing
**Date:** 2026-08-25 | **Chapter:** 3

**Observed.** First run of `ch3_longcontext_vs_rag.py --n 12` produced a result nothing like
the tutorial's stated expectation ("long-context is competitive or slightly better on
quality"): `all-140-notes` scored grounded=1.50, complete=1.33 — worse than both
`hybrid-k10` (2.67, 2.00) and `hybrid-k30` (3.08, 2.25), and every one of the 12 queries hit
the minimum 1/1 under `all-140-notes`, never a mix. Pulled one query out of the script
directly: `stop_reason="max_tokens"`, `output_tokens=1200` (exactly the configured budget),
and the response's only content block was a `thinking` block — zero characters of answer
text reached the judge.

**Hypothesised.** `claude-sonnet-5` emits an adaptive-thinking block even though
`answer()` never passes a `thinking` parameter — thinking is not opt-in for this model tier,
and thinking tokens count against `max_tokens` like any other output. `answer()`'s
`max_tokens=1200` was sized without accounting for that. Reasoning over 140 notes (~20k
input tokens) needs materially more thinking budget than reasoning over the 10-30 notes in
the retrieval conditions, so specifically (and only) the `all-140-notes` condition burned
its entire budget on thinking before emitting any answer text, across all 12 queries — the
judge then correctly scored the resulting empty answers at the floor. This was never a
finding about long-context quality; it was a starved-budget artifact that happened to point
in a dramatic, plausible-looking direction.

**Changed.** Raised `answer()`'s `max_tokens` from 1200 to 4096 in
`scripts/ch3_longcontext_vs_rag.py`, with a comment recording the mechanism so it doesn't
silently regress. Separately, before the first run, `JUDGE_TOOL`'s schema had the same
strict-mode defect as D-005 and the `ch2_bakeoff.py` `CLASSIFY_TOOL` fix (`minimum`/
`maximum` on an integer field, no top-level `additionalProperties: false`) — fixed
pre-emptively this time rather than after a crash, since the pattern was now recognisable
on sight. This is the third independent hand-written tool schema this tutorial run has hit
this exact defect in.

**Result.** Rerunning with the `max_tokens` fix flips the outcome to match the tutorial's
stated direction: `all-140-notes` now leads or ties on quality (grounded 2.67, complete
3.50) versus `hybrid-k10` (2.58, 2.08) and `hybrid-k30` (2.42, 2.67) — completeness in
particular favours long-context by a wide margin, which makes sense: nothing relevant can
be missing when every note is already in context. Real cost ratios are ~3.9x (`k10`) and
~2.3x (`k30`), not the tutorial's stated "~12x" — this instance's corpus/pricing evidently
differs — and latency is *higher* for long-context (23.4s p50) than either retrieval
condition (14.8s, 19.6s), which the tutorial doesn't call out at all.

**Decided.** Keep the `max_tokens` fix; the corrected numbers are the ones that go in the
report, not the first run's. Headline conclusion matches §3.11's own framing once corrected:
at this corpus size, retrieval's case is cost and latency, not accuracy — long-context
is not just competitive here, it wins on quality. Flagging the recurring strict-schema bug
as a pattern worth a pre-flight check (every new hand-written tool `input_schema` in this
codebase needs `additionalProperties: false` at every object level and no `minimum`/
`maximum` on numbers) rather than continuing to fix it reactively per-script. **Not** doing:
chasing an exact match to the tutorial's "12x" cost figure — the direction (retrieval is
meaningfully cheaper) is what transfers across instances, not the specific multiplier.

---

<!-- Chapter 4 -->

<!-- Chapter 5 -->

<!-- Chapter 6 -->
