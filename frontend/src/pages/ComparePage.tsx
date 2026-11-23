import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { api } from "../api";
import { Forest, type ForestRow } from "../charts/Forest";
import { GitCompareArrows } from "lucide-react";
import { Button, ChartCard, DataTable, LegendItem, Notice, Skeleton, Spinner } from "../components/ui";
import { delay } from "../motion";
import { int, signed, tagTitle } from "../format";
import { useSyncedHandle } from "../hooks";

const A_COLOR = "var(--series-1)";
const B_COLOR = "var(--series-2)";

export function ComparePage() {
  const [params, setParams] = useSearchParams();
  const a = params.get("a") ?? "";
  const b = params.get("b") ?? "";
  const [draftA, setDraftA] = useState(a);
  const [draftB, setDraftB] = useState(b);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (draftA.trim() && draftB.trim()) setParams({ a: draftA.trim(), b: draftB.trim() });
  };

  return (
    <div>
      <div className="flex items-center gap-3">
        <span className="bg-gradient grid size-11 place-items-center rounded-2xl text-white shadow-[0_8px_20px_-8px_var(--accent)]">
          <GitCompareArrows size={20} aria-hidden />
        </span>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">Compare two handles</h1>
          <p className="mt-0.5 text-sm text-ink-2">
            Tag levels side by side, for example you and a friend, or you and someone a rank above you.
          </p>
        </div>
      </div>
      <form onSubmit={submit} className="card mt-6 flex flex-wrap items-end gap-3 p-4">
        {[
          { id: "a", label: "First handle", value: draftA, set: setDraftA },
          { id: "b", label: "Second handle", value: draftB, set: setDraftB },
        ].map((f) => (
          <label key={f.id} className="min-w-0 flex-1 basis-40 text-xs text-ink-2">
            {f.label}
            <input
              value={f.value}
              onChange={(e) => f.set(e.target.value)}
              spellCheck={false}
              placeholder="handle"
              className="mt-1 block w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:shadow-[0_0_0_4px_var(--accent-wash)] focus:outline-none"
            />
          </label>
        ))}
        <Button type="submit">
          <GitCompareArrows size={16} aria-hidden /> Compare
        </Button>
      </form>
      {a && b && <Comparison a={a} b={b} />}
    </div>
  );
}

function Comparison({ a, b }: { a: string; b: string }) {
  const sa = useSyncedHandle(a);
  const sb = useSyncedHandle(b);
  const ready = sa.ready && sb.ready;
  const cmp = useQuery({
    queryKey: ["compare", a.toLowerCase(), b.toLowerCase(), sa.status?.last_synced_at, sb.status?.last_synced_at],
    queryFn: () => api.compare(a, b),
    enabled: ready,
  });

  const errors = [sa.error?.message, sb.error?.message, sa.status?.sync_state === "error" && `${a}: ${sa.status.sync_error}`, sb.status?.sync_state === "error" && `${b}: ${sb.status.sync_error}`, cmp.error?.message].filter(Boolean);
  if (errors.length)
    return (
      <div className="mt-6">
        <Notice tone="error">{errors[0]}</Notice>
      </div>
    );
  if (!cmp.data)
    return (
      <div className="mt-6 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
        <Skeleton className="h-96" />
        <p className="text-center text-sm text-ink-2">
          <Spinner label="Syncing both handles from Codeforces…" />
        </p>
      </div>
    );

  const { a: A, b: B } = cmp.data;
  const byTag = new Map(B.skills.map((s) => [s.tag, s]));
  // Tags both users have tried; compare absolute levels (level + offset), centred on A's level.
  const common = A.skills
    .filter((s) => s.attempts >= 3 && (byTag.get(s.tag)?.attempts ?? 0) >= 3)
    .map((s) => ({ a: s, b: byTag.get(s.tag)! }))
    .sort((x, y) => x.b.level - x.a.level - (y.b.level - y.a.level));

  const base = A.level;
  const rows: ForestRow[] = common.map(({ a: x, b: y }) => ({
    id: x.tag,
    label: tagTitle(x.tag),
    valueText: signed(y.level - x.level),
    points: [
      { value: x.level - base, low: x.ci_low + x.level - x.delta - base, high: x.ci_high + x.level - x.delta - base, color: A_COLOR },
      { value: y.level - base, low: y.ci_low + y.level - y.delta - base, high: y.ci_high + y.level - y.delta - base, color: B_COLOR },
    ],
    tooltip: (
      <div className="space-y-1">
        <div className="font-semibold text-ink">{tagTitle(x.tag)}</div>
        <div className="tabular text-ink"><b>{int(x.level)}</b> <span className="text-ink-2">{A.handle.handle}</span></div>
        <div className="tabular text-ink"><b>{int(y.level)}</b> <span className="text-ink-2">{B.handle.handle}</span></div>
      </div>
    ),
  }));

  return (
    <div className="mt-6 space-y-4">
      <div className="grid grid-cols-2 gap-3">
        {[A, B].map((side, i) => (
          <div key={i} className="card card-hover rise flex items-center gap-3 p-4" style={delay(i * 80)}>
            <div className="relative shrink-0">
              {side.handle.avatar ? (
                <img src={side.handle.avatar} alt="" className="size-11 rounded-xl object-cover" />
              ) : (
                <div className="size-11 rounded-xl bg-surface-2" />
              )}
              <span
                className="absolute -bottom-1 -right-1 size-3.5 rounded-full ring-2 ring-[var(--surface)]"
                style={{ background: i ? B_COLOR : A_COLOR }}
              />
            </div>
            <div className="min-w-0">
              <div className="truncate font-semibold text-ink">{side.handle.handle}</div>
              <div className="tabular text-xs text-ink-2">
                rating {side.handle.rating ?? "—"} · effective level {int(side.level)}
              </div>
            </div>
          </div>
        ))}
      </div>
      <ChartCard
        title="Tag levels"
        subtitle={`Axis is relative to ${A.handle.handle}'s effective level (${int(base)}). Right-hand numbers are ${B.handle.handle} minus ${A.handle.handle}. Only tags both have tried at least 3 times.`}
        legend={
          <>
            <LegendItem color={A_COLOR} label={A.handle.handle} />
            <LegendItem color={B_COLOR} label={B.handle.handle} />
          </>
        }
        table={
          <DataTable
            head={["Tag", A.handle.handle, B.handle.handle, "Difference"]}
            rows={common.map(({ a: x, b: y }) => [tagTitle(x.tag), int(x.level), int(y.level), signed(y.level - x.level)])}
          />
        }
      >
        {rows.length ? (
          <Forest rows={rows} ariaLabel="Tag levels for both handles" maxDomain={4000} zeroLabel="0" />
        ) : (
          <p className="py-8 text-center text-sm text-ink-2">These handles have no tags in common with enough attempts.</p>
        )}
      </ChartCard>
    </div>
  );
}
