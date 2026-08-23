# Chapter 2 — Machine learning foundations

*You will build: `insighthub/triage.py` — a calibrated model that ranks insights for a
capacity-constrained review queue — and run a text-classification bake-off that produces
a result you will not expect.*
*Time: ~3 hours. API spend: ~$0.50 (only §2.9).*

**The skill:** the discipline that classical ML spent thirty years learning — baselines,
honest splits, metrics that match the decision, calibration, and knowing when your number
is real. None of it stopped being true when LLMs arrived. Most LLM projects fail for
reasons that have nothing to do with LLMs.

---

## 2.1 Why this chapter is here

Two reasons, and the second is the important one.

**Reason one: there is a genuine supervised learning problem in InsightHub.** The medical
strategy team can read about **40 insights a week**. The field produces roughly **250**.
Something has to rank them. That is a supervised ranking problem with a label
(`selected_for_review`) and 2,000 rows of history in
`data/ml/insight_review_history.csv`.

**Reason two: everything you learn here transfers directly to evaluating LLM systems.**
Chapter 5 asks you to decide whether prompt v3 is better than prompt v2. That is a
hypothesis test on a sample. If you don't have the reflexes — *what's the baseline? is
this difference real? did I leak? does my metric match the decision?* — you will iterate
confidently in the wrong direction for weeks. The tabular problem in this chapter is a
cheap, fast place to build those reflexes before the expensive, slow LLM problem needs
them.

---

## 2.2 Look at the data before you model it

```python
import pandas as pd
from insighthub.triage import load_history

df = load_history()
print(df.shape)
print(df["selected_for_review"].value_counts(normalize=True))
print(df.describe().T)
print(df.groupby("category")["selected_for_review"].agg(["mean", "count"]))
```

Twelve feature columns, one binary target, ~16% positive.

Immediately ask three questions of any tabular dataset:

1. **What is the base rate?** 16.1%. A model that predicts "no" for everything is 83.6%
   accurate. Accuracy is now a useless metric and you should stop thinking about it.
2. **Where did the label come from?** `selected_for_review` records what humans *did*, not
   what was *correct*. It carries their biases — if reviewers historically over-weighted
   tier-1 KOLs, the model will learn to over-weight tier-1 KOLs, and deploying it will
   entrench that bias while appearing to validate it. This is not a footnote; in Medical
   Affairs it is the difference between amplifying the loudest academic voices and hearing
   the field. Write it in `DECISIONS.md` as a known limitation.
3. **Is any feature a leak?** A leak is a feature that would not be available at
   prediction time, or that encodes the answer. §2.4 has one.

---

## 2.3 Baselines first, always

Before any model, write down what you're competing against. Two baselines, both in
`triage.py`:

```python
from insighthub.triage import load_history, temporal_split, baseline_majority, baseline_rules

df = load_history()
train, test = temporal_split(df)
for name, s in [("majority", baseline_majority(test)), ("rules", baseline_rules(test))]:
    print(name, s.metrics(), "P@40:", round(s.precision_at_k(40), 3))
```

```
majority  {'base_rate': 0.205, 'roc_auc': 0.500, 'pr_auc': 0.205, 'brier': 0.163}  P@40: 0.300
rules     {'base_rate': 0.205, 'roc_auc': 0.660, 'pr_auc': 0.347, 'brier': 0.167}  P@40: 0.475
```

`baseline_rules` is the heuristic the strategy team uses *today*, written as four lines of
code: tier-1 KOL, or a compliance flag, or lots of corroboration, or strategic alignment.
It gets P@40 of 0.475 — of the 40 insights it surfaces, 19 turn out to be ones humans
selected.

**If your model can't beat this, don't ship a model.** You would be adding a training
pipeline, a monitoring burden and a retraining schedule to reproduce four lines of `if`.
An enormous amount of production ML is exactly this, deployed by people who never
computed the baseline.

Notice also that `rules` has a *worse* Brier score than `majority` (0.167 vs 0.163) while
having much better ranking (ROC-AUC 0.660 vs 0.500). The rules score is a good ordering
and a terrible probability. Keep that distinction — §2.6 is entirely about it.

