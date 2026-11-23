from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Problem(Base):
    """One problem from Codeforces' problemset (refreshed nightly)."""

    __tablename__ = "problems"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # e.g. "1520A"
    contest_id: Mapped[int] = mapped_column(Integer, index=True)
    index: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(255))
    rating: Mapped[int | None] = mapped_column(Integer, index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    solved_count: Mapped[int | None] = mapped_column(Integer)
    contest_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Handle(Base):
    """A Codeforces handle we have synced (or tried to). `key` is the lower-cased handle."""

    __tablename__ = "handles"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    handle: Mapped[str] = mapped_column(String(32))
    rating: Mapped[int | None] = mapped_column(Integer)
    max_rating: Mapped[int | None] = mapped_column(Integer)
    rank: Mapped[str | None] = mapped_column(String(64))
    max_rank: Mapped[str | None] = mapped_column(String(64))
    avatar: Mapped[str | None] = mapped_column(String(512))
    sync_state: Mapped[str] = mapped_column(String(16), default="idle")
    sync_error: Mapped[str | None] = mapped_column(Text)
    sync_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_submission_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Submission(Base):
    """A submission, with a snapshot of the problem's rating/tags at sync time."""

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    handle_key: Mapped[str] = mapped_column(
        ForeignKey("handles.key", ondelete="CASCADE"), index=True
    )
    problem_id: Mapped[str] = mapped_column(String(32), index=True)
    problem_name: Mapped[str] = mapped_column(String(255))
    problem_rating: Mapped[int | None] = mapped_column(Integer)
    problem_tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    verdict: Mapped[str | None] = mapped_column(String(48))
    participant_type: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RatingChange(Base):
    __tablename__ = "rating_changes"

    handle_key: Mapped[str] = mapped_column(
        ForeignKey("handles.key", ondelete="CASCADE"), primary_key=True
    )
    contest_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contest_name: Mapped[str] = mapped_column(String(255))
    rank: Mapped[int] = mapped_column(Integer)
    old_rating: Mapped[int] = mapped_column(Integer)
    new_rating: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class User(Base):
    """A verified owner of a Codeforces handle."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    handle_key: Mapped[str] = mapped_column(
        ForeignKey("handles.key", ondelete="CASCADE"), unique=True
    )
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    goal: Mapped[Goal | None] = relationship(back_populates="user", uselist=False, lazy="raise")


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    handle_key: Mapped[str] = mapped_column(String(32), index=True)
    handle: Mapped[str] = mapped_column(String(32))
    problem_id: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)


class Goal(Base):
    __tablename__ = "goals"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    target_rating: Mapped[int | None] = mapped_column(Integer)
    daily_count: Mapped[int] = mapped_column(Integer, default=4)
    focus_tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)

    user: Mapped[User] = relationship(back_populates="goal", lazy="raise")


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list[PlanItem]] = relationship(
        back_populates="plan", order_by="PlanItem.position", lazy="selectin"
    )


class PlanItem(Base):
    __tablename__ = "plan_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    problem_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(255))
    rating: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)
    kind: Mapped[str] = mapped_column(String(16))  # weak | stretch | upsolve
    focus_tag: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    predicted: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="todo")  # todo | solved | skipped
    solved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    plan: Mapped[Plan] = relationship(back_populates="items", lazy="raise")
