"""Assemble the full analysis for one handle: model fit, weaknesses, evidence, stats, history."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import numpy as np

from app.analysis.features import (
    Attempt,
    ContestProblem,
    SubmissionRow,
    build_attempts,
    clean_tags,
    contest_misses,
    contest_participation,
)
from app.analysis.skill import DEFAULT_HALF_LIFE_ATTEMPTS, DEFAULT_PRIOR_SD, SkillFit, fit_skill
from app.schemas import (
    AnalysisOut,
    BucketStat,
    Evidence,
    HandleOut,
    HistoryOut,
    ModelInfo,
    Overview,
    ProblemRef,
    RatingPoint,
    TagSkillOut,
    UpsolveStat,
    WeaknessOut,
    WeekStat,
)

COVERAGE_WEIGHT = 0.75
POOL_YEARS = 3
HISTORY_MONTHS = 12


@dataclass(frozen=True)
class PoolProblem:
    id: str
    contest_id: int
    index: str
    name: str
    rating: int | None
    tags: tuple[str, ...]
    solved_count: int | None
    contest_start: datetime | None


@dataclass(frozen=True)
class RatingRow:
    contest_id: int
    contest_name: str
    new_rating: int
    at: datetime


@dataclass(frozen=True)
class TagMarket:
    """How common a tag is among problems around the user's level."""

    pool_share: float
    importance: float  # pool_share normalised so the most common tag is 1.0


def tag_market(
    pool: Sequence[PoolProblem], low: float, high: float, now: datetime
) -> dict[str, TagMarket]:
    since = now - timedelta(days=365 * POOL_YEARS)
    weight: dict[str, float] = defaultdict(float)
    total = 0
    for p in pool:
        if p.rating is None or not (low <= p.rating <= high):
            continue
        if p.contest_start is not None and p.contest_start < since:
            continue
        tags = clean_tags(p.tags)
        if not tags:
            continue
        total += 1
        for t in tags:
            weight[t] += 1 / len(tags)
    if not total:
        return {}
    top = max(weight.values())
    return {t: TagMarket(pool_share=v / total, importance=v / top) for t, v in weight.items()}


def anchor_at(ratings: Sequence[RatingRow], when: datetime) -> float | None:
    """The user's Codeforces rating at a moment in the past (None before their first contest)."""
    past = [r for r in ratings if r.at <= when]
    return float(max(past, key=lambda r: r.at).new_rating) if past else None


def _ref(a: Attempt) -> ProblemRef:
    return ProblemRef.make(a.problem_id, a.name, a.rating, a.tags)


def evidence_for(tag: str, attempts: Sequence[Attempt]) -> Evidence:
    mine = [a for a in attempts if tag in a.tags]
    solved = [a for a in mine if a.solved]
    rated_solved = [a for a in solved if a.rating is not None]
    hardest = max(
        rated_solved,
        key=lambda a: (a.rating or 0, a.solved_at or datetime.min.replace(tzinfo=UTC)),
        default=None,
    )
    failures = sorted(
        (a for a in mine if not a.solved),
        key=lambda a: a.last_at or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )[:3]
    return Evidence(
        attempts=len(mine),
        solved=len(solved),
        solve_rate=len(solved) / len(mine) if mine else None,
        avg_wrong_before_ac=(sum(a.wrong_before_ac for a in solved) / len(solved))
        if solved
        else None,
        hardest_solved=_ref(hardest) if hardest else None,
        recent_failures=[_ref(a) for a in failures],
    )


def _title(tag: str) -> str:
    return tag[:1].upper() + tag[1:]


