from datetime import UTC, datetime, timedelta

from app.analysis.features import (
    ContestProblem,
    SubmissionRow,
    build_attempts,
    contest_misses,
    contest_participation,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def sub(pid: str, verdict: str | None, minutes: int, ptype: str = "PRACTICE") -> SubmissionRow:
    return SubmissionRow(
        problem_id=pid,
        name=pid,
        rating=1200,
        tags=("dp", "*special"),
        verdict=verdict,
        created_at=T0 + timedelta(minutes=minutes),
        participant_type=ptype,
        language="C++17",
    )


def test_attempts_count_wrong_answers_and_ignore_compile_errors() -> None:
    attempts = build_attempts(
        [
            sub("1A", "COMPILATION_ERROR", 0),
            sub("1A", "WRONG_ANSWER", 1, "CONTESTANT"),
            sub("1A", "TIME_LIMIT_EXCEEDED", 2, "CONTESTANT"),
            sub("1A", "OK", 60),
            sub("1A", "WRONG_ANSWER", 70),
            sub("2B", "COMPILATION_ERROR", 5),  # only a CE: not an attempt at all
        ]
    )
    assert len(attempts) == 1
    a = attempts[0]
    assert a.solved and a.wrong_before_ac == 2 and a.wrong_total == 3
    assert a.attempted_in_contest and not a.solved_in_contest and a.upsolved
    assert a.tags == ("dp",)  # format tags like *special are dropped


def test_until_cuts_off_later_submissions() -> None:
    subs = [sub("1A", "WRONG_ANSWER", 0), sub("1A", "OK", 100)]
    (a,) = build_attempts(subs, until=T0 + timedelta(minutes=50))
    assert not a.solved


def test_contest_misses_cover_unsubmitted_problems_only() -> None:
    subs = [sub("1900A", "OK", 0, "CONTESTANT"), sub("1900B", "WRONG_ANSWER", 5, "CONTESTANT")]
    attempts = build_attempts(subs)
    participated = contest_participation(subs, rated={})
    assert participated == {1900: T0}
    problems = {
        1900: [
            ContestProblem(f"1900{c}", c, 800 + 300 * i, ("math",)) for i, c in enumerate("ABCD")
        ]
    }
    misses = contest_misses(attempts, participated, problems)
    assert sorted(m.problem_id for m in misses) == ["1900C", "1900D"]
    assert all(not m.observed and not m.solved and m.weight == 0.5 for m in misses)
    assert contest_misses(attempts, participated, problems, until=T0 - timedelta(days=1)) == []
