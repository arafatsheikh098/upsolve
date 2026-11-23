import {
  BarChart3,
  Brain,
  CalendarCheck,
  Flame,
  GitCompareArrows,
  Repeat,
  ShieldCheck,
  Sigma,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import { Link } from "react-router";
import { HandleSearch } from "../components/Layout";
import { Ring } from "../components/ui";
import { delay, useMounted } from "../motion";

const EXAMPLES = ["arafatsheikh098", "tourist", "jiangly"];

const STEPS = [
  {
    icon: Brain,
    title: "Measure every tag",
    body: "A logistic skill model on the Codeforces rating scale estimates how you do on each tag, with an honest 90% range.",
  },
  {
    icon: Target,
    title: "Find the real gaps",
    body: "Tags where you underperform, or that are common at your level but missing from your practice. Each one comes with its evidence.",
  },
  {
    icon: CalendarCheck,
    title: "Practise at the right difficulty",
    body: "Problems you have about a 55% chance of solving, plus one stretch problem and one old failure to upsolve.",
  },
];

const FEATURES = [
  { icon: Sigma, title: "Explainable maths", body: "MAP-fitted logistic model with Laplace intervals. No black box, no AI." },
  { icon: BarChart3, title: "Skill over time", body: "The model is refitted month by month, so you see progress on day one." },
  { icon: Repeat, title: "Spaced upsolving", body: "Failed problems come back after 1, 3, 7 and 21 days until you crack them." },
  { icon: Flame, title: "Daily plan & streak", body: "Verify your handle to get a saved plan, goals and a streak." },
  { icon: GitCompareArrows, title: "Compare handles", body: "See tag by tag where a friend or rival is ahead of you." },
  { icon: ShieldCheck, title: "Public data only", body: "Reads the official Codeforces API. No password ever." },
];

export function HomePage() {
  return (
    <div className="pb-8">
      <section className="relative grid items-center gap-12 pt-6 sm:pt-14 lg:grid-cols-[1.05fr_1fr]">
        <div className="grid-pattern pointer-events-none absolute inset-x-0 -top-10 h-[420px] -z-10" aria-hidden />
        <div>
          <span className="rise inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-ink-2">
            <Sparkles size={13} className="text-accent" aria-hidden />
            Free · Open source · No sign-up
          </span>
          <h1 className="rise mt-5 text-4xl font-bold leading-[1.08] tracking-tight text-ink sm:text-6xl" style={delay(60)}>
            Find the tags holding your <span className="text-gradient">rating</span> back.
          </h1>
          <p className="rise mt-5 max-w-xl text-lg leading-relaxed text-ink-2" style={delay(120)}>
            Upsolve reads your Codeforces history, measures your skill on every tag, and builds a daily
            plan of problems at exactly the right difficulty.
          </p>
          <div className="rise mt-8 max-w-xl" style={delay(180)}>
            <HandleSearch big />
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-ink-2">
              Try
              {EXAMPLES.map((h) => (
                <Link
                  key={h}
                  to={`/u/${h}`}
                  className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-xs font-medium text-ink transition-colors hover:border-accent hover:text-accent-ink"
                >
                  {h}
                </Link>
              ))}
            </div>
          </div>
          <ul className="rise mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-2" style={delay(240)}>
            <li className="flex items-center gap-1.5">
              <Zap size={15} className="text-accent" aria-hidden /> Results in seconds
            </li>
            <li className="flex items-center gap-1.5">
              <Sigma size={15} className="text-accent" aria-hidden /> Explainable model
            </li>
            <li className="flex items-center gap-1.5">
              <ShieldCheck size={15} className="text-accent" aria-hidden /> Public data only
            </li>
          </ul>
        </div>
        <HeroPreview />
      </section>

      <section className="mt-24">
        <h2 className="text-center text-2xl font-semibold tracking-tight text-ink sm:text-3xl">How it works</h2>
        <p className="mx-auto mt-2 max-w-xl text-center text-ink-2">From submission history to a practice plan in three steps.</p>
        <ol className="mt-10 grid gap-4 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="card card-hover rise relative p-6" style={delay(i * 90)}>
              <div className="flex items-center justify-between">
                <span className="bg-gradient grid size-11 place-items-center rounded-2xl text-white shadow-[0_8px_20px_-8px_var(--accent)]">
                  <s.icon size={20} aria-hidden />
                </span>
                <span className="tabular text-4xl font-bold text-line">0{i + 1}</span>
              </div>
              <h3 className="mt-4 font-semibold text-ink">{s.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-20 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f, i) => (
          <div key={f.title} className="rise flex gap-3" style={delay(i * 60)}>
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-wash text-accent-ink">
              <f.icon size={18} aria-hidden />
            </span>
            <div>
              <h3 className="font-semibold text-ink">{f.title}</h3>
              <p className="mt-0.5 text-sm leading-relaxed text-ink-2">{f.body}</p>
            </div>
          </div>
        ))}
      </section>

      <section className="bg-gradient relative mt-20 overflow-hidden rounded-3xl p-8 text-white sm:p-12">
        <div className="pointer-events-none absolute -right-16 -top-16 size-64 rounded-full bg-white/10 blur-2xl" aria-hidden />
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Ready to stop guessing?</h2>
        <p className="mt-2 max-w-lg text-white/85">Enter your handle and get your weak spots in seconds.</p>
        <div className="mt-6 max-w-xl text-ink">
          <HandleSearch />
        </div>
        <p className="mt-4 text-sm text-white/85">
          Curious about the maths?{" "}
          <Link to="/how-it-works" className="font-semibold text-white underline underline-offset-4">
            Read how the model works
          </Link>
        </p>
      </section>
    </div>
  );
}

