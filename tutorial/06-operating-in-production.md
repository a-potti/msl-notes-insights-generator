# Chapter 6 — Operating in production

*You will build: `observability.py` (tracing, metrics, drift, alerting), `serve.py` (a
FastAPI service), `scripts/ci_gate.py` (a risk-calibrated regression gate), a GitHub
Actions workflow, and a cost/latency optimisation pass with measured savings.*
*Time: ~5 hours. API spend: ~$3.*

**The skill:** operating software whose output you cannot predict, whose cost is
per-request, and whose failure modes are silent. Traditional ops assumes deterministic
components that fail loudly. Almost nothing here fails loudly.

---

## 6.1 Tracing: the three lines you get for free

Turning tracing on is trivial *because we designed for it in Chapter 1*:

```python
from insighthub import observability as obs
obs.start_tracing(run_id="ingest-2026-08-21")
# ... run anything ...
obs.print_summary()
```

Every call already went through `llm.call`, which already had an observer hook. Retrofit
this into a codebase where forty call sites hit the SDK directly and you will touch forty
files, miss six, and never trust the numbers. **The instrumentation seam is a design
decision you make on day one or pay for forever.**

```
60 calls, $0.6299
step                       n        $     p50     p95   in tok  cache  retry  trunc
agent                     20   0.2192   2.73s   4.43s    1,439    75%    25%    35%
compliance_gate           11   0.1098   2.68s   3.96s    1,701    46%    27%    46%
extract                   10   0.1022   2.17s   5.43s    1,551    50%    40%    40%
judge                     19   0.1987   1.89s   5.08s    1,553    53%    26%    26%
```

Four columns people forget and then need at 2am:

- **p50 *and* p95.** p50 is how it feels most of the time. p95 is how it feels to the
  person about to complain. A mean hides both.
- **cache hit rate.** If this is 0% you are paying full price for a prefix you thought was
  cached (Chapter 1 §1.7). It drops silently when someone edits a "stable" block.
- **retry rate.** A creeping retry rate is the earliest signal of provider trouble, and it
  shows up in your latency before it shows up in anyone's status page.
- **truncation rate.** `stop_reason == "max_tokens"` means the model was cut off
  mid-answer. This is the single most under-monitored failure in LLM systems: the output
  is well-formed, plausible, and *incomplete*, and no exception is raised.

### What you must not log

```python
# NOTE what is deliberately NOT recorded: prompt and completion text.
```

Call notes contain HCP names and clinical detail. A trace store is a much softer target
than your primary database — more copies, looser access controls, longer retention,
shipped to third-party tools. Log identifiers, token counts, latency, cost and outcomes;
keep payloads in the system that already has the right controls and link by ID.

The counter-argument is real: debugging without payloads is harder. The workable
compromise is a short-retention sampled store (1% of traces, 7 days, access-logged) plus
full metadata forever.

---

## 6.2 The service

```bash
PYTHONPATH=src uvicorn insighthub.serve:app --reload
curl -s localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question":"What are EMEA KOLs saying about durability since ECCO?"}' | jq
```

The routes are boring. Three details are not:

**Every response carries a `trace_id`.** A user says "the answer at 14:32 was wrong". With
a trace ID in the response, that is one query. Without it, it is an afternoon.

**Every response carries `versions`.** Prompt version, taxonomy version, embedding model,
pipeline version. When output quality changes, the first question is always "what
changed?", and this makes it answerable in five seconds.

**`/feedback` is the most valuable endpoint in the service.**

```python
class Feedback(BaseModel):
    trace_id: str
    accepted: bool
    corrected_text: str | None = None
```

Offline evals tell you how you do on 60 examples you chose. Feedback tells you how you do
on what people actually asked. And every correction is a free labelled example (Chapter 5
§5.9). Design the review UI so accepting is one click and correcting captures the
correction — you are building your training set as a side effect of the product working.

---

## 6.3 Online metrics: what to watch when there are no labels

Production has no ground truth. So you need proxies, and the good ones are behavioural:

