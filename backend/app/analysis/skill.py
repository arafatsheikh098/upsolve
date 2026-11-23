"""Per-tag skill model.

The model is a logistic (Elo-style) regression on the same scale as Codeforces ratings:

    P(solve p) = σ( k · (A + b + Σ_{t ∈ tags(p)} δ_t / |tags(p)| − r_p) ),     k = ln(10) / 400

* A   = anchor: the user's current Codeforces rating (or the median solved rating if unrated)
* b   = baseline offset, fitted. It absorbs selection bias: people mostly submit to problems they
        expect to solve, so on attempted problems they look stronger than their rating.
* δ_t = tag offset, fitted. Negative means the user does worse on this tag than on their other
        attempted problems of the same difficulty. Reported relative to the user's average tag.
* r_p = the problem's rating.

Parameters are fitted by MAP with Gaussian priors (δ_t ~ N(0, 150²), b ~ N(0, 400²)), so tags
with little data are shrunk towards zero rather than producing wild estimates.

Recent attempts count more: an attempt's weight halves for every 150 attempts made after it. Decay
is by activity, not by calendar time, because skill changes when you practise. Someone who took a
year off hasn't forgotten everything, and their old attempts are still the best evidence available.

Uncertainty comes from the Laplace approximation: the posterior covariance is the inverse Hessian
at the optimum, which gives a 90% interval per tag.

The objective is convex, so Newton's method converges in a handful of iterations; with ~40
parameters a fit takes a few milliseconds. See docs/MODEL.md for the derivation.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import median

import numpy as np

from app.analysis.features import Attempt

K = math.log(10) / 400
Z90 = 1.6448536269514722

DEFAULT_PRIOR_SD = 150.0
DEFAULT_BASELINE_SD = 400.0
DEFAULT_HALF_LIFE_ATTEMPTS = 150.0
MIN_ATTEMPTS_FOR_LABEL = 3


@dataclass(frozen=True)
class TagSkill:
    tag: str
    delta: float
    sd: float
    exposure: float  # time-weighted effective number of problems carrying this tag
    attempts: int
    solved: int

    @property
    def ci_low(self) -> float:
        return self.delta - Z90 * self.sd

    @property
    def ci_high(self) -> float:
        return self.delta + Z90 * self.sd

    @property
    def label(self) -> str:
        if self.attempts < MIN_ATTEMPTS_FOR_LABEL:
            return "insufficient"
        if self.ci_high < 0:
            return "weak"
        if self.ci_low > 0:
            return "strong"
        return "average"


@dataclass(frozen=True)
class SkillFit:
    anchor: float
    # Problem rating at which the user solves about half of the problems they attempt (on their
    # average tag). Tag offsets in `tags` are relative to this level.
    level: float
    level_sd: float
    tags: dict[str, TagSkill]
    n_attempts: int
    iterations: int
    converged: bool

    def tag_level(self, tag: str) -> float:
        t = self.tags.get(tag)
        return self.level + (t.delta if t else 0.0)

    def offset(self, tags: Sequence[str]) -> float:
        """Mean offset of a problem's tags; unknown tags count as average (0)."""
        if not tags:
            return 0.0
        return sum(self.tags[t].delta if t in self.tags else 0.0 for t in tags) / len(tags)

    def predict(self, rating: float, tags: Sequence[str]) -> float:
        """Predicted probability of solving a problem with this rating and these tags."""
        z = K * (self.level + self.offset(tags) - rating)
        return 1.0 / (1.0 + math.exp(-z))


def outcome(a: Attempt) -> float:
    """Soft label: 1 for a clean solve, down to 0.5 for a solve after many wrong attempts, 0 if
    never solved. This keeps the information in 'solved, but with 6 WAs'."""
    if not a.solved:
        return 0.0
    return 1.0 - min(0.5, 0.1 * a.wrong_before_ac)


def default_anchor(attempts: Iterable[Attempt]) -> float:
    solved = [a.rating for a in attempts if a.solved and a.rating is not None]
    return float(median(solved)) if solved else 800.0


