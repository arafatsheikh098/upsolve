import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheck,
  CalendarCheck,
  Flame,
  LineChart,
  ListChecks,
  Loader2,
  PartyPopper,
  RefreshCw,
  Settings2,
  Trophy,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, type Goals } from "../api";
import { TagHistoryChart, WeeklyChart } from "../charts/charts";
import { Confetti } from "../components/Confetti";
import { ProblemCard } from "../components/insights";
import { HandleSearch } from "../components/Layout";
import { Button, CountUp, Notice, Ring, Section, Skeleton } from "../components/ui";
import { relativeTime, tagTitle } from "../format";
import { useMe, useSyncedHandle } from "../hooks";
import { delay } from "../motion";

const COMMON_TAGS = [
  "binary search", "bitmasks", "brute force", "combinatorics", "constructive algorithms",
  "data structures", "dfs and similar", "dp", "dsu", "games", "geometry", "graphs", "greedy",
  "hashing", "implementation", "interactive", "math", "number theory", "probabilities",
  "shortest paths", "sortings", "strings", "trees", "two pointers",
];

export function PlanPage() {
  const me = useMe();
  if (me.isLoading) return <Skeleton className="h-40" />;
  if (!me.data)
    return (
      <div className="mx-auto max-w-xl pt-10 text-center">
        <span className="bg-gradient mx-auto grid size-14 place-items-center rounded-2xl text-white shadow-[0_10px_28px_-10px_var(--accent)]">
          <CalendarCheck size={26} aria-hidden />
        </span>
        <h1 className="mt-5 text-3xl font-bold tracking-tight text-ink">Your daily plan</h1>
        <p className="mt-3 text-ink-2">
          Verify your Codeforces handle to get a saved daily plan, goals and a streak. Analyze your
          handle, then press <b className="text-ink">This is me: verify</b> on your profile. It takes about a minute.
        </p>
        <div className="mt-7 text-left">
          <HandleSearch big />
        </div>
        <ul className="mt-8 grid gap-3 text-left text-sm sm:grid-cols-3">
          {[
            { icon: ListChecks, text: "Fresh problems every day" },
            { icon: Flame, text: "Streaks that keep you going" },
            { icon: Settings2, text: "Your own focus tags" },
          ].map(({ icon: Icon, text }, i) => (
            <li key={text} className="card rise flex items-center gap-2 p-3 text-ink-2" style={delay(i * 70)}>
              <Icon size={16} className="text-accent" aria-hidden /> {text}
            </li>
          ))}
        </ul>
      </div>
    );
  return <Plan handle={me.data.handle} />;
}

