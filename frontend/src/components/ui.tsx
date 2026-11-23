import type { LucideIcon } from "lucide-react";
import { useState, type CSSProperties, type ReactNode } from "react";
import { Link } from "react-router";
import { useCountUp, useMounted } from "../motion";

export function Section({
  title,
  subtitle,
  action,
  children,
  id,
  icon: Icon,
}: {
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  id?: string;
  icon?: LucideIcon;
}) {
  return (
    <section id={id} className="mt-12 scroll-mt-32">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          {Icon && (
            <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl bg-accent-wash text-accent-ink">
              <Icon size={18} strokeWidth={2.2} aria-hidden />
            </span>
          )}
          <div className="min-w-0">
            <h2 className="text-xl font-semibold tracking-tight text-ink">{title}</h2>
            {subtitle && <p className="mt-0.5 max-w-3xl text-sm text-ink-2">{subtitle}</p>}
          </div>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** A number that counts up when it first appears (and animates between values). */
export function CountUp({ value, format }: { value: number; format?: (n: number) => string }) {
  const v = useCountUp(value);
  return <span className="tabular">{format ? format(v) : Math.round(v).toLocaleString("en-US")}</span>;
}

export function Stat({
  label,
  value,
  note,
  icon: Icon,
  style,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  icon?: LucideIcon;
  style?: CSSProperties;
}) {
  return (
    <div className="card card-hover rise relative overflow-hidden p-4 sm:p-5" style={style}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-medium text-muted">{label}</div>
        {Icon && <Icon size={16} className="text-accent" aria-hidden />}
      </div>
      <div className="mt-1.5 text-3xl font-semibold tracking-tight text-ink">{value}</div>
      {note && <div className="mt-1.5 text-xs leading-snug text-ink-2">{note}</div>}
    </div>
  );
}

const pillTones = {
  neutral: "bg-surface-2 text-ink-2",
  accent: "bg-accent-wash text-accent-ink",
  bad: "bg-surface-2 text-bad",
  good: "bg-surface-2 text-good",
} as const;

export function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: keyof typeof pillTones;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${pillTones[tone]}`}
    >
      {children}
    </span>
  );
}

const buttonBase =
  "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed";
const buttonKinds = {
  primary:
    "bg-gradient text-white shadow-[0_6px_20px_-6px_var(--accent)] hover:shadow-[0_10px_28px_-8px_var(--accent)] hover:brightness-110",
  secondary: "border border-line bg-surface text-ink hover:bg-surface-2",
  ghost: "text-ink-2 hover:bg-surface-2 hover:text-ink",
} as const;

export function Button({
  kind = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { kind?: keyof typeof buttonKinds }) {
  return <button className={`${buttonBase} ${buttonKinds[kind]} ${className}`} {...props} />;
}

export function ButtonLink({
  to,
  kind = "primary",
  children,
}: {
  to: string;
  kind?: keyof typeof buttonKinds;
  children: ReactNode;
}) {
  return (
    <Link to={to} className={`${buttonBase} ${buttonKinds[kind]}`}>
      {children}
    </Link>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-ink-2" role="status">
      <span className="size-4 animate-spin rounded-full border-2 border-line border-t-accent" />
      {label}
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function Notice({
  tone = "info",
  children,
}: {
  tone?: "info" | "error";
  children: ReactNode;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`card rise flex items-start gap-3 p-4 text-sm ${tone === "error" ? "text-bad" : "text-ink-2"}`}
    >
      <span
        aria-hidden
        className={`grid size-5 shrink-0 place-items-center rounded-full text-xs font-bold ${
          tone === "error" ? "bg-surface-2 text-bad" : "bg-accent-wash text-accent-ink"
        }`}
      >
        {tone === "error" ? "!" : "i"}
      </span>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/** Circular progress gauge; animates from empty on first render. */
export function Ring({
  value,
  size = 56,
  stroke = 6,
  children,
  label,
}: {
  value: number;
  size?: number;
  stroke?: number;
  children?: ReactNode;
  label: string;
}) {
  const mounted = useMounted();
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value));
  const id = `ring-${label.replace(/\W/g, "")}`;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={label}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--accent-2)" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--accent-wash)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={`url(#${id})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={mounted ? c * (1 - v) : c}
          style={{ transition: "stroke-dashoffset 900ms cubic-bezier(0.2, 0.7, 0.2, 1)" }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">{children}</div>
    </div>
  );
}

/** Card wrapper for a chart with an optional table view, so no value is hover-only. */
export function ChartCard({
  title,
  subtitle,
  legend,
  table,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  legend?: ReactNode;
  table?: ReactNode;
  children: ReactNode;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <div className="card rise min-w-0 p-4 sm:p-5">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-ink-2">{subtitle}</p>}
        </div>
        {table && (
          <div className="flex shrink-0 rounded-lg bg-surface-2 p-0.5 text-xs font-medium" role="group" aria-label="View">
            {(["Chart", "Table"] as const).map((v) => {
              const on = (v === "Table") === showTable;
              return (
                <button
                  key={v}
                  onClick={() => setShowTable(v === "Table")}
                  aria-pressed={on}
                  className={`rounded-md px-2 py-0.5 transition-colors ${on ? "bg-surface text-ink shadow-sm" : "text-ink-2 hover:text-ink"}`}
                >
                  {v}
                </button>
              );
            })}
          </div>
        )}
      </div>
      {legend && !showTable && <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1">{legend}</div>}
      {showTable ? <div className="max-h-96 overflow-auto">{table}</div> : children}
    </div>
  );
}

export function LegendItem({
  color,
  label,
  shape = "dot",
}: {
  color: string;
  label: string;
  shape?: "dot" | "line" | "rect";
}) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
      {shape === "line" ? (
        <span className="h-0.5 w-3.5 rounded" style={{ background: color }} />
      ) : (
        <span
          className={shape === "dot" ? "size-2.5 rounded-full" : "size-2.5 rounded-sm"}
          style={{ background: color }}
        />
      )}
      {label}
    </span>
  );
}

export function DataTable({
  head,
  rows,
}: {
  head: string[];
  rows: (string | number)[][];
}) {
  return (
    <table className="tabular w-full text-left text-xs">
      <thead className="sticky top-0 bg-surface text-muted">
        <tr>
          {head.map((h) => (
            <th key={h} className="border-b border-line py-1.5 pr-3 font-medium">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="text-ink">
        {rows.map((r, i) => (
          <tr key={i} className="border-b border-line last:border-0">
            {r.map((c, j) => (
              <td key={j} className="py-1.5 pr-3">
                {c}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