def find_weaknesses(
    fit: SkillFit, attempts: Sequence[Attempt], market: dict[str, TagMarket], limit: int = 6
) -> list[WeaknessOut]:
    total_exposure = sum(s.exposure for s in fit.tags.values()) or 1.0
    out: list[WeaknessOut] = []
    for tag, mk in market.items():
        s = fit.tags.get(tag)
        if s is None:
            continue
        user_share = s.exposure / total_exposure
        coverage = user_share / mk.pool_share if mk.pool_share > 0 else 1.0
        gap = max(0.0, 1.0 - coverage)
        deficit = max(0.0, -s.delta) / 100
        score = mk.importance * (deficit + COVERAGE_WEIGHT * gap)
        kinds = []
        if s.label == "weak" or (deficit > 0.5 and s.label != "insufficient"):
            kinds.append("skill")
        if gap >= 0.5 and mk.importance >= 0.2:
            kinds.append("coverage")
        if not kinds or score < 0.15:
            continue
        parts = []
        if "skill" in kinds:
            confident = s.label == "weak"
            parts.append(
                f"{'You' if confident else 'You probably'} solve {_title(tag)} problems at about "
                f"{s.delta:+.0f} rating compared with your average tag (90% range "
                f"{s.ci_low:+.0f} to {s.ci_high:+.0f}"
                f"{'' if confident else '; more practice will make this clearer'})."
            )
        if "coverage" in kinds:
            parts.append(
                f"It appears in {mk.pool_share:.0%} of recent problems at your level, but only "
                f"{user_share:.0%} of your practice."
            )
        out.append(
            WeaknessOut(
                tag=tag,
                score=round(score, 3),
                kinds=kinds,
                summary=" ".join(parts),
                delta=s.delta,
                ci_low=s.ci_low,
                ci_high=s.ci_high,
                label=s.label,
                importance=mk.importance,
                pool_share=mk.pool_share,
                user_share=user_share,
                evidence=evidence_for(tag, attempts),
            )
        )
    out.sort(key=lambda w: w.score, reverse=True)
    return out[:limit]


def _month_ends(now: datetime, months: int) -> list[datetime]:
    points = [now]
    y, m = now.year, now.month
    for _ in range(months):
        # first instant of the current month = end of the previous one
        points.append(datetime(y, m, 1, tzinfo=UTC))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return sorted(points)


def problems_by_contest(pool: Sequence[PoolProblem]) -> dict[int, list[ContestProblem]]:
    out: dict[int, list[ContestProblem]] = defaultdict(list)
    for p in pool:
        if p.rating is not None:
            out[p.contest_id].append(ContestProblem(p.id, p.name, p.rating, p.tags))
    return out


def model_inputs(
    subs: Sequence[SubmissionRow],
    ratings: Sequence[RatingRow],
    by_contest: dict[int, list[ContestProblem]],
    until: datetime | None = None,
) -> tuple[list[Attempt], list[Attempt]]:
    """(real attempts, real attempts + contest misses) as of `until`."""
    attempts = build_attempts(subs, until=until)
    participated = contest_participation(
        (s for s in subs if until is None or s.created_at <= until),
        {r.contest_id: r.at for r in ratings},
    )
    misses = contest_misses(attempts, participated, by_contest, until=until)
    return attempts, attempts + misses


def skill_history(
    subs: Sequence[SubmissionRow],
    ratings: Sequence[RatingRow],
    current_rating: int | None,
    now: datetime,
    by_contest: dict[int, list[ContestProblem]] | None = None,
    months: int = HISTORY_MONTHS,
) -> HistoryOut:
    """Refit the model as it would have looked at the end of each past month.

    Because the model is cheap and deterministic, progress charts work for any handle on day one,
    with no need to have stored daily snapshots."""
    dates: list[date] = []
    levels: list[float] = []
    series: dict[str, list[float | None]] = defaultdict(list)
    first = min((s.created_at for s in subs), default=now)
    points = [p for p in _month_ends(now, months) if p > first]
    fits: list[SkillFit] = []
    for p in points:
        _, model_att = model_inputs(subs, ratings, by_contest or {}, until=p)
        anchor = float(current_rating) if p == now and current_rating else anchor_at(ratings, p)
        fits.append(fit_skill(model_att, now=p, anchor=anchor))
    all_tags = sorted({t for f in fits for t, s in f.tags.items() if s.attempts >= 3})
    for p, f in zip(points, fits, strict=True):
        dates.append(p.date())
        levels.append(round(f.level, 1))
        for t in all_tags:
            s = f.tags.get(t)
            series[t].append(round(f.level + s.delta, 1) if s and s.attempts >= 3 else None)
    return HistoryOut(dates=dates, level=levels, tags=dict(series))


