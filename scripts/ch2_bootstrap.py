#!/usr/bin/env python3
"""Chapter 2 §2.5 — is the model's advantage over the rules baseline real?

Bootstrap resampling of the test set, paired so the two systems see the same
resamples. Costs nothing and takes two seconds. There is no excuse for reporting
a point estimate without one of these.
"""
import numpy as np

from insighthub.triage import (baseline_rules, fit_and_score, load_history,
                               temporal_split)

K = 40          # the review-queue capacity
N_BOOT = 3000


def main() -> None:
    df = load_history()
    train, test = temporal_split(df)
    _, model = fit_and_score(train, test, "logreg")
    rules = baseline_rules(test)

    rng = np.random.default_rng(0)
    idx = np.arange(len(test))

    def boot(scored):
        vals = []
        for _ in range(N_BOOT):
            b = rng.choice(idx, len(idx), replace=True)
            yt, yp = scored.y_true[b], scored.y_prob[b]
            vals.append(yt[np.argsort(-yp)[:K]].mean())
        v = np.array(vals)
        return v.mean(), np.percentile(v, 2.5), np.percentile(v, 97.5)

    for name, s in (("logreg", model), ("rules", rules)):
        m, lo, hi = boot(s)
        print(f"{name:8s} P@{K} = {m:.3f}  95% CI [{lo:.3f}, {hi:.3f}]")

    # Paired difference — the number that actually answers the question.
    diffs = []
    for _ in range(N_BOOT):
        b = rng.choice(idx, len(idx), replace=True)
        yt = model.y_true[b]
        a = yt[np.argsort(-model.y_prob[b])[:K]].mean()
        c = yt[np.argsort(-rules.y_prob[b])[:K]].mean()
        diffs.append(a - c)
    d = np.array(diffs)
    print(f"\npaired difference = {d.mean():+.3f}  "
          f"95% CI [{np.percentile(d, 2.5):+.3f}, {np.percentile(d, 97.5):+.3f}]  "
          f"P(diff > 0) = {(d > 0).mean():.2f}")

    print(f"\nprecision/recall at other operating points:")
    for k in (40, 100, 200):
        print(f"  k={k:3d}  logreg P@k={model.precision_at_k(k):.3f} "
              f"R@k={model.recall_at_k(k):.3f} | rules P@k={rules.precision_at_k(k):.3f}")


if __name__ == "__main__":
    main()