const DEMO = [
  { tag: "Constructive", v: -98, c: "var(--neg)" },
  { tag: "Bitmasks", v: -60, c: "var(--mid)" },
  { tag: "Binary search", v: -39, c: "var(--mid)" },
  { tag: "Greedy", v: 14, c: "var(--mid)" },
  { tag: "Implementation", v: 27, c: "var(--mid)" },
  { tag: "Math", v: 56, c: "var(--pos)" },
];

/** Decorative, animated preview of the product (example data, hidden from screen readers). */
function HeroPreview() {
  const mounted = useMounted();
  return (
    <div className="relative mx-auto w-full max-w-md lg:max-w-none" aria-hidden>
      <div className="card rise p-5 shadow-[var(--lift)]" style={delay(200)}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-muted">Skill by tag · example</div>
            <div className="mt-0.5 text-sm font-semibold text-ink">Relative to your average tag</div>
          </div>
          <span className="rounded-full bg-accent-wash px-2 py-0.5 text-[11px] font-semibold text-accent-ink">preview</span>
        </div>
        <div className="mt-4 space-y-3">
          {DEMO.map((d, i) => {
            const pos = 50 + (d.v / 150) * 50;
            return (
              <div key={d.tag} className="grid grid-cols-[96px_1fr_36px] items-center gap-3 text-xs">
                <span className="truncate text-right text-ink-2">{d.tag}</span>
                <div className="relative h-2 rounded-full bg-surface-2">
                  <div className="absolute inset-y-0 left-1/2 w-px bg-[var(--axis)]" />
                  <div
                    className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-[var(--surface)]"
                    style={{
                      left: `${mounted ? pos : 50}%`,
                      background: d.c,
                      transition: `left 900ms cubic-bezier(0.2,0.7,0.2,1) ${300 + i * 90}ms`,
                    }}
                  />
                </div>
                <span className="tabular text-right font-medium text-ink">{d.v > 0 ? `+${d.v}` : `−${-d.v}`}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="rise absolute -bottom-10 -left-4 hidden w-64 sm:block" style={delay(500)}>
        <div className="card float flex items-center gap-3 p-4 shadow-[var(--lift)]">
          <Ring value={0.55} size={52} label="55 percent">
            <span className="tabular text-xs font-bold text-ink">55%</span>
          </Ring>
          <div className="min-w-0">
            <div className="text-[11px] font-medium text-accent-ink">Today's pick · Constructive</div>
            <div className="truncate text-sm font-semibold text-ink">Make It Permutation</div>
            <div className="text-[11px] text-muted">Rated 1200</div>
          </div>
        </div>
      </div>

      <div className="rise absolute -right-3 -top-6 hidden sm:block" style={delay(650)}>
        <div
          className="card float flex items-center gap-2 px-3 py-2 text-xs font-medium text-ink shadow-[var(--lift)]"
          style={{ animationDelay: "1.5s" }}
        >
          <Flame size={15} className="flicker text-[var(--series-2)]" />
          7-day streak
        </div>
      </div>
    </div>
  );
}