def fit_skill(
    attempts: Sequence[Attempt],
    *,
    now: datetime,
    anchor: float | None = None,
    tag_universe: Iterable[str] = (),
    prior_sd: float = DEFAULT_PRIOR_SD,
    baseline_sd: float = DEFAULT_BASELINE_SD,
    half_life_attempts: float = DEFAULT_HALF_LIFE_ATTEMPTS,
    max_iter: int = 50,
    tol: float = 1e-4,
) -> SkillFit:
    usable = sorted(
        (a for a in attempts if a.rating is not None and (a.last_at is None or a.last_at <= now)),
        key=lambda a: a.last_at or now,
    )
    if anchor is None or anchor <= 0:
        anchor = default_anchor(usable)

    tags = sorted({t for a in usable for t in a.tags} | set(tag_universe))
    col = {t: i + 1 for i, t in enumerate(tags)}
    n, m = len(usable), len(tags) + 1

    x = np.zeros((n, m))
    x[:, 0] = 1.0
    r = np.empty(n)
    y = np.empty(n)
    w = np.empty(n)
    later = 0.0  # weighted count of attempts made after the current one (iterating newest first)
    for i in range(n - 1, -1, -1):
        a = usable[i]
        assert a.rating is not None
        r[i] = a.rating
        y[i] = outcome(a)
        w[i] = a.weight * 0.5 ** (later / half_life_attempts)
        later += a.weight
        for t in a.tags:
            x[i, col[t]] = 1.0 / len(a.tags)

    prior_prec = np.full(m, 1.0 / prior_sd**2)
    prior_prec[0] = 1.0 / baseline_sd**2

    def loss(theta: np.ndarray) -> float:
        z = K * (anchor + x @ theta - r)
        # log(1 + e^z) computed stably
        nll = np.sum(w * (np.logaddexp(0.0, z) - y * z))
        return float(nll + 0.5 * np.sum(prior_prec * theta**2))

    theta = np.zeros(m)
    current = loss(theta)
    converged = False
    it = 0
    for it in range(1, max_iter + 1):  # noqa: B007
        z = K * (anchor + x @ theta - r)
        p = 1.0 / (1.0 + np.exp(-z))
        grad = K * (x.T @ (w * (p - y))) + prior_prec * theta
        hess = (K**2) * (x.T * (w * p * (1 - p))) @ x + np.diag(prior_prec)
        step = np.linalg.solve(hess, grad)
        # Newton step with backtracking; the objective is convex so this always makes progress.
        scale = 1.0
        improved = False
        while scale > 1e-4:
            candidate = theta - scale * step
            cand_loss = loss(candidate)
            if cand_loss <= current + 1e-12:
                improved = True
                break
            scale /= 2
        if not improved:  # already at the optimum (to numerical precision)
            converged = True
            break
        theta, current = candidate, cand_loss
        if np.max(np.abs(scale * step)) < tol:
            converged = True
            break

    z = K * (anchor + x @ theta - r)
    p = 1.0 / (1.0 + np.exp(-z))
    hess = (K**2) * (x.T * (w * p * (1 - p))) @ x + np.diag(prior_prec)
    cov = np.linalg.inv(hess)

    exposure = (x[:, 1:] * w[:, None]).sum(axis=0) if n else np.zeros(m - 1)
    attempts_by_tag = {t: 0 for t in tags}
    solved_by_tag = {t: 0 for t in tags}
    for a in usable:
        if not a.observed:
            continue
        for t in a.tags:
            attempts_by_tag[t] += 1
            solved_by_tag[t] += int(a.solved)

    # Only differences between tags are identified by the data: adding c to every δ and
    # subtracting c from b leaves every prediction unchanged. So we report each δ relative to the
    # user's exposure-weighted average tag, and take its variance from the matching contrast of the
    # posterior covariance. Uncertainty about the shared shift then doesn't blur the comparison.
    seen = [col[t] for t in tags if exposure[col[t] - 1] > 0]
    avg = np.zeros(m)
    if seen:
        weights = exposure[[c - 1 for c in seen]]
        weights = (
            weights / weights.sum() if weights.sum() > 0 else np.full(len(seen), 1 / len(seen))
        )
        avg[seen] = weights
    mean_delta = float(avg @ theta)

    level_vec = avg.copy()
    level_vec[0] = 1.0
    level_sd = math.sqrt(max(0.0, float(level_vec @ cov @ level_vec)))

    skills: dict[str, TagSkill] = {}
    for t in tags:
        j = col[t]
        if exposure[j - 1] > 0:
            contrast = -avg
            contrast[j] += 1.0
            delta = float(theta[j]) - mean_delta
            sd = math.sqrt(max(0.0, float(contrast @ cov @ contrast)))
        else:
            delta, sd = 0.0, prior_sd
        skills[t] = TagSkill(
            tag=t,
            delta=delta,
            sd=sd,
            exposure=float(exposure[j - 1]),
            attempts=attempts_by_tag[t],
            solved=solved_by_tag[t],
        )
    return SkillFit(
        anchor=float(anchor),
        level=float(anchor + theta[0] + mean_delta),
        level_sd=level_sd,
        tags=skills,
        n_attempts=sum(1 for a in usable if a.observed),
        iterations=it,
        converged=converged or n == 0,
    )