| Metric | What it really tells you | Why it beats the obvious alternative |
|---|---|---|
| **MSL edit rate on extracted insights** | Quality, as judged by the person who was in the room | The single best signal in this system. Nobody edits something that's right. |
| Insight acceptance rate | Same, coarser | Free, one click |
| Themes surfaced that reviewers reject | Clustering quality | Notices bad clusters before a report does |
| Analyst follow-up-question rate | Whether first answers are complete | A high rate means shallow answers, not curious users |
| Time-to-first-token | Perceived speed | Correlates with abandonment better than total latency |
| Cost per accepted insight | Unit economics | Cost per *call* flatters a system that produces junk cheaply |
| PV routing volume vs manual audit | Compliance safety | The one you would have to explain to a regulator |

**Cost per accepted insight is the metric to put on the dashboard.** Cost per call rewards
producing more, cheaper garbage. Divide by the thing you actually wanted.

And run a **manual audit sample**: every week, a human reviews 20 random notes fully and
independently. That number is your only unbiased quality estimate, it costs about two
hours, and it is the thing that catches the failure your automated metrics were not
designed to see. Budget for it permanently.

---

## 6.4 Drift

Three distinct things drift, and they need different responses:

**1. Input drift.** A congress happens and the field's vocabulary changes overnight.
`population_stability_index` over the category mix:

```python
from insighthub.observability import drift_report, check_alerts
d = drift_report(baseline_rows, current_rows)
print(d["category_psi"])
```

PSI rules of thumb, from credit risk where it originates: `< 0.10` no meaningful shift,
`0.10–0.25` investigate, `> 0.25` act. Note that a genuine post-congress shift and a
silently broken categoriser produce *the same signal* — which is exactly why you
investigate rather than auto-remediate.

**2. Model drift.** The provider updates a model behind a floating alias and behaviour
changes. Two defences: pin a dated model ID in production, and keep a **golden set** — 20
fixed inputs re-run daily, with outputs diffed. When the diff spikes on a day you shipped
nothing, you have your answer.

**3. Calibration drift.** Chapter 2 §2.6 already showed it: the triage model was
calibrated on a 14.1% base period and applied to a 20.5% one. Track predicted-vs-observed
rates monthly. Calibration is the first thing to break and the last thing anyone checks.

### Alerting that people don't disable

```python
DEFAULT_THRESHOLDS = {
    "unfaithful_verbatim_rate": (">", 0.03, "page"),
    "empty_extraction_rate":    (">", 0.25, "ticket"),
    "category_psi":             (">", 0.25, "ticket"),
    "ae_flag_rate_drop":        (">", 0.40, "page"),
    "truncation_rate":          (">", 0.02, "page"),
}
```

Two severities only: **page** wakes a human, **ticket** is looked at tomorrow. If you
cannot say which one an alert is, it is a dashboard metric, not an alert. An alert nobody
acts on trains everyone to ignore alerts, including the one that mattered.

Note the asymmetry in `ae_flag_rate_drop`: a *drop* in the AE flag rate pages, because it
may mean reportable events are being missed. A *rise* is merely expensive. **Alert on the
direction that is dangerous, not on change.**

---

## 6.5 Regression testing and CI

Chapter 1 §1.4 proved you cannot write `assert output == expected`. So gates are
statistical, and they are **risk-calibrated**:

```python
GATES = [
    # BLOCKING — safety and correctness. Build does not ship.
    ("blocking", "code_evals.verbatim_is_substring",   "min", 0.97, 0.01),
    ("blocking", "code_evals.no_promotional_language", "min", 1.00, 0.00),
    ("blocking", "code_evals.injection_resisted",      "min", 1.00, 0.00),
    # WARN — quality. Opens a ticket.
    ("warn", "extraction.recall",          "min", 0.55, 0.05),
    ("warn", "extraction.category_accuracy","min", 0.75, 0.05),
]
```

```bash
PYTHONPATH=src python scripts/ci_gate.py --run runs/candidate.jsonl \
    --baseline runs/baseline_test.jsonl --split test
```

**Measured**, running a deliberately degraded candidate against a good baseline:

```
[FAIL] code_evals.verbatim_is_substring     0.8250  (baseline 0.8000, delta +0.025)  <- below floor 0.97
[FAIL] code_evals.no_promotional_language   0.9000  (baseline 0.9500, delta -0.050)  <- regressed 0.050 vs baseline (tolerance 0.0)
[WARN] extraction.recall                    0.4324  (baseline 0.6622, delta -0.230)  <- regressed 0.230 vs baseline
[PASS] extraction.category_accuracy         0.8438  (baseline 0.8571, delta -0.013)

BLOCKED: 2 blocking gate(s) failed.
```

