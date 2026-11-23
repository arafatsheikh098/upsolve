"""Turn raw submissions into one `Attempt` per problem: the unit the skill model learns from."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

# Verdicts that say nothing about whether the solution idea was right.
NEUTRAL_VERDICTS = frozenset(
    {None, "COMPILATION_ERROR", "TESTING", "SKIPPED", "REJECTED", "SECURITY_VIOLATED"}
)
CONTEST_TYPES = frozenset({"CONTESTANT", "OUT_OF_COMPETITION"})
# Tags that describe the contest format rather than an algorithmic skill.
IGNORED_TAGS = frozenset({"*special"})


@dataclass(frozen=True)
class SubmissionRow:
    problem_id: str
    name: str
    rating: int | None
    tags: tuple[str, ...]
    verdict: str | None
    created_at: datetime
    participant_type: str = "PRACTICE"
    language: str = ""


@dataclass
class Attempt:
    problem_id: str
    name: str
    rating: int | None
    tags: tuple[str, ...]
    solved: bool = False
    wrong_before_ac: int = 0
    wrong_total: int = 0
    attempted_in_contest: bool = False
    solved_in_contest: bool = False
    first_at: datetime | None = None
    last_at: datetime | None = None
    solved_at: datetime | None = None
    languages: set[str] = field(default_factory=set)
    # Contest problems the user saw but never submitted to are added as unobserved failures with a
    # lower weight (see `contest_misses`).
    observed: bool = True
    weight: float = 1.0

    @property
    def upsolved(self) -> bool:
        """Failed during the contest, solved afterwards."""
        return self.attempted_in_contest and self.solved and not self.solved_in_contest


def clean_tags(tags: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({t for t in tags if t not in IGNORED_TAGS}))


def build_attempts(subs: Iterable[SubmissionRow], until: datetime | None = None) -> list[Attempt]:
    """Group submissions by problem. If `until` is given, submissions after it are ignored."""
    by_problem: dict[str, Attempt] = {}
    for s in sorted(subs, key=lambda s: s.created_at):
        if until is not None and s.created_at > until:
            continue
        if s.verdict in NEUTRAL_VERDICTS:
            continue
        a = by_problem.get(s.problem_id)
        if a is None:
            a = Attempt(
                problem_id=s.problem_id,
                name=s.name,
                rating=s.rating,
                tags=clean_tags(s.tags),
                first_at=s.created_at,
            )
            by_problem[s.problem_id] = a
        # Ratings/tags can be assigned after the contest; prefer the latest non-empty values.
        if s.rating is not None:
            a.rating = s.rating
        if s.tags:
            a.tags = clean_tags(s.tags)
        a.last_at = s.created_at
        if s.language:
            a.languages.add(s.language)
        in_contest = s.participant_type in CONTEST_TYPES
        a.attempted_in_contest |= in_contest

        if s.verdict == "OK":
            if not a.solved:
                a.solved = True
                a.solved_at = s.created_at
                a.solved_in_contest = in_contest
        else:
            a.wrong_total += 1
            if not a.solved:
                a.wrong_before_ac += 1
    return list(by_problem.values())


MISS_WEIGHT = 0.5


@dataclass(frozen=True)
class ContestProblem:
    problem_id: str
    name: str
    rating: int
    tags: tuple[str, ...]


def contest_participation(
    subs: Iterable[SubmissionRow], rated: Mapping[int, datetime]
) -> dict[int, datetime]:
    """Contests the user took part in live: rated ones plus any with live submissions."""
    out = dict(rated)
    for s in subs:
        if s.participant_type in CONTEST_TYPES:
            cid = contest_of(s.problem_id)
            if cid is not None and (cid not in out or s.created_at < out[cid]):
                out[cid] = s.created_at
    return out


def contest_of(problem_id: str) -> int | None:
    digits = ""
    for ch in problem_id:
        if not ch.isdigit():
            break
        digits += ch
    return int(digits) if digits else None


def contest_misses(
    attempts: Sequence[Attempt],
    participated: Mapping[int, datetime],
    problems_by_contest: Mapping[int, Sequence[ContestProblem]],
    until: datetime | None = None,
) -> list[Attempt]:
    """Problems from contests the user took part in, which they never submitted to.

    People mostly submit to problems they expect to solve, so submissions alone are almost all
    successes. In a live contest, though, the user saw every problem; the ones they skipped are
    evidence too. They get half weight, since running out of time is not the same as failing."""
    tried = {a.problem_id for a in attempts}
    out: list[Attempt] = []
    for cid, when in participated.items():
        if until is not None and when > until:
            continue
        for p in problems_by_contest.get(cid, ()):
            if p.problem_id in tried:
                continue
            out.append(
                Attempt(
                    problem_id=p.problem_id,
                    name=p.name,
                    rating=p.rating,
                    tags=clean_tags(p.tags),
                    first_at=when,
                    last_at=when,
                    observed=False,
                    weight=MISS_WEIGHT,
                )
            )
    return out
