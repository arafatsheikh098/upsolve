"""Pull data from Codeforces into Postgres.

* `sync_handle` fetches a user's profile, rating history and submissions. After the first sync it is
  incremental: it pages newest-to-oldest and stops at the first submission it already has. The
  overlap page is upserted, so submissions that were still "TESTING" get their final verdict.
* `refresh_problemset` upserts every problem with its tags, rating, solved count and contest start.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cf.client import (
    CFError,
    CFSubmission,
    CFUnavailable,
    CodeforcesClient,
    HandleNotFound,
)
from app.models import Handle, Problem, RatingChange, Submission

log = logging.getLogger(__name__)

PAGE_SIZE = 500
_CHUNK = 1000


def handle_key(handle: str) -> str:
    return handle.strip().lower()


async def mark_sync_error(session: AsyncSession, key: str, message: str) -> None:
    h = await session.get(Handle, key)
    if h is not None:
        h.sync_state = "error"
        h.sync_error = message
        await session.commit()


async def sync_handle(session: AsyncSession, client: CodeforcesClient, handle: str) -> Handle:
    key = handle_key(handle)
    h = await session.get(Handle, key)
    if h is None:
        h = Handle(key=key, handle=handle, sync_state="syncing")
        session.add(h)
    h.sync_state = "syncing"
    h.sync_error = None
    await session.commit()

    try:
        info = await client.user_info(handle)
        h.handle = info.handle
        h.rating = info.rating
        h.max_rating = info.max_rating
        h.rank = info.rank
        h.max_rank = info.max_rank
        h.avatar = info.avatar

        known = h.last_submission_id
        newest: int | None = None
        start = 1
        while True:
            page = await client.user_status(info.handle, start=start, count=PAGE_SIZE)
            if page:
                await _upsert_submissions(session, key, page)
                # Commit per page so the UI can show live progress on big first syncs.
                await session.commit()
                top = max(s.id for s in page)
                newest = top if newest is None else max(newest, top)
            reached_known = known is not None and any(s.id <= known for s in page)
            if reached_known or len(page) < PAGE_SIZE:
                break
            start += PAGE_SIZE
        if newest is not None:
            h.last_submission_id = max(newest, known or 0)

        changes = await client.user_rating(info.handle)
        await session.execute(delete(RatingChange).where(RatingChange.handle_key == key))
        if changes:
            await session.execute(
                insert(RatingChange).values(
                    [
                        {
                            "handle_key": key,
                            "contest_id": c.contest_id,
                            "contest_name": c.contest_name,
                            "rank": c.rank,
                            "old_rating": c.old_rating,
                            "new_rating": c.new_rating,
                            "at": datetime.fromtimestamp(c.rating_update_time_seconds, tz=UTC),
                        }
                        for c in changes
                    ]
                )
            )

        h.sync_state = "ready"
        h.last_synced_at = datetime.now(UTC)
        await session.commit()
        return h
    except HandleNotFound:
        await session.rollback()
        await mark_sync_error(session, key, "This handle does not exist on Codeforces.")
        raise
    except CFUnavailable:
        await session.rollback()
        await mark_sync_error(session, key, "Codeforces is not responding. Try again in a minute.")
        raise
    except CFError as exc:
        await session.rollback()
        await mark_sync_error(session, key, f"Codeforces error: {exc}")
        raise


async def _upsert_submissions(session: AsyncSession, key: str, page: list[CFSubmission]) -> None:
    rows = [
        {
            "id": s.id,
            "handle_key": key,
            "problem_id": s.problem.id,
            "problem_name": s.problem.name[:255],
            "problem_rating": s.problem.rating,
            "problem_tags": s.problem.tags,
            "verdict": s.verdict,
            "participant_type": s.author.participant_type,
            "language": s.programming_language[:64],
            "created_at": s.created_at,
        }
        for s in page
    ]
    for i in range(0, len(rows), _CHUNK):
        stmt = insert(Submission).values(rows[i : i + _CHUNK])
        stmt = stmt.on_conflict_do_update(
            index_elements=[Submission.id],
            set_={
                "verdict": stmt.excluded.verdict,
                "problem_rating": stmt.excluded.problem_rating,
                "problem_tags": stmt.excluded.problem_tags,
            },
        )
        await session.execute(stmt)


async def refresh_problemset(session: AsyncSession, client: CodeforcesClient) -> int:
    problems, stats = await client.problemset()
    contests = await client.contests()
    starts = {
        c.id: datetime.fromtimestamp(c.start_time_seconds, tz=UTC)
        for c in contests
        if c.start_time_seconds is not None
    }
    solved = {f"{s.contest_id}{s.index}": s.solved_count for s in stats if s.contest_id is not None}

    rows = [
        {
            "id": p.id,
            "contest_id": p.contest_id,
            "index": p.index,
            "name": p.name[:255],
            "rating": p.rating,
            "tags": p.tags,
            "solved_count": solved.get(p.id),
            "contest_start": starts.get(p.contest_id) if p.contest_id is not None else None,
        }
        for p in problems
        if p.contest_id is not None
    ]
    for i in range(0, len(rows), _CHUNK):
        stmt = insert(Problem).values(rows[i : i + _CHUNK])
        stmt = stmt.on_conflict_do_update(
            index_elements=[Problem.id],
            set_={
                "name": stmt.excluded.name,
                "rating": stmt.excluded.rating,
                "tags": stmt.excluded.tags,
                "solved_count": stmt.excluded.solved_count,
                "contest_start": stmt.excluded.contest_start,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
    await session.commit()
    log.info("problemset refreshed: %d problems", len(rows))
    return len(rows)


async def problem_count(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count()).select_from(Problem))).scalar_one())
