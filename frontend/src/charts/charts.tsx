import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent";
import type { Analysis, History, WeekStat } from "../api";
import { ChartCard, DataTable, LegendItem } from "../components/ui";
import { dayMonth, int, shortDate, tagTitle } from "../format";

type TipProps = TooltipContentProps<ValueType, NameType>;

/** Round a y-domain out to clean steps so ticks land on 0 / 100 / 200 … rather than 1,261. */
function niceDomain(values: (number | null | undefined)[]): { domain: [number, number]; ticks: number[] } {
  const v = values.filter((x): x is number => x != null);
  const lo = Math.min(...v);
  const hi = Math.max(...v);
  const span = Math.max(hi - lo, 100);
  const step = [50, 100, 200, 250, 500].find((s) => span / s <= 5) ?? 1000;
  const start = Math.floor(lo / step) * step;
  const end = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let t = start; t <= end; t += step) ticks.push(t);
  return { domain: [start, end], ticks };
}

const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];
const axisProps = {
  stroke: "var(--axis)",
  tick: { fill: "var(--muted)", fontSize: 11 },
  tickLine: false,
} as const;

interface Row {
  name: string;
  value: string;
  color: string;
}

function TipBox({ title, rows }: { title: string; rows: Row[] }) {
  return (
    <div className="card min-w-40 p-2.5 text-xs">
      <div className="mb-1 text-muted">{title}</div>
      {rows.map((r) => (
        <div key={r.name} className="flex items-center gap-2 py-0.5">
          <span className="h-0.5 w-3 rounded" style={{ background: r.color }} />
          <span className="tabular font-semibold text-ink">{r.value}</span>
          <span className="text-ink-2">{r.name}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------

export function RatingChart({ data }: { data: Analysis["rating_history"] }) {
  const rows = data.map((d) => ({ t: new Date(d.at).getTime(), rating: d.rating, name: d.contest_name }));
  const last = rows.at(-1);
  return (
    <ChartCard
      title="Rating history"
      subtitle={last ? `${data.length} rated contests · now ${last.rating}` : "No rated contests yet"}
      table={
        <DataTable
          head={["Date", "Contest", "Rating"]}
          rows={[...data].reverse().map((d) => [dayMonth(d.at) + " " + new Date(d.at).getFullYear(), d.contest_name, d.rating])}
        />
      }
    >
      {rows.length < 2 ? (
        <p className="py-10 text-center text-sm text-ink-2">Not enough rated contests to draw a chart.</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(t: number) => shortDate(new Date(t).toISOString())}
              {...axisProps}
            />
            <YAxis {...niceDomain(rows.map((r) => r.rating))} {...axisProps} width={48} allowDecimals={false} />
            <Tooltip
              cursor={{ stroke: "var(--axis)" }}
              content={({ active, payload }: TipProps) =>
                active && payload?.length ? (
                  <TipBox
                    title={`${payload[0].payload.name} · ${dayMonth(new Date(payload[0].payload.t).toISOString())}`}
                    rows={[{ name: "rating", value: String(payload[0].payload.rating), color: "var(--series-1)" }]}
                  />
                ) : null
              }
            />
            <Line
              type="linear"
              dataKey="rating"
              stroke="var(--series-1)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, stroke: "var(--surface)", strokeWidth: 2 }}
              animationDuration={900} animationEasing="ease-out"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------------------------

export function SolvedByRating({ data }: { data: Analysis["by_rating"] }) {
  const rows = data.map((d) => ({ rating: d.rating, solved: d.solved, unsolved: d.attempted - d.solved }));
  return (
    <ChartCard
      title="Problems by difficulty"
      subtitle="Every problem you've submitted to, by its rating"
      legend={
        <>
          <LegendItem color="var(--series-1)" label="Solved" shape="rect" />
          <LegendItem color="var(--series-2)" label="Not solved" shape="rect" />
        </>
      }
      table={
        <DataTable
          head={["Rating", "Attempted", "Solved", "Solve rate"]}
          rows={data.map((d) => [d.rating, d.attempted, d.solved, `${Math.round((d.solved / d.attempted) * 100)}%`])}
        />
      }
    >
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="rating" {...axisProps} interval="preserveStartEnd" />
          <YAxis {...axisProps} allowDecimals={false} width={44} />
          <Tooltip
            cursor={{ fill: "var(--surface-2)" }}
            content={({ active, payload }: TipProps) =>
              active && payload?.length ? (
                <TipBox
                  title={`Rated ${payload[0].payload.rating}`}
                  rows={[
                    { name: "solved", value: String(payload[0].payload.solved), color: "var(--series-1)" },
                    { name: "not solved", value: String(payload[0].payload.unsolved), color: "var(--series-2)" },
                  ]}
                />
              ) : null
            }
          />
          <Bar dataKey="solved" stackId="a" fill="var(--series-1)" maxBarSize={24} stroke="var(--surface)" strokeWidth={1} animationDuration={900} animationEasing="ease-out" />
          <Bar dataKey="unsolved" stackId="a" fill="var(--series-2)" maxBarSize={24} radius={[4, 4, 0, 0]} stroke="var(--surface)" strokeWidth={1} animationDuration={900} animationEasing="ease-out" />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------------------------

export function WeeklyChart({ data, title = "Solved per week" }: { data: WeekStat[]; title?: string }) {
  const total = data.reduce((s, d) => s + d.solved, 0);
  return (
    <ChartCard
      title={title}
      subtitle={`${total} new problems solved in the last ${data.length} weeks`}
      table={<DataTable head={["Week of", "Solved"]} rows={data.map((d) => [dayMonth(d.week_start), d.solved])} />}
    >
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="week_start" tickFormatter={dayMonth} {...axisProps} interval="preserveStartEnd" minTickGap={24} />
          <YAxis {...axisProps} allowDecimals={false} width={40} />
          <Tooltip
            cursor={{ fill: "var(--surface-2)" }}
            content={({ active, payload }: TipProps) =>
              active && payload?.length ? (
                <TipBox
                  title={`Week of ${dayMonth(payload[0].payload.week_start)}`}
                  rows={[{ name: "solved", value: String(payload[0].payload.solved), color: "var(--series-1)" }]}
                />
              ) : null
            }
          />
          <Bar dataKey="solved" fill="var(--series-1)" maxBarSize={24} radius={[4, 4, 0, 0]} animationDuration={900} animationEasing="ease-out" />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------------------------

/** Estimated level per tag over time, refitted month by month. Up to four tags at once. */
export function TagHistoryChart({ history, initial }: { history: History; initial: string[] }) {
  const available = Object.keys(history.tags).sort();
  // Each selected tag keeps its colour slot, so removing one never repaints the others.
  const [slots, setSlots] = useState<(string | null)[]>(() => {
    const picked = initial.filter((t) => available.includes(t)).slice(0, 4);
    return [0, 1, 2, 3].map((i) => picked[i] ?? null);
  });
  const selected = slots.filter((s): s is string => s !== null);

  const toggle = (tag: string) =>
    setSlots((cur) => {
      const i = cur.indexOf(tag);
      if (i >= 0) return cur.map((s, j) => (j === i ? null : s));
      const free = cur.indexOf(null);
      return free < 0 ? cur : cur.map((s, j) => (j === free ? tag : s));
    });

  const rows = history.dates.map((d, i) => {
    const row: Record<string, number | string | null> = { date: d, overall: history.level[i] };
    for (const t of selected) row[t] = history.tags[t]?.[i] ?? null;
    return row;
  });

  return (
    <ChartCard
      title="Skill over time"
      subtitle="Estimated level per tag, refitted at the end of each month. Pick up to 4 tags."
      legend={
        <>
          <LegendItem color="var(--muted)" label="All tags" shape="line" />
          {slots.map((t, i) => (t ? <LegendItem key={t} color={SERIES[i]} label={tagTitle(t)} shape="line" /> : null))}
        </>
      }
      table={
        <DataTable
          head={["Month", "All tags", ...selected.map(tagTitle)]}
          rows={rows.map((r) => [
            shortDate(String(r.date)),
            int(r.overall as number),
            ...selected.map((t) => int(r[t] as number | null)),
          ])}
        />
      }
    >
      <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Tags to show">
        {available.map((t) => {
          const slot = slots.indexOf(t);
          const on = slot >= 0;
          return (
            <button
              key={t}
              onClick={() => toggle(t)}
              aria-pressed={on}
              disabled={!on && selected.length >= 4}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs transition-colors disabled:opacity-40 ${
                on ? "border-transparent bg-surface-2 text-ink" : "border-line text-ink-2 hover:bg-surface-2"
              }`}
            >
              {on && <span className="size-2 rounded-full" style={{ background: SERIES[slot] }} />}
              {tagTitle(t)}
            </button>
          );
        })}
      </div>
      {rows.length < 2 ? (
        <p className="py-10 text-center text-sm text-ink-2">Not enough history yet.</p>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="date" tickFormatter={shortDate} {...axisProps} minTickGap={24} />
            <YAxis
              {...niceDomain(rows.flatMap((r) => [r.overall as number, ...selected.map((t) => r[t] as number | null)]))}
              {...axisProps}
              width={48}
              allowDecimals={false}
            />
            <Tooltip
              cursor={{ stroke: "var(--axis)" }}
              content={({ active, payload, label }: TipProps) =>
                active && payload?.length ? (
                  <TipBox
                    title={shortDate(String(label))}
                    rows={[
                      { name: "all tags", value: int(payload[0].payload.overall), color: "var(--muted)" },
                      ...slots.flatMap((t, i) =>
                        t ? [{ name: tagTitle(t), value: int(payload[0].payload[t]), color: SERIES[i] }] : [],
                      ),
                    ]}
                  />
                ) : null
              }
            />
            <Line dataKey="overall" stroke="var(--muted)" strokeWidth={2} dot={false} animationDuration={900} animationEasing="ease-out" />
            {slots.map((t, i) =>
              t ? (
                <Line
                  key={t}
                  dataKey={t}
                  stroke={SERIES[i]}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }}
                  animationDuration={900} animationEasing="ease-out"
                />
              ) : null,
            )}
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartCard>
  );
}
