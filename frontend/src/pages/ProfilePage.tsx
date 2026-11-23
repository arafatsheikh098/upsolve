import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BadgeCheck,
  CalendarCheck,
  CheckCircle2,
  Dumbbell,
  Gauge,
  Loader2,
  RefreshCw,
  Repeat,
  ScanSearch,
  Target,
  TrendingUp,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api, type Analysis, type SyncStatus } from "../api";
import { RatingChart, SolvedByRating, TagHistoryChart, WeeklyChart } from "../charts/charts";
import { ProblemCard, SkillChart, WeaknessCard } from "../components/insights";
import { Button, ButtonLink, ChartCard, CountUp, Notice, Section, Skeleton, Stat } from "../components/ui";
import { VerifyDialog } from "../components/VerifyDialog";
import { useAnalysis, useMe, useSyncedHandle } from "../hooks";
import { int, relativeTime, tagTitle } from "../format";
import { delay, useMounted } from "../motion";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "weak-spots", label: "Weak spots" },
  { id: "practise", label: "Practise" },
  { id: "skills", label: "Skills" },
  { id: "activity", label: "Activity" },
];

export function ProfilePage() {
  const { handle = "" } = useParams();
  const sync = useSyncedHandle(handle);
  const analysis = useAnalysis(handle, sync.status?.last_synced_at);
  const me = useMe();
  const [verifying, setVerifying] = useState(false);
  const isMine = me.data?.handle.toLowerCase() === handle.toLowerCase();

  const recs = useQuery({
    queryKey: ["recs", handle.toLowerCase(), sync.status?.last_synced_at],
    queryFn: () => api.recommendations(handle, 4),
    enabled: sync.ready,
  });

  const s = sync.status;
  const a = analysis.data;
  const name = s?.handle ?? handle;

  return (
    <div>
      <ProfileHero
        name={name}
        status={s}
        syncing={sync.syncing}
        action={
          sync.ready &&
          (isMine ? (
            <ButtonLink to="/plan">
              <CalendarCheck size={16} aria-hidden /> Open my plan
            </ButtonLink>
          ) : (
            <Button kind="secondary" onClick={() => setVerifying(true)}>
              <BadgeCheck size={16} aria-hidden /> This is me: verify
            </Button>
          ))
        }
      />

      {verifying && <VerifyDialog handle={name} onClose={() => setVerifying(false)} />}

      <div className="mt-6 space-y-4">
        {sync.error && <Notice tone="error">{sync.error.message}</Notice>}
        {s?.sync_state === "error" && <Notice tone="error">{s.sync_error}</Notice>}
        {analysis.error && <Notice tone="error">{analysis.error.message}</Notice>}
      </div>

      {!sync.ready && !sync.error && s?.sync_state !== "error" && <SyncProgress status={s} />}
      {sync.ready && !a && !analysis.error && <ProfileSkeleton />}

      {a && (
        <div className={analysis.isFetching ? "opacity-70 transition-opacity" : "transition-opacity"}>
          <SectionTabs />

          <section id="overview" className="scroll-mt-32">
            <Overview a={a} />
          </section>

          <Section
            id="weak-spots"
            icon={Target}
            title="Weak spots"
            subtitle="Ranked by how far below your average you perform and how often the tag shows up at your level."
          >
            {a.weaknesses.length ? (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {a.weaknesses.map((w, i) => (
                  <WeaknessCard key={w.tag} w={w} rank={i + 1} style={delay(i * 70)} />
                ))}
              </div>
            ) : (
              <Notice>
                No clear weak spots yet. Your tags look balanced, or there isn't enough data. The
                suggestions below still target your lowest-rated tags.
              </Notice>
            )}
          </Section>

          <Section
            id="practise"
            icon={Dumbbell}
            title="Practise next"
            subtitle="Today's picks for this handle. They change daily, and stay the same within a day."
            action={
              isMine ? (
                <Link to="/plan" className="text-sm font-medium text-accent-ink hover:underline">
                  Track them in My plan →
                </Link>
              ) : (
                <button onClick={() => setVerifying(true)} className="text-sm font-medium text-accent-ink hover:underline">
                  Verify to save plans and streaks →
                </button>
              )
            }
          >
            {recs.error && <Notice tone="error">{recs.error.message}</Notice>}
            {recs.data && recs.data.items.length === 0 && (
              <Notice>The problem list is still loading on the server. Try again in a minute.</Notice>
            )}
            <div className="grid gap-4 md:grid-cols-2">
              {recs.isLoading &&
                [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-48" />)}
              {recs.data?.items.map((r, i) => (
                <ProblemCard key={r.problem.id} rec={r} style={delay(i * 70)} />
              ))}
            </div>
          </Section>

          <Section id="skills" icon={ScanSearch} title="Skill profile" subtitle="Hover or focus a row for details. Every chart also has a table view.">
            <div className="grid gap-4 lg:grid-cols-2">
              <SkillChart skills={a.skills} />
              <TagHistoryChart history={a.history} initial={a.weaknesses.slice(0, 3).map((w) => w.tag)} />
            </div>
          </Section>

          <Section id="activity" icon={Activity} title="Activity">
            <div className="grid gap-4 lg:grid-cols-2">
              <RatingChart data={a.rating_history} />
              <SolvedByRating data={a.by_rating} />
              <WeeklyChart data={a.weekly} />
              <Breakdown a={a} />
            </div>
          </Section>
        </div>
      )}
    </div>
  );
}

function ProfileHero({
  name,
  status: s,
  syncing,
  action,
}: {
  name: string;
  status: SyncStatus | undefined;
  syncing: boolean;
  action: React.ReactNode;
}) {
  const below = s?.rating != null && s.max_rating != null ? s.max_rating - s.rating : 0;
  return (
    <header className="card overflow-hidden">
      <div className="bg-gradient relative h-20 sm:h-24" aria-hidden>
        <div className="grid-pattern absolute inset-0 opacity-40" />
      </div>
      <div className="flex flex-wrap items-start gap-x-4 gap-y-3 px-5 pb-5 pt-3 sm:px-6">
        <div className="relative z-10 -mt-12 rounded-2xl bg-surface p-1 shadow-[var(--lift)]">
          {s?.avatar ? (
            <img src={s.avatar} alt="" className="size-20 rounded-xl object-cover" />
          ) : (
            <div className="bg-gradient grid size-20 place-items-center rounded-xl text-3xl font-bold uppercase text-white">
              {name[0]}
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-bold tracking-tight text-ink sm:text-3xl">{name}</h1>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-ink-2">
            {s?.rank && (
              <span className="rounded-full bg-accent-wash px-2.5 py-0.5 text-xs font-semibold capitalize text-accent-ink">
                {s.rank}
              </span>
            )}
            {s?.rating != null && (
              <span className="tabular">
                <b className="text-ink">{s.rating}</b>
                {s.max_rating != null && (
                  <span className="text-muted">
                    {" "}
                    · peak {s.max_rating}
                    {below > 0 && ` (${below} to go)`}
                  </span>
                )}
              </span>
            )}
            {s?.last_synced_at && (
              <span className="inline-flex items-center gap-1 text-xs text-muted">
                {syncing ? (
                  <Loader2 size={12} className="animate-spin" aria-hidden />
                ) : (
                  <RefreshCw size={12} aria-hidden />
                )}
                {syncing ? "Refreshing…" : `Synced ${relativeTime(s.last_synced_at)}`} · {int(s.submissions)} submissions
              </span>
            )}
          </div>
        </div>
        {action}
      </div>
    </header>
  );
}

const SYNC_STEPS = ["Profile", "Submissions", "Rating history", "Skill model"];

function SyncProgress({ status }: { status: SyncStatus | undefined }) {
  const count = status?.submissions ?? 0;
  // Profile is fetched first; once the job is running we're on submissions.
  const step = !status || status.sync_state === "queued" ? 0 : 1;
  return (
    <div className="card rise mt-6 flex flex-col items-center px-6 py-14 text-center">
      <div className="relative grid size-20 place-items-center">
        <span className="pulse-ring absolute inset-0 rounded-full bg-accent/30" />
        <span className="pulse-ring absolute inset-0 rounded-full bg-accent/20" style={{ animationDelay: "0.6s" }} />
        <span className="bg-gradient relative grid size-14 place-items-center rounded-full text-white shadow-[0_8px_24px_-8px_var(--accent)]">
          <ScanSearch size={24} aria-hidden />
        </span>
      </div>
      <h2 className="mt-6 text-lg font-semibold text-ink">
        {status?.sync_state === "queued" ? "Getting ready…" : "Reading your Codeforces history"}
      </h2>
      <p className="mt-1 text-sm text-ink-2" aria-live="polite">
        {count > 0 ? (
          <>
            <b className="text-ink">
              <CountUp value={count} />
            </b>{" "}
            submissions fetched so far
          </>
        ) : (
          "Codeforces allows one request every two seconds, so this takes a few seconds."
        )}
      </p>
      <ol className="mt-6 flex flex-wrap justify-center gap-2 text-xs">
        {SYNC_STEPS.map((label, i) => {
          const done = i < step;
          const active = i === step;
          return (
            <li
              key={label}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 ${
                active ? "border-accent text-accent-ink" : done ? "border-line text-ink" : "border-line text-muted"
              }`}
            >
              {done ? (
                <CheckCircle2 size={13} className="text-[var(--good)]" aria-hidden />
              ) : active ? (
                <Loader2 size={13} className="animate-spin" aria-hidden />
              ) : (
                <span className="size-1.5 rounded-full bg-[var(--axis)]" />
              )}
              {label}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function ProfileSkeleton() {
  return (
    <div className="mt-6 space-y-6" aria-label="Loading analysis">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-56" />
        ))}
      </div>
    </div>
  );
}

/** Sticky in-page navigation with scroll-spy. */
function SectionTabs() {
  const [active, setActive] = useState("overview");
  useEffect(() => {
    const els = SECTIONS.map((s) => document.getElementById(s.id)).filter((e): e is HTMLElement => !!e);
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-30% 0px -60% 0px" },
    );
    els.forEach((e) => obs.observe(e));
    return () => obs.disconnect();
  }, []);
  return (
    <nav
      className="sticky top-[61px] z-20 -mx-4 mb-6 mt-6 overflow-x-auto border-b border-line bg-page/80 px-4 backdrop-blur-xl sm:top-[61px]"
      aria-label="Sections"
    >
      <ul className="flex gap-1 py-2">
        {SECTIONS.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              aria-current={active === s.id ? "true" : undefined}
              className={`block whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                active === s.id ? "bg-surface text-ink shadow-sm" : "text-ink-2 hover:text-ink"
              }`}
            >
              {s.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function Overview({ a }: { a: Analysis }) {
  const o = a.overview;
  const rating = a.handle.rating;
  const easy = o.comfort_median != null && rating != null && o.comfort_median < rating - 200;
  const top = a.weaknesses[0];
  return (
    <div className="space-y-3">
      {top && (
        <div className="card rise flex flex-wrap items-center gap-3 border-accent/30 bg-accent-wash/40 p-4 text-sm">
          <span className="bg-gradient grid size-9 place-items-center rounded-xl text-white">
            <TrendingUp size={17} aria-hidden />
          </span>
          <p className="min-w-0 flex-1 text-ink">
            <b>Biggest opportunity: {tagTitle(top.tag)}.</b>{" "}
            <span className="text-ink-2">
              {easy
                ? "Also, most of your recent solves are well below your rating. Harder problems build skill faster."
                : "Today's picks below start there."}
            </span>
          </p>
          <a href="#practise" className="text-sm font-semibold text-accent-ink hover:underline">
            See problems →
          </a>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          icon={Gauge}
          label="Effective level"
          value={<CountUp value={o.level} />}
          note={`± ${int(o.level_sd)}. The problem rating at which you solve about half of what you try.`}
        />
        <Stat
          icon={CheckCircle2}
          label="Problems solved"
          value={<CountUp value={o.solved} />}
          note={`of ${int(o.attempts)} attempted · ${int(o.submissions)} submissions`}
          style={delay(70)}
        />
        <Stat
          icon={Repeat}
          label="Upsolve rate"
          value={o.upsolve.rate == null ? "—" : <CountUp value={o.upsolve.rate * 100} format={(n) => `${Math.round(n)}%`} />}
          note={
            o.upsolve.failed_in_contest
              ? `${o.upsolve.upsolved} of ${o.upsolve.failed_in_contest} problems missed in contests were solved later`
              : "No missed contest problems yet"
          }
          style={delay(140)}
        />
        <Stat
          icon={Dumbbell}
          label="Recent practice difficulty"
          value={o.comfort_median != null ? <CountUp value={o.comfort_median} /> : "—"}
          note={
            o.comfort_median == null
              ? "Nothing solved in the last 6 months"
              : easy
                ? "Median of the last 6 months, well below your rating"
                : "Median rating of problems solved in the last 6 months"
          }
          style={delay(210)}
        />
      </div>
    </div>
  );
}

function Breakdown({ a }: { a: Analysis }) {
  const mounted = useMounted();
  const lists = [
    { title: "Verdicts", data: a.overview.verdicts },
    { title: "Languages", data: a.overview.languages },
  ];
  return (
    <ChartCard title="Submissions" subtitle="Every submission, by verdict and language">
      <div className="grid gap-6 sm:grid-cols-2">
        {lists.map(({ title, data }) => {
          const entries = Object.entries(data).slice(0, 6);
          const max = Math.max(1, ...entries.map(([, v]) => v));
          return (
            <div key={title}>
              <h4 className="mb-2 text-xs font-medium text-muted">{title}</h4>
              <ul className="space-y-2.5">
                {entries.map(([k, v], i) => (
                  <li key={k} className="text-xs">
                    <div className="flex justify-between gap-2">
                      <span className="truncate capitalize text-ink-2">{k.replaceAll("_", " ").toLowerCase()}</span>
                      <span className="tabular font-medium text-ink">{int(v)}</span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-surface-2">
                      <div
                        className="bg-gradient h-full rounded-full"
                        style={{
                          width: mounted ? `${(v / max) * 100}%` : "0%",
                          transition: `width 800ms cubic-bezier(0.2,0.7,0.2,1) ${i * 60}ms`,
                        }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </ChartCard>
  );
}