---

## 2.4 Split honestly: the two traps

### Trap 1: random splits

`train_test_split(df, test_size=0.3)` is the default everyone reaches for and it is wrong
for any system that will be applied to *future* data. Randomly splitting lets the model
train on next month and test on last month. Real deployment never gives you that.

`triage.py` splits on time instead:

```python
def temporal_split(df, cutoff_days=120):
    train = df[df["days_since_captured"] >= cutoff_days]   # older
    test  = df[df["days_since_captured"] <  cutoff_days]   # newer
    return train, test
```

```
train 1396 (base rate 0.141)   test 604 (base rate 0.205)
```

**Stop and look at those base rates.** They differ by 6.4 points. The temporal split has
revealed genuine label shift: recent insights are selected more often. A random split
would have averaged that away and you would have shipped a model that is systematically
under-confident on new data. *That surprise is the entire reason to split temporally.*

### Trap 2: a feature that encodes time

`days_since_captured` is one of the strongest single predictors in the raw data. It is
also excluded from the feature set:

```python
EXCLUDED = ["days_since_captured", "insight_id"]
```

Why: it measures *how long ago something happened relative to a fixed snapshot date*.
Train on rows where it is 120–400 and apply to rows where it is 0–120 and the model
extrapolates a coefficient outside its training range. Worse, in production the value
keeps changing for the same row.

