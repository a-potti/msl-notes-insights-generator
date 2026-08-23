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

<!-- Chapter 2 -->

<!-- Chapter 3 -->

<!-- Chapter 4 -->

<!-- Chapter 5 -->

<!-- Chapter 6 -->