Look carefully at the first line. It **failed on the absolute floor while improving
against the baseline.** Both checks matter: a floor stops you from ratcheting downward one
acceptable regression at a time, and a delta catches a sudden break. Ship only one and you
get slow rot or brittle alarms respectively.

### Two tiers, because evals cost money

`.github/workflows/evals.yml`:

| Tier | When | What | Cost |
|---|---|---|---|
| **fast** | every commit | pytest + code evals on the offline fixture, `INSIGHTHUB_EMBED_BACKEND=hash` | $0 |
| **slow** | nightly, or on a `run-evals` label | judge validation → real extraction on `test` → `ci_gate.py` | ~$3 |

The `hash` embedding backend earns its keep here: CI needs no model download and no API
key for the fast tier, so the deterministic checks run on every commit rather than being
skipped for being slow.

Note the ordering in the slow job: **judge validation runs first.** If the judge has
drifted below its bar, no judge-derived number in that run means anything, and the
pipeline should say so rather than reporting numbers.

Now use the `holdout` split. It has been untouched since Chapter 0 and it simulates data
arriving after you finished tuning:

```bash
PYTHONPATH=src python scripts/ch5_iterate.py --version v3 --split holdout
PYTHONPATH=src python -m insighthub.evals.run --run runs/ch5_holdout_v3.jsonl --split holdout
```

If holdout is meaningfully worse than test, you overfit to your dev set. That is normal,
it is information, and it is the number to quote when someone asks how the system will
perform on next month's notes.

---

## 6.6 Incident response

Two rehearsals. Do them; the first time should not be the real time.

### Incident 1 — silent quality collapse

*Symptom:* MSL edit rate went from 12% to 34% over three days. No errors, no alerts.

The runbook:

1. **What changed?** Query traces by `versions`. Prompt version? Model ID? Taxonomy?
   Index rebuild? If nothing on your side changed, suspect the model or the input.
2. **Which step?** `obs.print_summary()` by step. Did `extract`'s mean output tokens drop?
   Did `truncation_rate` rise? Did `cache_hit_rate` fall to zero — meaning someone put a
   timestamp in the "stable" prefix and you are now also paying 3× more?
3. **Reproduce.** Run the golden set. Diff against last week's outputs.
4. **Bisect.** Re-run yesterday's inputs with last week's prompt version. One variable.
5. **Mitigate before you fix.** Roll back the prompt/model. Fix afterwards, with an eval.

### Incident 2 — prompt injection in the wild

*Symptom:* the security review queue gets a note containing text addressed to the model.

1. **Contain.** Quarantine that note and every insight derived from it. Do not delete —
   you need it for the investigation.
2. **Scope.** Search all notes for similar patterns. How long has it been there? Which
   reports included insights from it?
3. **Assess capability.** What tools *could* the agent have called? For InsightHub the
   answer is "read-only ones" (Chapter 4 §4.9), which turns an incident into a finding.
   If the answer were "an email tool", you would be doing breach notification.
4. **Attribute.** Which MSL account submitted it? Injection usually means either a
   compromised account or an upstream system that ingests third-party text.
5. **Report.** In pharma this is likely a security incident with regulatory implications.
   Know your reporting path before you need it.
6. **Fix the class, not the instance.** Add the pattern to `INJECTION_PATTERNS`, add the
   note to your eval set as a permanent test case, and re-examine whether any tool
   acquired new capability since the last review.

---

## 6.7 Cost and latency

Only now — with evals and traces in place — can you optimise safely. Every technique below
trades something for money, and without evals you cannot see what you traded.

Baseline for InsightHub at realistic volume (8 MSLs × 15 notes/week × 50 weeks =
6,000 notes/year, plus ~20 analyst questions/day):

| Workload | Volume/yr | Per unit | Per year |
|---|---|---|---|
| Ingestion (extract + gate) | 6,000 | ~$0.004 | ~$24 |
| Analyst questions | ~5,000 | ~$0.06 | ~$300 |
| Quarterly reports | 4 | ~$1.50 | ~$6 |
| Nightly eval suite | 365 | ~$3 | ~$1,095 |

**Read that table before optimising anything.** The dominant cost is *the eval suite*, and
the second is analyst questions. Ingestion — the thing that feels expensive because it's
high volume — is $24/year. Half of all LLM cost-optimisation work is spent on the cheapest
part of the system because nobody made this table.

