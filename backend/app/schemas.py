"""API response/request models."""

from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, Field

_PID = re.compile(r"^(\d+)([A-Za-z][0-9A-Za-z]*)$")


def problem_url(problem_id: str) -> str | None:
    m = _PID.match(problem_id)
    if not m:
        return None
    contest, index = m.groups()
    if int(contest) >= 100000:
        return f"https://codeforces.com/gym/{contest}/problem/{index}"
    return f"https://codeforces.com/problemset/problem/{contest}/{index}"


class ProblemRef(BaseModel):
    id: str
    name: str
    rating: int | None
    tags: list[str]
    url: str | None

    @classmethod
    def make(
        cls, id: str, name: str, rating: int | None, tags: list[str] | tuple[str, ...]
    ) -> ProblemRef:
        return cls(id=id, name=name, rating=rating, tags=list(tags), url=problem_url(id))


class HandleOut(BaseModel):
    handle: str
    rating: int | None
    max_rating: int | None
    rank: str | None
    max_rank: str | None
    avatar: str | None
    sync_state: str
    sync_error: str | None
    last_synced_at: datetime | None


class SyncStatus(HandleOut):
    submissions: int


class TagSkillOut(BaseModel):
    tag: str
    delta: float
    sd: float
    ci_low: float
    ci_high: float
    level: float
    exposure: float
    attempts: int
    solved: int
    label: str


class Evidence(BaseModel):
    attempts: int
    solved: int
    solve_rate: float | None
    avg_wrong_before_ac: float | None
    hardest_solved: ProblemRef | None
    recent_failures: list[ProblemRef]


class WeaknessOut(BaseModel):
    tag: str
    score: float
    kinds: list[str]  # "skill" and/or "coverage"
    summary: str
    delta: float
    ci_low: float
    ci_high: float
    label: str
    importance: float
    pool_share: float
    user_share: float
    evidence: Evidence


class RatingPoint(BaseModel):
    at: datetime
    rating: int
    contest_id: int
    contest_name: str


class BucketStat(BaseModel):
    rating: int
    attempted: int
    solved: int


class WeekStat(BaseModel):
    week_start: date
    solved: int


class UpsolveStat(BaseModel):
    failed_in_contest: int
    upsolved: int
    rate: float | None


class Overview(BaseModel):
    attempts: int
    solved: int
    submissions: int
    level: float
    level_sd: float
    comfort_median: float | None
    comfort_p80: float | None
    upsolve: UpsolveStat
    verdicts: dict[str, int]
    languages: dict[str, int]


class HistoryOut(BaseModel):
    dates: list[date]
    level: list[float]
    tags: dict[str, list[float | None]]


class ModelInfo(BaseModel):
    anchor: float
    iterations: int
    converged: bool
    half_life_attempts: float
    prior_sd: float


class AnalysisOut(BaseModel):
    handle: HandleOut
    overview: Overview
    skills: list[TagSkillOut]
    weaknesses: list[WeaknessOut]
    rating_history: list[RatingPoint]
    by_rating: list[BucketStat]
    weekly: list[WeekStat]
    history: HistoryOut
    model: ModelInfo


class RecommendationOut(BaseModel):
    problem: ProblemRef
    kind: str  # weak | stretch | upsolve
    focus_tag: str | None
    reason: str
    predicted: float


class RecommendationsOut(BaseModel):
    day: date
    items: list[RecommendationOut]


class CompareSide(BaseModel):
    handle: HandleOut
    level: float
    skills: list[TagSkillOut]


class CompareOut(BaseModel):
    a: CompareSide
    b: CompareSide


# --- auth -------------------------------------------------------------------------------------


class VerifyStartIn(BaseModel):
    handle: str = Field(min_length=3, max_length=24)


class VerifyStartOut(BaseModel):
    verification_id: str
    handle: str
    problem: ProblemRef
    submit_url: str | None
    expires_at: datetime


class VerifyCheckIn(BaseModel):
    verification_id: str


class MeOut(BaseModel):
    handle: str
    verified_at: datetime


# --- plans & goals ----------------------------------------------------------------------------


class PlanItemOut(BaseModel):
    id: int
    problem: ProblemRef
    kind: str
    focus_tag: str | None
    reason: str
    predicted: float
    status: str
    solved_at: datetime | None


class PlanOut(BaseModel):
    day: date
    items: list[PlanItemOut]
    streak: int
    solved_today: int


class PlanItemPatch(BaseModel):
    status: str = Field(pattern="^(todo|skipped)$")


class GoalIn(BaseModel):
    target_rating: int | None = Field(default=None, ge=800, le=3500)
    daily_count: int = Field(default=4, ge=1, le=8)
    focus_tags: list[str] = Field(default_factory=list, max_length=3)


class GoalOut(GoalIn):
    pass


class ProgressOut(BaseModel):
    history: HistoryOut
    weekly: list[WeekStat]
    streak: int
    plan_days: int
    plan_solved: int
