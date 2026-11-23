import type { ReactNode } from "react";

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold tracking-tight text-ink">{title}</h2>
      <div className="mt-3 space-y-3 leading-relaxed text-ink-2">{children}</div>
    </section>
  );
}

function Formula({ children }: { children: ReactNode }) {
  return (
    <pre className="card overflow-x-auto p-4 text-sm leading-relaxed text-ink">
      <code>{children}</code>
    </pre>
  );
}

export function AboutPage() {
  return (
    <article className="mx-auto max-w-2xl pt-4">
      <h1 className="text-3xl font-semibold tracking-tight text-ink">How Upsolve works</h1>
      <p className="mt-3 text-lg leading-relaxed text-ink-2">
        Upsolve doesn't use AI. It's a small statistical model plus a recommender, and both are
        explainable line by line. This page describes them.
      </p>

      <Block title="1. One row per problem you tried">
        <p>
          Your submissions are grouped by problem. A problem counts as <b className="text-ink">solved</b> if any
          submission was accepted. Wrong answers before the first accept are counted. Compilation errors
          are ignored, since they say nothing about your idea.
        </p>
        <p>
          People mostly submit to problems they expect to solve, so this data is almost all
          successes. To balance it, problems from contests you took part in but never submitted to
          are added as failures at <b className="text-ink">half weight</b>: you saw them and didn't solve them in time.
        </p>
      </Block>

      <Block title="2. A skill model on the Codeforces rating scale">
        <p>The chance of solving problem p is modelled with the same logistic curve Elo ratings use:</p>
        <Formula>
          {"P(solve p) = σ( k · (A + b + Σ δₜ / |tags(p)| − rₚ) )\nk = ln(10) / 400"}
        </Formula>
        <ul className="list-disc space-y-1 pl-5">
          <li><b className="text-ink">rₚ</b> is the problem's rating and <b className="text-ink">A</b> is your current rating.</li>
          <li><b className="text-ink">b</b> is a fitted offset that absorbs selection bias.</li>
          <li><b className="text-ink">δₜ</b> is a fitted offset per tag: how much better or worse you do on that tag. A problem with several tags splits the effect between them.</li>
        </ul>
        <p>
          A clean accept counts as 1. An accept after several wrong answers counts a little less
          (down to 0.5), and an unsolved problem counts as 0. Newer attempts weigh more: an attempt's
          weight halves for every 150 attempts made after it. Decay is by activity, not calendar time,
          so a break from practice doesn't erase your history.
        </p>
      </Block>

      <Block title="3. Honest uncertainty">
        <p>
          Every δₜ has a Gaussian prior N(0, 150²), so a tag you've tried twice is pulled towards
          "average" instead of being called terrible. The model is fitted by maximum a posteriori
          estimation with Newton's method. The objective is convex, so a fit takes a few milliseconds.
        </p>
        <p>
          The 90% ranges come from the Laplace approximation (the inverse Hessian at the optimum).
          Only differences between tags are identifiable, so each tag is reported relative to your
          exposure-weighted average tag, with the matching contrast variance. A tag is called{" "}
          <b className="text-ink">weak</b> or <b className="text-ink">strong</b> only when its entire 90% range is on one side of zero.
        </p>
        <p>
          The test suite simulates users with known per-tag skills and checks that the fit recovers
          them, and that about 90% of the 90% ranges contain the true value.
        </p>
      </Block>

      <Block title="4. What counts as a weak spot">
        <p>Each tag gets a score that combines two things:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li><b className="text-ink">Skill gap:</b> how far below your average the tag is.</li>
          <li>
            <b className="text-ink">Coverage gap:</b> the tag appears often in recent problems near your level,
            but rarely in your practice.
          </li>
        </ul>
        <p>Both are weighted by how common the tag is at your level, so rare tags don't crowd out common ones.</p>
      </Block>

      <Block title="5. Choosing problems">
        <p>For each weak tag, the recommender looks for unsolved problems where the model predicts about a{" "}
          <b className="text-ink">55% chance</b> of solving. That's hard enough to learn from but not hopeless. It
          prefers recent rounds, problems where the tag is central, and problems enough people have
          solved. A daily plan also includes:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>one <b className="text-ink">stretch</b> problem at about a 30% chance</li>
          <li>
            one problem you <b className="text-ink">failed before</b>, brought back with spaced repetition at
            1, 3, 7 and then 21 days
          </li>
        </ul>
        <p>Picks are seeded by handle and date, so a plan doesn't change when you reload the page.</p>
      </Block>

      <Block title="Limitations">
        <ul className="list-disc space-y-1 pl-5">
          <li>Tags on Codeforces are coarse and sometimes missing, and unrated problems are skipped.</li>
          <li>The model doesn't know about time pressure, editorials you read, or help from others.</li>
          <li>Users with few attempts get wide ranges. That's correct, but it means fewer clear verdicts.</li>
        </ul>
      </Block>
    </article>
  );
}
