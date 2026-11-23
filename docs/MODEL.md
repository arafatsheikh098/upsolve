# The Upsolve skill model

This document explains how Upsolve turns a Codeforces submission history into per-tag skill
estimates, weak spots and practice problems. The code lives in `backend/app/analysis/`.

## 1. From submissions to attempts (`features.py`)

Submissions are grouped into one **attempt** per problem:

| field | meaning |
|---|---|
| `solved` | any submission got `OK` |
| `wrong_before_ac` | non-OK verdicts before the first `OK` |
| `attempted_in_contest`, `solved_in_contest` | participant type `CONTESTANT` / `OUT_OF_COMPETITION` |
| `rating`, `tags` | latest non-empty values seen (CF assigns them after the round) |

Compilation errors, `SKIPPED`, `TESTING` and similar verdicts are ignored. They say nothing about
whether the idea was right. The `*special` tag (April Fools and similar) is dropped.

### Selection bias and contest misses

People mostly submit to problems they expect to solve. For a typical user well over 90% of attempts
are accepted, which leaves the model almost nothing to learn from. Rated contests fix part of this:
the user **saw every problem**. So for every contest the user took part in, each problem they never
submitted to is added as an unobserved failure with **weight 0.5**, because running out of time is
weaker evidence than a wrong answer.

## 2. The model (`skill.py`)

For problem *p* with rating *rₚ* and tags *T(p)*:

```
P(solve p) = σ( k · (A + b + (1/|T(p)|) · Σ_{t∈T(p)} δₜ − rₚ) ),   k = ln(10) / 400
```

- **A** is the anchor: the user's Codeforces rating (or their median solved rating if unrated).
- **b** is a baseline offset, learned. It absorbs whatever is left of the selection bias.
- **δₜ** is a per-tag offset, learned. A problem with several tags splits the effect evenly.

`k = ln(10)/400` is the Elo/Codeforces scale. A 400-point gap is 10:1 odds, so every number the
model produces reads as rating points.

### Labels

The outcome is a soft label in [0, 1]:

```
y = 0                                   if never solved
y = 1 − min(0.5, 0.1 · wrong_before_ac)   otherwise
```

An accept after six wrong answers is weaker evidence of mastery than a clean accept, but still
clearly a success.

### Weights

Each attempt's weight is `miss_weight × 0.5^(n_later / 150)`, where `n_later` is the (weighted)
number of attempts made after it. Decay is by **activity, not calendar time**. A user who took a
year off hasn't forgotten everything, and their old attempts are still the best evidence available.
Only newer practice pushes old evidence out.

### Fitting

The parameters θ = (b, δ₁…δₘ) get Gaussian priors:

```
b  ~ N(0, 400²)      δₜ ~ N(0, 150²)
```

and are fitted by **maximum a posteriori** estimation:

```
minimise  Σᵢ wᵢ · [ log(1 + e^{zᵢ}) − yᵢ zᵢ ]  +  ½ θᵀ Λ θ,     zᵢ = k(A + xᵢᵀθ − rᵢ)
```

The objective is convex (logistic loss plus a quadratic), so Newton's method with backtracking
converges in about 5 iterations. Gradient and Hessian:

```
g = k · Xᵀ (w ⊙ (p − y)) + Λθ
H = k² · Xᵀ diag(w ⊙ p ⊙ (1 − p)) X + Λ
```

With roughly 40 parameters, a fit takes a few milliseconds. That's cheap enough to refit the model
at the end of each of the last 12 months for the "skill over time" chart, without storing any
snapshots.

### Identifiability and uncertainty

Adding a constant *c* to every δₜ and subtracting it from *b* leaves every prediction unchanged.
**Only differences between tags are identified by the data.** Upsolve therefore reports each tag
relative to the user's **exposure-weighted average tag**:

```
δ̄ = Σₜ πₜ δₜ,    πₜ ∝ Σᵢ wᵢ xᵢₜ        reported δₜ' = δₜ − δ̄
level = A + b + δ̄
```

Uncertainty comes from the **Laplace approximation**: the posterior covariance is Σ = H⁻¹ at the
optimum. The variance of a reported offset is the variance of the matching contrast,
`Var(δₜ') = cᵀ Σ c` with `c = eₜ − π`. Without this step, uncertainty about the shared shift (which
the data can't resolve) inflates every interval.

Each tag gets a label:

| label | rule |
|---|---|
| `insufficient` | fewer than 3 real attempts |
| `weak` | the whole 90% interval is below 0 |
| `strong` | the whole 90% interval is above 0 |
| `average` | otherwise |

## 3. Weak spots (`report.py`)

For each tag that appears among recent problems near the user's level (rated level − 100 to
level + 400, from the last 3 years of rounds):

```
importance   = share of those problems carrying the tag, scaled so the most common tag = 1
coverage_gap = max(0, 1 − user_share / pool_share)
score        = importance · ( max(0, −δₜ') / 100  +  0.75 · coverage_gap )
```

The kind is `skill` if the tag is weak (or leaning weak), and `coverage` if the user practises it at
less than half its share among problems at their level. Each weak spot comes with its evidence:
attempts, solve rate, average wrong answers before AC, hardest solve and recent failures.

## 4. Recommendations (`recommend.py`)

- **Weak-tag picks.** Unsolved, unattempted problems carrying the tag, rated within ±300 of the
  tag's level, with a predicted chance between 35% and 75%. Candidates are scored by closeness to
  **55%**, plus bonuses when the tag is central (fewer tags) and the round is recent. Quality
  filters require ≥ 100 solvers, a round from the last 6 years, and no `*special` tag.
- **Stretch.** Above the user's level, about 30% predicted chance (range 15–45%).
- **Upsolve.** A previously failed problem, resurfaced with spaced repetition at 1, 3, 7 and then
  every 21 days after it was last shown.
- **Determinism.** One of the top 8 candidates is picked at random, with the random generator
  seeded by `handle:date`. The same day gives the same plan, and each day gives a different one.

## 5. Validation

`backend/tests/test_skill_model.py` checks the model against simulated users:

- **Recovery.** With a known level and per-tag offsets, a fit on 4,000 simulated attempts puts every
  tag within 3 standard errors of the truth, and the standard errors are under 40 points.
- **Calibration.** Over 40 simulated users, the share of 90% intervals that contain the true value
  must be between 80% and 98%.
- **Shrinkage.** A single failure on a rare tag is labelled `insufficient`, not `weak`.
- **Decay.** Old failures fade as newer successes pile up, and idle time changes nothing.

## 6. Limitations

- Codeforces tags are coarse and sometimes missing, and unrated problems are skipped.
- The model can't see time pressure, editorials read, or help received.
- With few attempts or mostly easy practice, intervals are wide. The UI says so instead of guessing.
