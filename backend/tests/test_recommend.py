from datetime import UTC, datetime, timedelta

from app.analysis.features import Attempt
from app.analysis.recommend import ShownHistory, plan_seed, recommend
from app.analysis.report import PoolProblem
from app.analysis.skill import fit_skill
from tests.test_skill_model import ANCHOR, NOW, TRUE_DELTA, simulate

TAGS = list(TRUE_DELTA)


def make_pool() -> list[PoolProblem]:
    pool = []
    for i in range(1200):
        rating = 800 + (i % 18) * 100
        tags = (TAGS[i % len(TAGS)],) if i % 3 else (TAGS[i % len(TAGS)], TAGS[(i + 3) % len(TAGS)])
        pool.append(
            PoolProblem(
                id=f"{1500 + i}A",
                contest_id=1500 + i,
                index="A",
                name=f"Problem {i}",
                rating=rating,
                tags=tags,
                solved_count=5000,
                contest_start=NOW - timedelta(days=30 + i),
            )
        )
    return pool


def setup(solved_only: bool = False):  # type: ignore[no-untyped-def]
    attempts = simulate(600, seed=11)
    if solved_only:  # no unsolved attempts, so nothing else competes for the upsolve slot
        attempts = [a for a in attempts if a.solved]
    fit = fit_skill(attempts, now=NOW, anchor=ANCHOR)
    return fit, attempts, make_pool()


def test_plan_shape_and_rules() -> None:
    fit, attempts, pool = setup()
    failed = Attempt(
        "1A",
        "Old fail",
        1500,
        ("dp",),
        solved=False,
        wrong_total=2,
        last_at=NOW - timedelta(days=10),
    )
    recs = recommend(fit, [], pool, [*attempts, failed], seed="u:1", now=NOW, n=4)
    assert [r.kind for r in recs] == ["weak", "weak", "stretch", "upsolve"]
    unsolved = {a.problem_id for a in attempts if not a.solved} | {"1A"}
    assert recs[-1].problem_id in unsolved
    attempted = {a.problem_id for a in attempts}
    assert not attempted & {r.problem_id for r in recs[:-1]}
    assert len({r.problem_id for r in recs}) == len(recs)
    for r in recs:
        assert r.reason
        assert 0 < r.predicted < 1
    # Weak picks come from the weakest tags at a learnable difficulty.
    weakest = sorted(fit.tags.values(), key=lambda s: s.delta)[0].tag
    assert recs[0].focus_tag == weakest and weakest in recs[0].tags
    assert all(0.35 <= r.predicted <= 0.75 for r in recs[:2])
    assert 0.15 <= recs[2].predicted <= 0.45  # the stretch problem is clearly harder


def test_deterministic_per_day_and_varies_across_days() -> None:
    fit, attempts, pool = setup()
    day = NOW.date()
    a = recommend(fit, [], pool, attempts, seed=plan_seed("u", day), now=NOW)
    b = recommend(fit, [], pool, attempts, seed=plan_seed("u", day), now=NOW)
    assert a == b
    days = [day + timedelta(days=i) for i in range(1, 6)]
    others = [recommend(fit, [], pool, attempts, seed=plan_seed("u", d), now=NOW) for d in days]
    assert any([r.problem_id for r in o] != [r.problem_id for r in a] for o in others)


def test_focus_tags_come_first() -> None:
    fit, attempts, pool = setup()
    recs = recommend(fit, [], pool, attempts, seed="s", now=NOW, n=3, focus_tags=["strings"])
    assert recs[0].focus_tag == "strings"
    assert "focus" in recs[0].reason


def test_upsolve_spacing() -> None:
    fit, attempts, pool = setup(solved_only=True)
    fresh = Attempt("1A", "x", 1500, ("dp",), solved=False, last_at=NOW - timedelta(hours=3))
    recs = recommend(fit, [], pool, [*attempts, fresh], seed="s", now=NOW)
    assert all(r.kind != "upsolve" for r in recs)  # tried 3 hours ago: not due for a day

    old = Attempt("1A", "x", 1500, ("dp",), solved=False, last_at=NOW - timedelta(days=30))
    shown = {"1A": ShownHistory(times=2, last=NOW - timedelta(days=3))}
    recs = recommend(fit, [], pool, [*attempts, old], seed="s", now=NOW, shown=shown)
    assert all(r.kind != "upsolve" for r in recs)  # shown twice, 3 days ago: next is at 7 days

    shown = {"1A": ShownHistory(times=2, last=NOW - timedelta(days=8))}
    recs = recommend(fit, [], pool, [*attempts, old], seed="s", now=NOW, shown=shown)
    assert recs[-1].kind == "upsolve" and recs[-1].reason.startswith("Review #3")


def test_low_quality_and_old_problems_are_skipped() -> None:
    fit, attempts, _ = setup(solved_only=True)
    bad = [
        PoolProblem("1A", 1, "A", "unpopular", 1400, ("dp",), 3, NOW - timedelta(days=10)),
        PoolProblem("2A", 2, "A", "ancient", 1400, ("dp",), 9000, NOW - timedelta(days=4000)),
        PoolProblem("3A", 3, "A", "april fools", 1400, ("dp", "*special"), 9000, NOW),
    ]
    assert recommend(fit, [], bad, attempts, seed="s", now=datetime.now(UTC)) == []
