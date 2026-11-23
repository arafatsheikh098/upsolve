import { Check, ExternalLink, EyeOff, Repeat, Rocket, Target, TrendingDown, XCircle } from "lucide-react";
import { useState } from "react";
import type { Recommendation, TagSkill, Weakness } from "../api";
import { Forest, type ForestRow } from "../charts/Forest";
import { LABEL_TEXT, labelColor, pct, signed, tagTitle } from "../format";
import { useMounted } from "../motion";
import { ChartCard, DataTable, LegendItem, Pill, Ring } from "./ui";

export function SkillChart({ skills }: { skills: TagSkill[] }) {
  const [all, setAll] = useState(false);
  const enough = skills.filter((s) => s.attempts >= 3);
  const shown = (all ? skills.filter((s) => s.attempts > 0) : enough).sort((a, b) => a.delta - b.delta);
  const hidden = skills.filter((s) => s.attempts > 0).length - enough.length;

  const rows: ForestRow[] = shown.map((s) => ({
    id: s.tag,
    label: tagTitle(s.tag),
    valueText: signed(s.delta),
    points: [{ value: s.delta, low: s.ci_low, high: s.ci_high, color: labelColor(s.label) }],
    tooltip: (
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-2">
          <span className="font-semibold text-ink">{tagTitle(s.tag)}</span>
          <span className="text-ink-2">{LABEL_TEXT[s.label]}</span>
        </div>
        <div className="tabular text-ink">
          <b>{signed(s.delta)}</b> vs your average tag
        </div>
        <div className="tabular text-ink-2">
          90% range {signed(s.ci_low)} to {signed(s.ci_high)}
        </div>
        <div className="tabular text-ink-2">
          Est. level {Math.round(s.level)} · {s.solved}/{s.attempts} solved
        </div>
      </div>
    ),
  }));

  return (
    <ChartCard
      title="Skill by tag"
      subtitle="Each dot is the model's estimate relative to your average tag; the bar is its 90% range. A tag counts as weak or strong only when the whole range is on one side."
      legend={
        <>
          <LegendItem color="var(--neg)" label="Weak" />
          <LegendItem color="var(--mid)" label="Average / unclear" />
          <LegendItem color="var(--pos)" label="Strong" />
        </>
      }
      table={
        <DataTable
          head={["Tag", "Offset", "90% range", "Level", "Solved / tried", "Verdict"]}
          rows={shown.map((s) => [
            tagTitle(s.tag),
            signed(s.delta),
            `${signed(s.ci_low)} to ${signed(s.ci_high)}`,
            Math.round(s.level),
            `${s.solved} / ${s.attempts}`,
            LABEL_TEXT[s.label],
          ])}
        />
      }
    >
      {rows.length ? (
        <Forest rows={rows} ariaLabel="Estimated skill per tag with 90% intervals" />
      ) : (
        <p className="py-8 text-center text-sm text-ink-2">Solve a few more problems to see per-tag estimates.</p>
      )}
      {hidden > 0 && (
        <button className="mt-2 text-xs font-medium text-accent-ink hover:underline" onClick={() => setAll((v) => !v)}>
          {all ? "Hide tags with fewer than 3 attempts" : `Show ${hidden} more tags with fewer than 3 attempts`}
        </button>
      )}
    </ChartCard>
  );
}