function Plan({ handle }: { handle: string }) {
  const qc = useQueryClient();
  const sync = useSyncedHandle(handle);
  const syncedAt = sync.status?.last_synced_at;
  const plan = useQuery({
    queryKey: ["plan", syncedAt],
    queryFn: api.plan,
    enabled: !!syncedAt,
    placeholderData: (p) => p,
  });
  // Load progress after the plan exists, so today's plan is included in the counts.
  const progress = useQuery({
    queryKey: ["progress", syncedAt, plan.data?.solved_today],
    queryFn: api.progress,
    enabled: !!plan.data,
    placeholderData: (p) => p,
  });
  const refresh = useMutation({
    mutationFn: () => api.sync(handle, true),
    onSuccess: (s) => qc.setQueryData(["status", handle.toLowerCase()], s),
  });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: "todo" | "skipped" }) => api.setItemStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan"] }),
  });

  const p = plan.data;
  const total = p?.items.length ?? 0;
  const solved = p?.solved_today ?? 0;
  const allDone = total > 0 && solved === total;

  // Celebrate when a new solve shows up (not on first load).
  const [burst, setBurst] = useState(0);
  const prevSolved = useRef<number | null>(null);
  useEffect(() => {
    if (p == null) return;
    if (prevSolved.current != null && solved > prevSolved.current) setBurst((b) => b + 1);
    prevSolved.current = solved;
  }, [p, solved]);

  const busy = sync.syncing || refresh.isPending;

  return (
    <div>
      <Confetti fire={burst} />

      <header className="card relative overflow-hidden p-5 sm:p-6">
        <div className="bg-gradient pointer-events-none absolute -right-20 -top-24 size-72 rounded-full opacity-15 blur-3xl" aria-hidden />
        <div className="relative flex flex-wrap items-center gap-6">
          <Ring value={total ? solved / total : 0} size={104} stroke={10} label={`${solved} of ${total} solved today`}>
            <div className="text-center">
              <div className="tabular text-2xl font-bold text-ink">
                {solved}/{total}
              </div>
              <div className="text-[11px] text-muted">solved</div>
            </div>
          </Ring>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-medium uppercase tracking-wider text-accent-ink">Today's plan</div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-3xl">
              {allDone ? "All done. Great work!" : p ? `${total - solved} problem${total - solved === 1 ? "" : "s"} to go` : "Building your plan…"}
            </h1>
            <p className="mt-1 text-sm text-ink-2">
              {p
                ? new Date(p.day + "T00:00:00Z").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: "UTC" })
                : " "}
              {" · "}synced {relativeTime(syncedAt)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3">
              <Flame
                size={28}
                className={(p?.streak ?? 0) > 0 ? "flicker text-[var(--series-2)]" : "text-muted"}
                aria-hidden
              />
              <div>
                <div className="tabular text-xl font-bold leading-none text-ink">
                  <CountUp value={p?.streak ?? 0} />
                </div>
                <div className="mt-1 text-[11px] text-muted">day streak</div>
              </div>
            </div>
            <Button kind="secondary" onClick={() => refresh.mutate()} disabled={busy}>
              {busy ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <RefreshCw size={16} aria-hidden />}
              {busy ? "Checking Codeforces…" : "I solved something"}
            </Button>
          </div>
        </div>
        {allDone && (
          <div className="pop relative mt-5 flex items-center gap-3 rounded-xl bg-accent-wash px-4 py-3 text-sm text-accent-ink">
            <PartyPopper size={18} aria-hidden />
            Every problem in today's plan is solved. Come back tomorrow for a fresh set.
          </div>
        )}
      </header>

      {plan.error && (
        <div className="mt-6">
          <Notice tone="error">{plan.error.message}</Notice>
        </div>
      )}

      <Section
        icon={ListChecks}
        title="Problems"
        subtitle="Solve them on Codeforces. Accepted submissions are detected when you press “I solved something”, and automatically twice a day."
      >
        <div className="grid gap-4 md:grid-cols-2">
          {!p && !plan.error && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-52" />)}
          {p?.items.map((item, i) => (
            <ProblemCard
              key={item.id}
              rec={item}
              status={item.status}
              style={delay(i * 70)}
              actions={
                item.status === "todo" ? (
                  <Button kind="ghost" className="px-2.5 py-1 text-xs" onClick={() => setStatus.mutate({ id: item.id, status: "skipped" })}>
                    Skip for today
                  </Button>
                ) : item.status === "skipped" ? (
                  <Button kind="ghost" className="px-2.5 py-1 text-xs" onClick={() => setStatus.mutate({ id: item.id, status: "todo" })}>
                    Undo skip
                  </Button>
                ) : (
                  <span className="inline-flex items-center gap-1.5 text-xs font-medium text-good">
                    <BadgeCheck size={14} aria-hidden /> Solved — counted towards your streak
                  </span>
                )
              }
            />
          ))}
        </div>
      </Section>

      {progress.data && (
        <Section icon={LineChart} title="Progress">
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[
              { icon: CalendarCheck, label: "Plans so far", value: progress.data.plan_days },
              { icon: Trophy, label: "Plan problems solved", value: progress.data.plan_solved },
              { icon: Flame, label: "Current streak", value: progress.data.streak },
            ].map(({ icon: Icon, label, value }, i) => (
              <div key={label} className="card rise flex items-center gap-3 p-4" style={delay(i * 70)}>
                <span className="grid size-10 place-items-center rounded-xl bg-accent-wash text-accent-ink">
                  <Icon size={18} aria-hidden />
                </span>
                <div>
                  <div className="text-2xl font-bold text-ink">
                    <CountUp value={value} />
                  </div>
                  <div className="text-xs text-muted">{label}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <TagHistoryChart history={progress.data.history} initial={[]} />
            <WeeklyChart data={progress.data.weekly} />
          </div>
        </Section>
      )}

      <Section icon={Settings2} title="Goals" subtitle="Changes apply from tomorrow's plan.">
        <GoalsForm />
      </Section>
    </div>
  );
}

function GoalsForm() {
  const goals = useQuery({ queryKey: ["goals"], queryFn: api.goals });
  if (goals.error) return <Notice tone="error">{goals.error.message}</Notice>;
  if (!goals.data) return <Skeleton className="h-48" />;
  return <GoalsEditor initial={goals.data} />;
}

function GoalsEditor({ initial }: { initial: Goals }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Goals>(initial);
  const save = useMutation({
    mutationFn: api.saveGoals,
    onSuccess: (g) => {
      qc.setQueryData(["goals"], g);
      setDraft(g);
    },
  });

  const toggleTag = (t: string) =>
    setDraft((d) =>
      ({
        ...d,
        focus_tags: d.focus_tags.includes(t)
          ? d.focus_tags.filter((x) => x !== t)
          : d.focus_tags.length < 3
            ? [...d.focus_tags, t]
            : d.focus_tags,
      }),
    );
  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate(draft);
  };

  return (
    <form onSubmit={submit} className="card rise space-y-6 p-5 sm:p-6">
      <div className="flex flex-wrap gap-6">
        <div className="text-sm text-ink-2">
          Problems per day
          <div className="mt-1.5 flex rounded-xl bg-surface-2 p-1" role="group" aria-label="Problems per day">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
              <button
                type="button"
                key={n}
                aria-pressed={draft.daily_count === n}
                onClick={() => setDraft({ ...draft, daily_count: n })}
                className={`tabular size-8 rounded-lg text-sm font-medium transition-colors ${
                  draft.daily_count === n ? "bg-gradient text-white shadow-sm" : "text-ink-2 hover:text-ink"
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
        <label className="text-sm text-ink-2">
          Target rating (optional)
          <input
            type="number"
            min={800}
            max={3500}
            step={100}
            value={draft.target_rating ?? ""}
            onChange={(e) => setDraft({ ...draft, target_rating: e.target.value ? Number(e.target.value) : null })}
            className="mt-1.5 block w-32 rounded-xl border border-line bg-surface px-3 py-1.5 text-ink focus:border-accent focus:outline-none"
          />
        </label>
      </div>
      <fieldset>
        <legend className="text-sm text-ink-2">Focus tags (up to 3). These are picked before the model's weak spots.</legend>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {COMMON_TAGS.map((t) => {
            const on = draft.focus_tags.includes(t);
            return (
              <button
                type="button"
                key={t}
                aria-pressed={on}
                onClick={() => toggleTag(t)}
                disabled={!on && draft.focus_tags.length >= 3}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition-all disabled:opacity-40 ${
                  on ? "bg-gradient border-transparent text-white shadow-sm" : "border-line text-ink-2 hover:border-accent hover:text-ink"
                }`}
              >
                {tagTitle(t)}
              </button>
            );
          })}
        </div>
      </fieldset>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={save.isPending}>
          Save goals
        </Button>
        {save.isSuccess && (
          <span className="pop inline-flex items-center gap-1 text-sm text-good">
            <BadgeCheck size={15} aria-hidden /> Saved
          </span>
        )}
        {save.error && <span className="text-sm text-bad">{save.error.message}</span>}
      </div>
    </form>
  );
}
