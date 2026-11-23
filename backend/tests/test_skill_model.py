"""The model must recover known per-tag skills from simulated data, with honest intervals."""

import math
import random
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.analysis.features import Attempt
from app.analysis.skill import K, fit_skill, outcome

NOW = datetime(2026, 11, 1, tzinfo=UTC)
TRUE_DELTA = {
    "dp": -220.0,
    "graphs": -160.0,
    "math": -40.0,
    "implementation": 150.0,
    "greedy": 110.0,
    "strings": 0.0,
    "sortings": 90.0,
    "number theory": 70.0,
}
ANCHOR = 1400.0
TRUE_LEVEL = 1550.0  # anchor + baseline (selection bias makes attempted problems look easier)


def simulate(n: int, seed: int) -> list[Attempt]:
    rng = random.Random(seed)
    tags = list(TRUE_DELTA)
    out: list[Attempt] = []
    for i in range(n):
        k = rng.choice([1, 1, 2, 2, 3])
        ts = tuple(sorted(rng.sample(tags, k)))
        rating = rng.randrange(800, 2401, 100)
        z = K * (TRUE_LEVEL + sum(TRUE_DELTA[t] for t in ts) / k - rating)
        solved = rng.random() < 1 / (1 + math.exp(-z))
        out.append(
            Attempt(
                problem_id=f"{i}A",
                name=f"P{i}",
                rating=rating,
                tags=ts,
                solved=solved,
                last_at=NOW - timedelta(days=1),
            )
        )
    return out


def centred(d: dict[str, float]) -> dict[str, float]:
    mean = sum(d.values()) / len(d)
    return {t: v - mean for t, v in d.items()}


def test_recovers_tag_offsets_and_level() -> None:
    fit = fit_skill(simulate(4000, seed=1), now=NOW, anchor=ANCHOR, half_life_attempts=1e9)
    assert fit.converged
    est = centred({t: fit.tags[t].delta for t in TRUE_DELTA})
    true = centred(TRUE_DELTA)
    for t in TRUE_DELTA:
        # within 3 standard errors, and the standard errors themselves are tight
        assert abs(est[t] - true[t]) < 3 * fit.tags[t].sd, (t, est[t], true[t], fit.tags[t].sd)
        assert fit.tags[t].sd < 40
    true_mean = sum(TRUE_DELTA.values()) / len(TRUE_DELTA)
    est_mean = sum(fit.tags[t].delta for t in TRUE_DELTA) / len(TRUE_DELTA)
    assert abs((fit.level + est_mean) - (TRUE_LEVEL + true_mean)) < 3 * fit.level_sd + 10
    weakest = min(fit.tags.values(), key=lambda s: s.delta)
    assert weakest.tag == "dp" and weakest.label == "weak"


def test_intervals_have_roughly_nominal_coverage() -> None:
    """Across repeated simulations, ~90% of the 90% intervals should contain the truth."""
    hits = total = 0
    for seed in range(40):
        fit = fit_skill(simulate(800, seed=seed), now=NOW, anchor=ANCHOR, half_life_attempts=1e9)
        # Estimates are relative to the exposure-weighted average tag; express truth the same way.
        w = {t: fit.tags[t].exposure for t in TRUE_DELTA}
        tw = sum(TRUE_DELTA[t] * w[t] for t in TRUE_DELTA) / sum(w.values())
        for t in TRUE_DELTA:
            s = fit.tags[t]
            hits += int(s.ci_low <= TRUE_DELTA[t] - tw <= s.ci_high)
            total += 1
    assert 0.80 <= hits / total <= 0.98, hits / total


def test_sparse_tags_are_shrunk_and_flagged() -> None:
    attempts = simulate(300, seed=3)
    attempts.append(
        Attempt("9999A", "Rare", 1500, ("fft",), solved=False, last_at=NOW - timedelta(days=1))
    )
    fit = fit_skill(attempts, now=NOW, anchor=ANCHOR, tag_universe=["flows"])
    assert fit.tags["fft"].label == "insufficient"
    assert abs(fit.tags["fft"].delta) < 100  # one failure shouldn't scream "terrible at FFT"
    assert fit.tags["flows"].attempts == 0
    assert fit.tags["flows"].delta == 0.0
    assert fit.tags["flows"].sd == pytest.approx(150.0, rel=0.05)


def test_empty_history_is_safe() -> None:
    fit = fit_skill([], now=NOW, anchor=None, tag_universe=["dp"])
    assert fit.n_attempts == 0
    assert fit.level == 800.0
    assert 0.0 < fit.predict(800, ["dp"]) < 1.0


def test_recent_attempts_weigh_more() -> None:
    """Old failures fade as newer attempts pile up: failing dp long ago but solving it now
    shouldn't make dp look weak."""
    old = [
        Attempt(f"{i}A", "", 1400, ("dp",), solved=False, last_at=NOW - timedelta(days=730))
        for i in range(30)
    ] + [
        Attempt(f"{i}D", "", 1400, ("math",), solved=i % 2 == 0, last_at=NOW - timedelta(days=400))
        for i in range(300)
    ]
    new = [
        Attempt(f"{i}B", "", 1400, ("dp",), solved=True, last_at=NOW - timedelta(days=5))
        for i in range(30)
    ]
    other = [
        Attempt(f"{i}C", "", 1400, ("greedy",), solved=i % 2 == 0, last_at=NOW - timedelta(days=5))
        for i in range(30)
    ]
    fit = fit_skill(old + new + other, now=NOW, anchor=1400)
    assert fit.tags["dp"].delta > fit.tags["greedy"].delta
    no_decay = fit_skill(old + new + other, now=NOW, anchor=1400, half_life_attempts=1e9)
    assert fit.tags["dp"].delta > no_decay.tags["dp"].delta


def test_activity_decay_ignores_idle_time() -> None:
    """Taking a year off doesn't change the estimate; only newer attempts push old ones out."""
    attempts = simulate(400, seed=7)
    a = fit_skill(attempts, now=NOW, anchor=ANCHOR)
    b = fit_skill(attempts, now=NOW + timedelta(days=365), anchor=ANCHOR)
    assert a.tags["dp"].delta == pytest.approx(b.tags["dp"].delta)


def test_soft_label() -> None:
    a = Attempt("1A", "", 800, (), solved=True, wrong_before_ac=3)
    assert outcome(a) == pytest.approx(0.7)
    a.wrong_before_ac = 20
    assert outcome(a) == 0.5
    assert outcome(Attempt("1B", "", 800, ())) == 0.0


def test_predict_is_monotone_in_rating() -> None:
    fit = fit_skill(simulate(500, seed=5), now=NOW, anchor=ANCHOR)
    ps = [fit.predict(r, ["dp"]) for r in range(800, 3000, 100)]
    assert all(np.diff(ps) < 0)