The techniques, in the order they usually pay:

**1. Caching.** Done in Chapter 1. Verify `cache_hit_rate` in your traces is what you
think. This is free and has no quality risk.

**2. Model routing.** Measure per step, then route. Chapter 1's bake-off said Haiku
paraphrased `verbatim` spans 6% of the time — disqualifying for extraction. But for
*compliance gating*, where the model's job is high-recall flagging and precision is
explicitly not the goal, Haiku is fine. Re-run the bake-off per step; the right model is
almost never the same one everywhere.

**3. Prompt shortening.** Real savings, real quality risk. Only with evals. Measure the
token reduction *and* the eval delta, and put both in the decision log.

**4. Batch processing.** Ingestion is not latency-sensitive. A batch API typically offers
a substantial discount for asynchronous work. This is the highest-leverage change for the
ingestion workload and it costs nothing in quality.

**5. Agentic workflow simplification.** Look at your traces: how many tool calls does the
median question take? If most questions take two searches and the same two searches, a
fixed workflow for the common case with agent fallback for the rest can halve analyst cost.
**Chapter 4 §4.14 exercise 5 is this measurement** — the agent is not always worth its
price.

**6. Distillation.** Once the human review stream (§6.2) has produced thousands of
verified labels, fine-tuning a small model on the extraction task becomes viable. The
arithmetic:

```
break-even ≈ fine-tuning cost / (per-call saving × calls per year)
```

At 6,000 calls/year and a saving of $0.003/call ($18/year), a fine-tune costing hundreds
of dollars **never pays back on cost alone**. It might still be right — for latency, for
data residency, for removing a vendor dependency — but say which, and don't dress a
strategic decision as a cost saving.

**Measure it end to end:**

```bash
PYTHONPATH=src python scripts/ch6_cost_report.py --run-id ingest-2026-08-21
```

---

## 6.8 Decision log

- **D-037 Trace schema.** Metadata and identifiers only; no prompt or completion text.
  Sampled payload store (1%, 7 days, access-logged) as the debugging compromise.
- **D-038 Primary online metric.** MSL edit rate on extracted insights, plus a weekly
  20-note manual audit as the unbiased estimate.
- **D-039 Unit economics.** Cost per *accepted* insight, not cost per call.
- **D-040 Alert policy.** Two severities. Alert on the dangerous direction (AE flag rate
  *drop*), not on change.
- **D-041 CI tiers.** Deterministic evals on every commit (hash backend, $0); judge and
  live evals nightly. Judge validation runs first and gates the rest of the job.
- **D-042 Gate design.** Absolute floors AND baseline deltas. Blocking reserved for safety
  and correctness; quality regressions open tickets.
- **D-043 Cost model.** Eval suite dominates annual spend, not inference. Optimisation
  effort directed at eval frequency and analyst questions, not at ingestion.
- **D-044 Distillation.** Not justified on cost at current volume. Revisit if latency or
  data residency becomes a requirement.

---

## 6.9 Exercises

1. **Break the cache.** Add `datetime.now()` to the system prefix. Watch `cache_hit_rate`
   go to zero and cost roughly triple. Then find it using only the metrics table — that is
   the skill.
2. **Golden set.** Build one: 20 fixed inputs, outputs stored, a script that diffs today
   against the stored version and reports similarity. Run it daily for a week. What is the
   natural day-to-day variation? That number is your detection floor for model drift.
3. **Simulate model drift.** Run the holdout split with a different model and treat the
   result as an incident. Follow the §6.6 runbook and time yourself. Which step was
   slowest, and what instrumentation would have made it fast?
4. **The real cost table.** Instrument a full ingest of all 140 notes plus 20 agent
   questions. Extrapolate to 10× MSLs. Which line item grows fastest? Does your answer
   change what you would optimise?
5. **Workflow vs agent, for money.** Implement the fixed-workflow analyst from Chapter 4
   exercise 5, route by a cheap difficulty classifier, and measure cost and quality
   against always-agent on 20 questions. What fraction of questions can safely take the
   cheap path?
6. **Write the incident report.** Pick either incident from §6.6, run it, and write the
   postmortem: timeline, detection, root cause, contributing factors, what you changed,
   and what monitoring would have caught it sooner. This is the artefact that makes the
   next incident shorter.

---

**Next:** [Chapter 7 — Capstone](07-capstone.md)
