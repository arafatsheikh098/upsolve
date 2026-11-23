"""Daily practice plans, goals and progress for verified users."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.recommend import ShownHistory, plan_seed, recommend
from app.db import get_session
from app.deps import current_user
from app.models import Goal, Handle, Plan, PlanItem, Submission, User
from app.schemas import (
    GoalIn,
    GoalOut,
    PlanItemOut,
    PlanItemPatch,
    PlanOut,
    ProblemRef,
    ProgressOut,
)
from app.services import analyze

router = APIRouter(prefix="/me", tags=["me"])


def today() -> date:
    return datetime.now(UTC).date()


async def _goal(session: AsyncSession, user: User) -> Goal:
    goal = await session.get(Goal, user.id)
    if goal is None:
        goal = Goal(user_id=user.id, daily_count=4, focus_tags=[])
    return goal


async def _shown_history(session: AsyncSession, user: User) -> dict[str, ShownHistory]:
    rows = await session.execute(
        select(PlanItem.problem_id, func.count(), func.max(Plan.created_at))
        .join(Plan, Plan.id == PlanItem.plan_id)
        .where(Plan.user_id == user.id, PlanItem.kind == "upsolve")
        .group_by(PlanItem.problem_id)
    )
    return {pid: ShownHistory(times=int(n), last=last) for pid, n, last in rows}


async def _refresh_statuses(session: AsyncSession, user: User, plan: Plan) -> None:
    """Mark plan items solved if an accepted submission appeared after the plan was created."""
    open_items = [i for i in plan.items if i.status != "solved"]
    if not open_items:
        return
    rows = await session.execute(
        select(Submission.problem_id, func.min(Submission.created_at))
        .where(
            Submission.handle_key == user.handle_key,
            Submission.problem_id.in_([i.problem_id for i in open_items]),
            Submission.verdict == "OK",
            Submission.created_at >= plan.created_at - timedelta(hours=1),
        )
        .group_by(Submission.problem_id)
    )
    solved = {pid: first for pid, first in rows}
    changed = False
    for item in open_items:
        if item.problem_id in solved:
            item.status = "solved"
            item.solved_at = solved[item.problem_id]
            changed = True
    if changed:
        await session.commit()


async def _streak(session: AsyncSession, user: User) -> int:
    """Consecutive days (ending today or yesterday) with at least one plan problem solved."""
    rows = await session.scalars(
        select(PlanItem.solved_at)
        .join(Plan, Plan.id == PlanItem.plan_id)
        .where(Plan.user_id == user.id, PlanItem.solved_at.is_not(None))
    )
    days = {d.date() for d in rows if d is not None}
    cursor = today()
    if cursor not in days:
        cursor -= timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _item_out(i: PlanItem) -> PlanItemOut:
    return PlanItemOut(
        id=i.id,
        problem=ProblemRef.make(i.problem_id, i.name, i.rating, i.tags),
        kind=i.kind,
        focus_tag=i.focus_tag,
        reason=i.reason,
        predicted=i.predicted,
        status=i.status,
        solved_at=i.solved_at,
    )


async def _plan_out(session: AsyncSession, user: User, plan: Plan) -> PlanOut:
    return PlanOut(
        day=plan.day,
        items=[_item_out(i) for i in plan.items],
        streak=await _streak(session, user),
        solved_today=sum(1 for i in plan.items if i.status == "solved"),
    )


async def _load_plan(session: AsyncSession, user: User, day: date) -> Plan | None:
    return await session.scalar(select(Plan).where(Plan.user_id == user.id, Plan.day == day))


@router.get("/plan/today", response_model=PlanOut)
async def plan_today(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> PlanOut:
    day = today()
    plan = await _load_plan(session, user, day)
    if plan is None:
        plan = await _create_plan(session, user, day)
    await _refresh_statuses(session, user, plan)
    return await _plan_out(session, user, plan)


async def _create_plan(session: AsyncSession, user: User, day: date) -> Plan:
    h = await session.get(Handle, user.handle_key)
    if h is None or h.last_synced_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Your handle is still syncing.")
    goal = await _goal(session, user)
    result = await analyze(session, h)
    now = datetime.now(UTC)
    recs = recommend(
        result.fit,
        result.report.weaknesses,
        result.pool,
        result.attempts,
        seed=plan_seed(h.key, day),
        now=now,
        n=goal.daily_count,
        focus_tags=goal.focus_tags,
        shown=await _shown_history(session, user),
    )
    # Two tabs can ask for today's plan at the same moment: insert-if-absent, then reload.
    plan_id = await session.scalar(
        insert(Plan)
        .values(user_id=user.id, day=day)
        .on_conflict_do_nothing(index_elements=["user_id", "day"])
        .returning(Plan.id)
    )
    if plan_id is not None:
        session.add_all(
            PlanItem(
                plan_id=plan_id,
                position=pos,
                problem_id=r.problem_id,
                name=r.name,
                rating=r.rating,
                tags=list(r.tags),
                kind=r.kind,
                focus_tag=r.focus_tag,
                reason=r.reason,
                predicted=r.predicted,
            )
            for pos, r in enumerate(recs)
        )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
    plan = await _load_plan(session, user, day)
    assert plan is not None
    await session.refresh(plan, ["items"])
    return plan


@router.patch("/plan/items/{item_id}", response_model=PlanItemOut)
async def update_item(
    item_id: int,
    body: PlanItemPatch,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> PlanItemOut:
    item = await session.scalar(
        select(PlanItem)
        .join(Plan, Plan.id == PlanItem.plan_id)
        .where(PlanItem.id == item_id, Plan.user_id == user.id)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan item not found.")
    if item.status == "solved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Solved problems can't be changed.")
    item.status = body.status
    await session.commit()
    return _item_out(item)


@router.get("/goals", response_model=GoalOut)
async def get_goals(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> GoalOut:
    g = await _goal(session, user)
    return GoalOut(
        target_rating=g.target_rating, daily_count=g.daily_count, focus_tags=g.focus_tags
    )


@router.put("/goals", response_model=GoalOut)
async def put_goals(
    body: GoalIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> GoalOut:
    g = await session.get(Goal, user.id)
    if g is None:
        g = Goal(user_id=user.id)
        session.add(g)
    g.target_rating = body.target_rating
    g.daily_count = body.daily_count
    g.focus_tags = [t.strip().lower() for t in body.focus_tags if t.strip()]
    await session.commit()
    return GoalOut(
        target_rating=g.target_rating, daily_count=g.daily_count, focus_tags=g.focus_tags
    )


@router.get("/progress", response_model=ProgressOut)
async def progress(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> ProgressOut:
    h = await session.get(Handle, user.handle_key)
    if h is None or h.last_synced_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Your handle is still syncing.")
    result = await analyze(session, h)
    plan_days = await session.scalar(
        select(func.count()).select_from(Plan).where(Plan.user_id == user.id)
    )
    plan_solved = await session.scalar(
        select(func.count())
        .select_from(PlanItem)
        .join(Plan, Plan.id == PlanItem.plan_id)
        .where(Plan.user_id == user.id, PlanItem.status == "solved")
    )
    return ProgressOut(
        history=result.report.history,
        weekly=result.report.weekly,
        streak=await _streak(session, user),
        plan_days=int(plan_days or 0),
        plan_solved=int(plan_solved or 0),
    )
