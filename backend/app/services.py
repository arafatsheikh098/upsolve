"""Glue between the database and the pure analysis code."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.features import Attempt, SubmissionRow
from app.analysis.report import PoolProblem, RatingRow, build_report
from app.analysis.skill import SkillFit
from app.models import Handle, Problem, RatingChange, Submission
from app.schemas import AnalysisOut, HandleOut, SyncStatus

POOL_TTL_SECONDS = 900


def handle_out(h: Handle) -> HandleOut:
    return HandleOut(
        handle=h.handle,
        rating=h.rating,
        max_rating=h.max_rating,
        rank=h.rank,
        max_rank=h.max_rank,
        avatar=h.avatar,
        sync_state=h.sync_state,
        sync_error=h.sync_error,
        last_synced_at=h.last_synced_at,
    )


async def sync_status(session: AsyncSession, h: Handle) -> SyncStatus:
    count = await session.scalar(
        select(func.count()).select_from(Submission).where(Submission.handle_key == h.key)
    )
    return SyncStatus(**handle_out(h).model_dump(), submissions=int(count or 0))


async def load_submissions(session: AsyncSession, key: str) -> list[SubmissionRow]:
    rows = await session.execute(
        select(
            Submission.problem_id,
            Submission.problem_name,
            Submission.problem_rating,
            Submission.problem_tags,
            Submission.verdict,
            Submission.created_at,
            Submission.participant_type,
            Submission.language,
        ).where(Submission.handle_key == key)
    )
    return [
        SubmissionRow(
            problem_id=r.problem_id,
            name=r.problem_name,
            rating=r.problem_rating,
            tags=tuple(r.problem_tags or ()),
            verdict=r.verdict,
            created_at=r.created_at,
            participant_type=r.participant_type,
            language=r.language,
        )
        for r in rows
    ]


async def load_ratings(session: AsyncSession, key: str) -> list[RatingRow]:
    rows = await session.scalars(select(RatingChange).where(RatingChange.handle_key == key))
    return [
        RatingRow(
            contest_id=r.contest_id, contest_name=r.contest_name, new_rating=r.new_rating, at=r.at
        )
        for r in rows
    ]


class _PoolCache:
    def __init__(self) -> None:
        self.problems: list[PoolProblem] = []
        self.loaded_at = 0.0

    async def get(self, session: AsyncSession) -> list[PoolProblem]:
        if self.problems and time.monotonic() - self.loaded_at < POOL_TTL_SECONDS:
            return self.problems
        rows = await session.scalars(select(Problem))
        problems = [
            PoolProblem(
                id=p.id,
                contest_id=p.contest_id,
                index=p.index,
                name=p.name,
                rating=p.rating,
                tags=tuple(p.tags or ()),
                solved_count=p.solved_count,
                contest_start=p.contest_start,
            )
            for p in rows
        ]
        if problems:  # don't cache an empty problemset; it's probably still being loaded
            self.problems = problems
            self.loaded_at = time.monotonic()
        return problems

    def clear(self) -> None:
        self.problems = []
        self.loaded_at = 0.0


pool_cache = _PoolCache()


@dataclass
class HandleAnalysis:
    report: AnalysisOut
    fit: SkillFit
    attempts: list[Attempt]
    pool: list[PoolProblem]


async def analyze(session: AsyncSession, h: Handle, now: datetime | None = None) -> HandleAnalysis:
    now = now or datetime.now(UTC)
    subs = await load_submissions(session, h.key)
    ratings = await load_ratings(session, h.key)
    pool = await pool_cache.get(session)
    report, fit, attempts = build_report(handle_out(h), subs, ratings, pool, now)
    return HandleAnalysis(report=report, fit=fit, attempts=attempts, pool=pool)