def weekly_solved(attempts: Sequence[Attempt], now: datetime, weeks: int = 26) -> list[WeekStat]:
    start = (now - timedelta(days=now.weekday())).date() - timedelta(weeks=weeks - 1)
    counts = Counter(
        (a.solved_at.date() - timedelta(days=a.solved_at.weekday()))
        for a in attempts
        if a.solved_at is not None and a.solved_at.date() >= start
    )
    return [
        WeekStat(
            week_start=start + timedelta(weeks=i), solved=counts.get(start + timedelta(weeks=i), 0)
        )
        for i in range(weeks)
    ]


def build_report(
    handle: HandleOut,
    subs: Sequence[SubmissionRow],
    ratings: Sequence[RatingRow],
    pool: Sequence[PoolProblem],
    now: datetime,
) -> tuple[AnalysisOut, SkillFit, list[Attempt]]:
    by_contest = problems_by_contest(pool)
    attempts, model_attempts = model_inputs(subs, ratings, by_contest)
    fit = fit_skill(model_attempts, now=now, anchor=float(handle.rating) if handle.rating else None)
    # "Problems at your level": from a little below your level to a few hundred points above it.
    low = round(fit.level / 100) * 100 - 100
    market = tag_market(pool, low, low + 500, now)

    skills = sorted(
        (
            TagSkillOut(
                tag=s.tag,
                delta=s.delta,
                sd=s.sd,
                ci_low=s.ci_low,
                ci_high=s.ci_high,
                level=fit.level + s.delta,
                exposure=s.exposure,
                attempts=s.attempts,
                solved=s.solved,
                label=s.label,
            )
            for s in fit.tags.values()
        ),
        key=lambda s: s.delta,
    )

    recent_cut = now - timedelta(days=180)
    recent_solved = [
        a.rating
        for a in attempts
        if a.solved and a.rating and a.solved_at and a.solved_at >= recent_cut
    ]
    failed_in_contest = [a for a in attempts if a.attempted_in_contest and not a.solved_in_contest]
    upsolved = sum(1 for a in failed_in_contest if a.solved)

    buckets: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for a in attempts:
        if a.rating is not None:
            buckets[a.rating][0] += 1
            buckets[a.rating][1] += int(a.solved)

    languages = Counter(s.language for s in subs if s.language)
    overview = Overview(
        attempts=len(attempts),
        solved=sum(1 for a in attempts if a.solved),
        submissions=len(subs),
        level=fit.level,
        level_sd=fit.level_sd,
        comfort_median=float(np.median(recent_solved)) if recent_solved else None,
        comfort_p80=float(np.percentile(recent_solved, 80)) if recent_solved else None,
        upsolve=UpsolveStat(
            failed_in_contest=len(failed_in_contest),
            upsolved=upsolved,
            rate=upsolved / len(failed_in_contest) if failed_in_contest else None,
        ),
        verdicts=dict(Counter(s.verdict or "UNKNOWN" for s in subs).most_common()),
        languages=dict(languages.most_common(6)),
    )

    report = AnalysisOut(
        handle=handle,
        overview=overview,
        skills=skills,
        weaknesses=find_weaknesses(fit, attempts, market),
        rating_history=[
            RatingPoint(
                at=r.at, rating=r.new_rating, contest_id=r.contest_id, contest_name=r.contest_name
            )
            for r in sorted(ratings, key=lambda r: r.at)
        ],
        by_rating=[
            BucketStat(rating=k, attempted=v[0], solved=v[1]) for k, v in sorted(buckets.items())
        ],
        weekly=weekly_solved(attempts, now),
        history=skill_history(subs, ratings, handle.rating, now, by_contest),
        model=ModelInfo(
            anchor=fit.anchor,
            iterations=fit.iterations,
            converged=fit.converged,
            half_life_attempts=DEFAULT_HALF_LIFE_ATTEMPTS,
            prior_sd=DEFAULT_PRIOR_SD,
        ),
    )
    return report, fit, attempts