export function WeaknessCard({ w, rank, style }: { w: Weakness; rank: number; style?: React.CSSProperties }) {
  const e = w.evidence;
  const mounted = useMounted();
  // Severity bar: how much of the strongest possible weakness score this one reaches.
  const severity = Math.min(1, w.score / 1.2);
  return (
    <article className="card card-hover rise relative flex flex-col overflow-hidden p-5" style={style}>
      <div className="absolute inset-x-0 top-0 h-1 bg-surface-2">
        <div
          className="h-full rounded-r-full bg-[var(--neg)]"
          style={{ width: mounted ? `${Math.max(12, severity * 100)}%` : "0%", transition: "width 900ms cubic-bezier(0.2,0.7,0.2,1) 200ms" }}
        />
      </div>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="tabular grid size-7 shrink-0 place-items-center rounded-lg bg-surface-2 text-xs font-bold text-ink-2">
            {rank}
          </span>
          <h3 className="font-semibold text-ink">{tagTitle(w.tag)}</h3>
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-1">
          {w.kinds.includes("skill") && (
            <Pill tone="bad">
              <TrendingDown size={12} aria-hidden /> {w.label === "weak" ? "Weak" : "Likely weak"}
            </Pill>
          )}
          {w.kinds.includes("coverage") && (
            <Pill>
              <EyeOff size={12} aria-hidden /> Under-practised
            </Pill>
          )}
        </div>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-ink-2">{w.summary}</p>
      <dl className="mt-4 grid grid-cols-3 gap-2 rounded-xl bg-surface-2 p-3 text-xs">
        <div>
          <dt className="text-muted">Solved</dt>
          <dd className="tabular mt-0.5 font-semibold text-ink">
            {e.solved}/{e.attempts}
          </dd>
        </div>
        <div>
          <dt className="text-muted">WA before AC</dt>
          <dd className="tabular mt-0.5 font-semibold text-ink">{e.avg_wrong_before_ac?.toFixed(1) ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-muted">Hardest solved</dt>
          <dd className="tabular mt-0.5 font-semibold text-ink">{e.hardest_solved?.rating ?? "—"}</dd>
        </div>
      </dl>
      {e.recent_failures.length > 0 && (
        <div className="mt-4 text-xs">
          <div className="mb-1.5 font-medium text-muted">Recently not solved</div>
          <ul className="space-y-1">
            {e.recent_failures.map((p) => (
              <li key={p.id} className="flex items-center gap-1.5 truncate">
                <XCircle size={12} className="shrink-0 text-[var(--neg)]" aria-hidden />
                <a href={p.url ?? undefined} target="_blank" rel="noreferrer" className="truncate text-accent-ink hover:underline">
                  {p.id} · {p.name}
                </a>
                <span className="shrink-0 text-muted">· {p.rating ?? "?"}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

const KIND = {
  weak: { text: "Weak spot", icon: Target, tone: "accent" },
  stretch: { text: "Stretch", icon: Rocket, tone: "accent" },
  upsolve: { text: "Upsolve", icon: Repeat, tone: "neutral" },
} as const;

export function ProblemCard({
  rec,
  status,
  actions,
  style,
}: {
  rec: Recommendation;
  status?: "todo" | "solved" | "skipped";
  actions?: React.ReactNode;
  style?: React.CSSProperties;
}) {
  const p = rec.problem;
  const done = status === "solved";
  const kind = KIND[rec.kind];
  return (
    <article
      className={`card card-hover rise relative flex flex-col overflow-hidden p-5 ${status === "skipped" ? "opacity-55" : ""} ${
        done ? "border-[var(--good)]" : ""
      }`}
      style={style}
    >
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Pill tone={kind.tone}>
              <kind.icon size={12} aria-hidden />
              {kind.text}
              {rec.focus_tag ? ` · ${tagTitle(rec.focus_tag)}` : ""}
            </Pill>
            {status === "skipped" && <Pill>Skipped</Pill>}
          </div>
          <h3 className="mt-2.5 text-base font-semibold leading-snug text-ink">
            <a href={p.url ?? undefined} target="_blank" rel="noreferrer" className="group inline-flex items-start gap-1 hover:text-accent-ink">
              <span>
                {p.id}. {p.name}
              </span>
              <ExternalLink size={13} className="mt-1 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
            </a>
          </h3>
          <div className="mt-1.5 flex flex-wrap gap-1">
            <span className="tabular rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] font-semibold text-ink">{p.rating ?? "?"}</span>
            {p.tags.map((t) => (
              <span key={t} className="rounded-md border border-line px-1.5 py-0.5 text-[11px] text-ink-2">
                {tagTitle(t)}
              </span>
            ))}
          </div>
        </div>
        {done ? (
          <span className="pop grid size-14 shrink-0 place-items-center rounded-full bg-[var(--good)] text-white" aria-label="Solved">
            <Check size={26} strokeWidth={3} aria-hidden />
          </span>
        ) : (
          <Ring value={rec.predicted} size={56} label={`Predicted chance to solve: ${pct(rec.predicted)}`}>
            <span className="tabular text-xs font-bold text-ink">{pct(rec.predicted)}</span>
          </Ring>
        )}
      </div>
      <p className="mt-3 flex-1 text-sm leading-relaxed text-ink-2">{rec.reason}</p>
      {actions && <div className="mt-3 flex gap-2 border-t border-line pt-3">{actions}</div>}
    </article>
  );
}