The general rule: **a feature must be computable, with the same meaning, at prediction
time.** If it encodes position in a dataset rather than a property of the thing, either
drop it or re-express it relative to prediction time ("days between capture and now, as of
scoring"). We drop it, and record the decision.

> ### 🛑 Stop and look
> Add `days_since_captured` back into `NUMERIC`, re-run, and watch PR-AUC jump. That jump
> is the feeling of leakage: **it always feels like success.** Every leak you will ever
> ship will announce itself as unusually good results. Train the reflex now — when a
> number is better than you expected, go looking for the reason before you celebrate.

---

## 2.5 Metrics that match the decision

```python
from insighthub.triage import fit_and_score
for kind in ("logreg", "logreg_balanced", "gbm"):
    _, s = fit_and_score(train, test, kind)
    print(f"{kind:16s}", s.metrics(), "P@40:", round(s.precision_at_k(40), 3))
```

Measured on this dataset:

| Model | ROC-AUC | PR-AUC | Brier | P@40 | R@40 |
|---|---|---|---|---|---|
| majority | 0.500 | 0.205 | 0.163 | 0.300 | — |
| rules baseline | 0.660 | 0.347 | 0.167 | 0.475 | — |
| logistic regression | **0.768** | **0.468** | **0.142** | 0.575 | 0.185 |
| logreg, class_weight=balanced | 0.764 | 0.457 | 0.204 | 0.575 | 0.185 |
| gradient boosting | 0.698 | 0.387 | 0.153 | 0.450 | 0.145 |

Four things to take from this table:

**ROC-AUC flatters imbalanced problems.** 0.768 sounds strong. PR-AUC of 0.468 against a
base rate of 0.205 is the honest version: better than random, not miraculous. On any
imbalanced problem, report PR-AUC. ROC-AUC's denominator is dominated by the negatives you
don't care about.

**`class_weight="balanced"` bought nothing and cost a lot.** Identical P@40, marginally
worse PR-AUC, and a Brier score 44% worse (0.204 vs 0.142). Class weighting is a reflex
people apply because imbalance "should" be corrected. It re-weights the loss, which
distorts the output probabilities — and since we need probabilities (§2.6), that is a real
cost for no measurable gain. Reflexes are not evidence.

**Gradient boosting lost to logistic regression** on every metric. With 1,396 rows and twelve features,
the flexible model overfits and the linear one doesn't. "Use the fancier model" is not a
strategy. Start linear; earn complexity.

**The metric that actually matters is P@40**, because the decision is "which 40 do humans
read this week". Not F1, not accuracy, not AUC. Derive your metric from the decision, and
if you cannot describe the decision, you are not ready to model.

### Is 0.575 vs 0.475 a real difference?

This is the question people skip. Bootstrap it:

```bash
PYTHONPATH=src python scripts/ch2_bootstrap.py
```

```
logreg   P@40 = 0.589  95% CI [0.425, 0.750]
rules    P@40 = 0.492  95% CI [0.325, 0.650]
paired difference = +0.099  95% CI [-0.100, +0.275]   P(diff > 0) = 0.82
```

**The confidence interval on the difference includes zero.** At the operating point we
actually care about, 40 items, we do not have enough test data to say the model beats four
lines of `if`. That is not a reason to abandon the model — look at wider k:

| k | logreg P@k | rules P@k | logreg R@k |
|---|---|---|---|
| 40 | 0.575 | 0.475 | 0.185 |
| 100 | 0.480 | 0.430 | 0.387 |
| 200 | 0.415 | 0.310 | 0.669 |

The advantage is consistent and grows with k, which is much more convincing than any
single point estimate. But the honest headline is: *at our stated operating point, the
evidence is weak, and we should either collect more data or widen the review capacity
before claiming a win.*

**Internalise this.** It is exactly the situation you will be in throughout Chapter 5,
when you have 60 eval examples and a prompt change that moves a metric by 5 points.

---

## 2.6 Calibration: the difference between ranking and believing

A ranking says "this is more likely than that." A calibrated probability says "**of the
things I score 0.7, about 70% will be positive.**" You need the second whenever a number
feeds a downstream decision, a cost calculation, or a human's judgement.

```python
from insighthub.triage import fit_and_score, reliability_table
_, s = fit_and_score(train, test, "logreg_balanced")
print(reliability_table(s).to_string(index=False))
```

```
    bin   n  mean_predicted  observed_rate    gap
0.2-0.3  95           0.254          0.084  +0.170
0.4-0.5  94           0.447          0.138  +0.309
0.6-0.7  72           0.646          0.347  +0.299
0.8-0.9  23           0.836          0.435  +0.401
```

The `class_weight="balanced"` model says 0.64 and delivers 0.31. It is wrong by a factor
of two, consistently. Hand that to an analyst as "64% likely to matter" and you have
actively misinformed them.

Fix it with a calibration wrapper — a second model that learns the mapping from raw score
to observed frequency, fit on held-out folds:

```python
_, s2 = fit_and_score(train, test, "logreg_balanced", calibrate="isotonic")
print(s2.metrics())        # brier 0.204 -> 0.143
print(reliability_table(s2).to_string(index=False))
```

Brier drops from 0.204 to 0.143 and the ranking metrics barely move — calibration changes
*what the numbers mean*, not their order.

But look at the calibrated table honestly:

```
    bin   n  mean_predicted  observed_rate    gap
0.1-0.2 170           0.146          0.224  -0.078
0.3-0.4  45           0.353          0.578  -0.225
0.5-0.6   3           0.577          1.000  -0.423
```

Now it is *under*-confident. Why? Because calibration was fit on the training period, where
the base rate was 14.1%, and applied to a test period where it is 20.5%. **Calibration is
the first thing that breaks under distribution shift**, which is why Chapter 6 §6.4
monitors it as a drift signal rather than a one-time fix.

> ### Connect this back to Chapter 1
> In Chapter 1 exercise 5 you bucketed the LLM's self-reported `confidence` field and
> hand-checked the top and bottom buckets. Run `reliability_table` on that data now, once
> you have labels in Chapter 5. An LLM's stated confidence is a *number-shaped token
> sequence*, not a probability, and it is usually badly calibrated — typically compressed
> into 0.7–0.95 regardless of difficulty. If you need a real probability from an LLM
> system, you calibrate it against outcomes exactly as you just did here. You do not ask
> the model nicely.

---

## 2.7 Choosing a threshold: the business constraint wins

Where do you set the cutoff? Not at 0.5 — that number has no meaning here. Two approaches,
and the conflict between them is the lesson.

**Approach A: maximise expected value.** State the costs explicitly:

```python
from insighthub.triage import sweep_thresholds
_, s = fit_and_score(train, test, "logreg")
print(sweep_thresholds(s).to_string(index=False))
```

The defaults encode a business claim: a missed strategically-relevant insight costs ~13×
a wasted five minutes of analyst reading (`cost_false_negative=2.0`,
`cost_false_positive=0.15`). Under those numbers:

```
 threshold  tp   fp  fn  flagged  precision  recall  expected_value
    0.1154 101  201  23      302      0.334   0.815           24.85
    0.1592  86  129  38      215      0.400   0.694           -9.35
    0.2109  ..   ..  ..      ~150      ~0.46   ~0.57          ~ -50
    0.3785  ..   ..  ..       ~41      ~0.56   ~0.19          ~-185
```

EV is maximised at the *lowest* threshold — flag 302 of 604 items.

**Approach B: respect capacity.** The team reads 40 a week. Out of 604 test items spanning
roughly four months, that's a budget of about 40 per week, nowhere near 302.

**These two answers are incompatible, and that is the finding.** The EV calculation is
telling you something real: given how costly misses are, the review queue is
under-resourced. The correct engineering response is not to quietly pick the threshold
that fits capacity and call the problem solved. It is to take the number to the business:

> "At current capacity we surface the top 40, catching 18% of relevant insights. If misses
> cost what you say they cost, doubling review capacity to 80 would catch 40% and pay for
> itself. Here is the curve. Where do you want to be?"

That conversation is the highest-value thing in this chapter, and it is only possible
because you stated the costs explicitly instead of hiding them inside an F1 score.

**In the meantime, ship the ranking, not the threshold.** Sort by score, hand over the top
40, and let the queue length be a business dial rather than a model constant. Systems that
rank degrade gracefully when capacity changes; systems that threshold do not.

---

## 2.8 Error analysis on the ML model

Same discipline as Chapter 1 §1.12 — look at the individual mistakes:

```python
import pandas as pd
_, s = fit_and_score(train, test, "logreg")
test = test.copy(); test["prob"] = s.y_prob

# confident and wrong, in both directions
fp = test[(test.prob > 0.5) & (test.selected_for_review == 0)]
fn = test[(test.prob < 0.1) & (test.selected_for_review == 1)]
print(fp.groupby("category").size().sort_values(ascending=False).head())
print(fn.groupby("category").size().sort_values(ascending=False).head())
```

Ask of each cluster of errors: *is this the model being wrong, or the label being wrong?*
With a human-behaviour label like ours, a systematic false positive often means the model
learned a real pattern that the reviewers apply inconsistently. That's a finding about
your organisation, not a bug in your model, and it belongs in `DECISIONS.md` either way.

---

## 2.9 The bake-off: classical text classification vs an LLM

Now the interesting part. Categorising an insight into the 12-category taxonomy is a text
classification problem. We have `data/ml/insight_text_archive.csv` — 508 labelled
sentences from last year's reviewed insights. Do we need an LLM at all?

### Round 1: TF-IDF + logistic regression

```python
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import cross_val_score, StratifiedKFold

d = pd.read_csv("data/ml/insight_text_archive.csv")
pipe = make_pipeline(
    TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
    LogisticRegression(max_iter=2000, C=5),
)
cv = StratifiedKFold(5, shuffle=True, random_state=0)
print(cross_val_score(pipe, d.text, d.label, cv=cv, scoring="f1_macro").mean())
```

```
1.0
```

**Perfect macro-F1.** Ship it, cancel the LLM contract, go home.

Do not go home. A perfect score on a messy human-judgement task is not a triumph, it is a
symptom. Go and look at the data:

```python
print(d.columns.tolist())
print(d[d.variant_group == "S01-V0"][["text", "label"]].to_string())
```

There's a column you ignored. The archive contains **near-duplicates**: each source
sentence appears four times with light perturbations. `StratifiedKFold` put some copies in
train and others in test, so the model was scored on sentences it had effectively already
seen.

This is **the single most common way real ML projects lie to themselves.** Duplicate
records, the same customer in train and test, the same document chunked twice, the same
patient across visits, the same underlying event reported by two systems.

### Round 2: group-aware splitting

```python
from sklearn.model_selection import StratifiedGroupKFold
g = StratifiedGroupKFold(5, shuffle=True, random_state=0)
print(cross_val_score(pipe, d.text, d.label, cv=g,
                      groups=d.variant_group, scoring="f1_macro").mean())
```

```
0.08
```

From 1.00 to 0.08. The same model, the same data, one honest split.

And harder still — group by *topic*, so the model must classify insights about a subject
it has never seen:

```python
print(cross_val_score(pipe, d.text, d.label, cv=StratifiedGroupKFold(3, shuffle=True, random_state=0),
                      groups=d.topic_group, scoring="f1_macro").mean())
```

```
0.028
```

TF-IDF has learned nothing generalisable. With ~3 distinct source sentences per category,
a bag-of-words model has no signal — it memorised vocabulary. It never had a chance and
the naive CV hid that completely.

### Round 3: the LLM, with zero training examples

Classify the same held-out sentences with the extraction prompt's taxonomy and no
training data at all:

```bash
PYTHONPATH=src python scripts/ch2_bakeoff.py --n 150
```

Fill in your own numbers — this is your experiment, not mine:

| Approach | Training examples | Honest macro-F1 | Cost / 1,000 | p50 latency |
|---|---|---|---|---|
| TF-IDF + LogReg (naive CV) | 400 | **1.00** ← a lie | ~$0 | <1 ms |
| TF-IDF + LogReg (grouped CV) | 400 | 0.08 | ~$0 | <1 ms |
| Embeddings + LogReg (grouped) | 400 | *your number* | ~$0 (local) | ~2 ms |
| LLM zero-shot (Haiku) | **0** | *your number* | *your number* | *your number* |
| LLM zero-shot (Sonnet) | **0** | *your number* | *your number* | *your number* |

The result you will get — and the reason this section exists — is that **the LLM wins
decisively at this data volume, and that is not the usual story.** The received wisdom
("always try the boring model first") is right about *method* and wrong about *conclusion*
here. What the boring model needs is data, and we have almost none.

So state the actual rule, which is about the crossover:

- **Few labels (< ~1,000/class), lexically diverse text, evolving taxonomy** → LLM. Its
  prior *is* your training data. This is InsightHub today.
- **Many labels, stable taxonomy, high volume, latency-sensitive** → classical or a
  distilled small model. This is InsightHub in eighteen months, once the human review
  stream in Chapter 5 has produced thousands of verified labels. Chapter 6 §6.7 does that
  arithmetic.
- **Always** → build the cheap baseline anyway, because a baseline you didn't build is a
  claim you can't defend, and because occasionally it wins and saves you a system.

The embeddings row is the one to pay most attention to: sentence embeddings + logistic
regression is often the best accuracy-per-dollar in the whole table, and almost nobody
tries it. Chapter 3 gives you the embeddings; come back and fill in that row.

---

## 2.10 Clustering: find the themes with maths, name them with an LLM

The last ML idea we need, and it goes straight into Chapter 3.

Twenty notes say the same thing about durability in twenty wordings. Grouping them is
**clustering**, and it should not be done by an LLM. An LLM asked to "find the themes in
these 300 insights" will do something plausible, non-reproducible, and impossible to
evaluate — and it can't hold 300 items in working memory well enough to be consistent.

Instead: embed, cluster, and use the LLM only for the one job it is uniquely good at —
naming the cluster in language a medical director will recognise.

```python
# sketch; the real version is in Chapter 3 §3.13
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

X = embed(texts)                                     # Chapter 3
for k in range(4, 20):
    km = KMeans(k, n_init=10, random_state=0).fit(X)
    print(k, round(silhouette_score(X, km.labels_), 3))
```

Three things to know:

1. **Choosing k is a judgement call with a diagnostic, not an answer.** Silhouette gives
   you a curve; the business decides whether 8 themes or 15 themes is the useful
   granularity for a quarterly report. Run both, show both, ask.
2. **k-means assumes round, similar-sized clusters.** Insight themes are neither — some
   have 40 members, some have 2. HDBSCAN handles varying density and, crucially, has a
   *noise* label for points that belong to no cluster. Singleton insights are real and
   important (a novel observation from one KOL may be the most valuable thing in the
   quarter); an algorithm that must assign everything to a cluster will bury them.
3. **The division of labour is the pattern to remember.** Deterministic maths does the
   grouping — reproducible, cheap, evaluable. The LLM does the linguistic step — naming,
   summarising, explaining. Use each for what it is good at rather than asking the LLM to
   do everything because it can.

---

## 2.11 What ML foundations actually buy you

Everything in this chapter transfers to Chapter 5, where the "model" is a prompt:

| ML habit | Its LLM-engineering form |
|---|---|
| Compute the baseline | Before optimising a prompt, measure: keyword rules? the previous prompt? a smaller model? |
| Split honestly, group-aware | Dev/test/holdout splits; never iterate on your test set; watch for near-duplicate eval cases |
| Metric matches the decision | P@40, not F1 — and in Ch.5, AE recall, not "quality" |
| Report a confidence interval | 60 eval examples give you ±12 points; act accordingly |
| Calibrate before believing a number | LLM self-reported confidence is not a probability |
| A too-good result means a leak | Eval cases that appeared in your prompt as examples |
| Look at individual errors | Error analysis, Ch.5 §5.2 |
| Distribution shift is inevitable | Drift monitoring, Ch.6 §6.4 |

---

## 2.12 Decision log

- **D-007 Metric.** P@40, from the review-queue capacity constraint. PR-AUC as the
  secondary; ROC-AUC reported but not used for decisions.
- **D-008 Split.** Temporal, not random. Documented the 14.1% → 20.5% base-rate shift it
  exposed.
- **D-009 Feature exclusion.** Dropped `days_since_captured` as time-encoding. Recorded
  that adding it back inflates PR-AUC — a leak that looks like success.
- **D-010 Model.** Plain logistic regression over GBM and over class-weighted variants, on
  PR-AUC *and* Brier. Ship the *ranking*, not a fixed threshold.
- **D-011 Significance.** P@40 advantage over the rules baseline is +0.10 with CI
  [−0.10, +0.28] — not significant at n=40. Advantage is consistent at k=100 and k=200.
  Flagged as needing more data before claiming a win.
- **D-012 Capacity finding.** EV-optimal threshold flags ~300 items vs a capacity of 40.
  Escalating as a resourcing question rather than silently thresholding to fit.
- **D-013 Text classification.** LLM zero-shot over TF-IDF for category assignment at
  current label volume. Revisit when the review stream has produced >1,000 verified labels
  per class (Ch.6 §6.7).
- **D-014 Label bias.** `selected_for_review` encodes historical reviewer behaviour, not
  ground truth. Known limitation; do not present model output as objective importance.

---

## 2.13 Exercises

1. **Feel the leak.** Put `days_since_captured` back in. Report the PR-AUC gain. Then
   simulate deployment: score rows with `days_since_captured` set to 0 for all of them,
   as it would be for genuinely new insights. Watch the ranking collapse.
2. **Cost sensitivity.** Re-run `sweep_thresholds` with `cost_false_negative` at 0.5, 2.0
   and 10.0. At what ratio does the EV-optimal threshold fall inside a capacity of 40?
   What would you have to believe about the business for that to be the right number?
3. **Fairness-ish audit.** Compute P@40 separately by `region`. Is the model surfacing
   EMEA and APAC insights at the same rate as US ones? If not, is that the model, the
   label, or the world? What would you do about each?
4. **How much data do you need?** Retrain on 10%, 25%, 50%, 100% of the training rows and
   plot PR-AUC. Does the curve suggest more data would help, or that you're
   feature-limited? This same plot in Chapter 5 tells you how many eval examples to label.
5. **Fill in §2.9's table.** Do the embeddings row after Chapter 3. Then answer: at what
   number of labelled examples per class would you switch from the LLM to the classical
   model? Justify with the curve from exercise 4, not with intuition.

---

**Next:** [Chapter 3 — Grounding models with data](03-grounding-with-data.md) — where you
build a vector index from scratch, and then find out whether it beats sending everything.
