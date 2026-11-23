"""Pick practice problems: weakest tags at the right difficulty, one stretch, one upsolve.

Difficulty is chosen with the skill model: a problem is "right" when the predicted chance of solving
it is around 55% (accepted range 35-75%). That is hard enough to learn from but not hopeless
("desirable difficulty"). The stretch problem targets about 30% (range 15-45%).

Picks are random among the best few candidates, seeded by (handle, day), so the same day always
gives the same plan and different days give variety.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.analysis.features import Attempt, clean_tags
from app.analysis.report import PoolProblem, _title
from app.analysis.skill import SkillFit
from app.schemas import WeaknessOut

TARGET_P = 0.55
WEAK_P_RANGE = (0.35, 0.75)
STRETCH_P = 0.3
STRETCH_P_RANGE = (0.15, 0.45)
MIN_SOLVED_COUNT = 100
MAX_PROBLEM_AGE_YEARS = 6
RECENT_YEARS = 3
SPACING_DAYS = (1, 3, 7, 21)
TOP_K = 8


@dataclass(frozen=True)
class Recommendation:
    problem_id: str
    name: str
    rating: int | None
    tags: tuple[str, ...]
    kind: str  # weak | stretch | upsolve
    focus_tag: str | None
    reason: str
    predicted: float


@dataclass(frozen=True)
class ShownHistory:
    times: int
    last: datetime


def _is_due(a: Attempt, shown: ShownHistory | None, now: datetime) -> tuple[bool, float]:
    """Spaced repetition: resurface an unsolved problem 1, 3, 7, then every 21 days."""
    base = shown.last if shown else a.last_at
    if base is None:
        return True, 0.0
    step = SPACING_DAYS[min(shown.times if shown else 0, len(SPACING_DAYS) - 1)]
    overdue = (now - (base + timedelta(days=step))).total_seconds() / 86400
    return overdue >= 0, overdue


def _eligible(pool: Sequence[PoolProblem], exclude: set[str], now: datetime) -> list[PoolProblem]:
    oldest = now - timedelta(days=365 * MAX_PROBLEM_AGE_YEARS)
    out = []
    for p in pool:
        if p.id in exclude or p.rating is None or (p.solved_count or 0) < MIN_SOLVED_COUNT:
            continue
        if "*special" in p.tags or not clean_tags(p.tags):
            continue
        if p.contest_start is not None and p.contest_start < oldest:
            continue
        out.append(p)
    return out


def _recency(p: PoolProblem, now: datetime) -> float:
    if p.contest_start is None:
        return 0.0
    return 1.0 if p.contest_start >= now - timedelta(days=365 * RECENT_YEARS) else 0.0


def _pick(rng: random.Random, scored: list[tuple[float, PoolProblem]]) -> PoolProblem | None:
    if not scored:
        return None
    scored.sort(key=lambda sp: (-sp[0], sp[1].id))
    return rng.choice(scored[:TOP_K])[1]


def focus_order(
    fit: SkillFit, weaknesses: Sequence[WeaknessOut], focus_tags: Sequence[str] = ()
) -> list[str]:
    order: list[str] = [t for t in focus_tags if t]
    order += [w.tag for w in weaknesses if w.tag not in order]
    if len(order) < 3:  # not enough flagged weaknesses: fall back to the lowest-rated tags
        by_delta = sorted((s for s in fit.tags.values() if s.attempts >= 3), key=lambda s: s.delta)
        order += [s.tag for s in by_delta if s.tag not in order]
    return order


def recommend(
    fit: SkillFit,
    weaknesses: Sequence[WeaknessOut],
    pool: Sequence[PoolProblem],
    attempts: Sequence[Attempt],
    *,
    seed: str,
    now: datetime,
    n: int = 4,
    focus_tags: Sequence[str] = (),
    shown: Mapping[str, ShownHistory] | None = None,
) -> list[Recommendation]:
    rng = random.Random(seed)
    shown = shown or {}
    attempted = {a.problem_id for a in attempts}
    candidates = _eligible(pool, attempted, now)
    chosen: set[str] = set()
    weak_by_tag = {w.tag: w for w in weaknesses}
    order = focus_order(fit, weaknesses, focus_tags) or ["implementation"]

    upsolve_pick = _pick_upsolve(attempts, fit, shown, now) if n >= 3 else None
    stretch_slots = 1 if n >= 2 else 0
    weak_slots = n - stretch_slots - (1 if upsolve_pick else 0)

    recs: list[Recommendation] = []
    cursor = 0
    for _ in range(weak_slots):
        # Walk the focus order; skip a tag if no suitable problem is left for it.
        for _ in range(len(order)):
            tag = order[cursor % len(order)]
            cursor += 1
            pick = _pick(rng, _score_for_tag(tag, candidates, chosen, fit, now))
            if pick is not None:
                chosen.add(pick.id)
                reason = _weak_reason(tag, pick, fit, weak_by_tag, focus_tags)
                recs.append(_make(pick, fit, "weak", tag, reason))
                break

    if stretch_slots:
        stretch_tags = set(order[:5])
        scored = []
        for p in candidates:
            assert p.rating is not None
            if p.id in chosen or p.rating < fit.level + 100:
                continue
            tags = clean_tags(p.tags)
            if not stretch_tags & set(tags):
                continue
            pr = fit.predict(p.rating, tags)
            if not STRETCH_P_RANGE[0] <= pr <= STRETCH_P_RANGE[1]:
                continue
            scored.append((1 - abs(pr - STRETCH_P) / 0.2 + 0.25 * _recency(p, now), p))
        pick = _pick(rng, scored)
        if pick is not None:
            chosen.add(pick.id)
            assert pick.rating is not None
            pr = fit.predict(pick.rating, clean_tags(pick.tags))
            recs.append(
                _make(
                    pick,
                    fit,
                    "stretch",
                    None,
                    f"Stretch problem: about {pr:.0%} predicted chance. Problems just beyond your "
                    "comfort zone are where rating gains come from, so give it a real attempt "
                    "before reading the editorial.",
                )
            )

    if upsolve_pick is not None:
        recs.append(upsolve_pick)
    return recs


def _score_for_tag(
    tag: str, candidates: Sequence[PoolProblem], chosen: set[str], fit: SkillFit, now: datetime
) -> list[tuple[float, PoolProblem]]:
    tag_level = fit.tag_level(tag)
    scored = []
    for p in candidates:
        if p.id in chosen or tag not in p.tags:
            continue
        assert p.rating is not None
        if not (tag_level - 300 <= p.rating <= tag_level + 300):
            continue
        tags = clean_tags(p.tags)
        pr = fit.predict(p.rating, tags)
        if not WEAK_P_RANGE[0] <= pr <= WEAK_P_RANGE[1]:
            continue
        # Closest to the target difficulty wins; prefer problems where the tag is central
        # (fewer tags) and problems from recent rounds.
        score = 1 - abs(pr - TARGET_P) / 0.25 + 0.35 / len(tags) + 0.25 * _recency(p, now)
        scored.append((score, p))
    return scored


def _make(p: PoolProblem, fit: SkillFit, kind: str, tag: str | None, reason: str) -> Recommendation:
    assert p.rating is not None
    return Recommendation(
        problem_id=p.id,
        name=p.name,
        rating=p.rating,
        tags=clean_tags(p.tags),
        kind=kind,
        focus_tag=tag,
        reason=reason,
        predicted=round(fit.predict(p.rating, clean_tags(p.tags)), 3),
    )


def _weak_reason(
    tag: str,
    p: PoolProblem,
    fit: SkillFit,
    weak_by_tag: Mapping[str, WeaknessOut],
    focus_tags: Sequence[str],
) -> str:
    assert p.rating is not None
    pr = fit.predict(p.rating, clean_tags(p.tags))
    w = weak_by_tag.get(tag)
    if tag in focus_tags:
        lead = f"{_title(tag)} is one of your chosen focus tags."
    elif w and "skill" in w.kinds:
        lead = (
            f"{_title(tag)} is a weak spot: about {w.delta:+.0f} rating compared with your "
            "average tag."
        )
    elif w and "coverage" in w.kinds:
        lead = (
            f"You rarely practise {_title(tag)}, yet it appears in {w.pool_share:.0%} of "
            "problems at your level."
        )
    else:
        delta = fit.tags[tag].delta if tag in fit.tags else 0.0
        lead = f"{_title(tag)} is one of your lower-rated tags ({delta:+.0f})."
    return (
        f"{lead} At {p.rating} you have about a {pr:.0%} predicted chance: hard enough to "
        "learn from."
    )


def _pick_upsolve(
    attempts: Sequence[Attempt], fit: SkillFit, shown: Mapping[str, ShownHistory], now: datetime
) -> Recommendation | None:
    best: tuple[float, Attempt] | None = None
    for a in attempts:
        if a.solved or a.rating is None:
            continue
        due, overdue = _is_due(a, shown.get(a.problem_id), now)
        if not due:
            continue
        # Prefer problems near the user's level, then the most overdue.
        closeness = -abs(a.rating - fit.level) / 100
        key = closeness + min(overdue, 60) / 60
        if best is None or key > best[0] or (key == best[0] and a.problem_id < best[1].problem_id):
            best = (key, a)
    if best is None:
        return None
    a = best[1]
    assert a.rating is not None and a.last_at is not None
    days = max(1, (now - a.last_at).days)
    h = shown.get(a.problem_id)
    wrong = f"{a.wrong_total} wrong attempt{'s' if a.wrong_total != 1 else ''}"
    lead = f"Review #{h.times + 1}. " if h else ""
    reason = (
        f"{lead}You tried this {days} day{'s' if days != 1 else ''} ago ({wrong}) and haven't "
        "solved it yet. Upsolving problems you got stuck on is the fastest way to close gaps."
    )
    return Recommendation(
        problem_id=a.problem_id,
        name=a.name,
        rating=a.rating,
        tags=a.tags,
        kind="upsolve",
        focus_tag=None,
        reason=reason,
        predicted=round(fit.predict(a.rating, a.tags), 3),
    )


def plan_seed(handle_key: str, day: date) -> str:
    return f"{handle_key}:{day.isoformat()}"
