import { useEffect, useState, type ReactNode } from "react";
import { useWidth } from "../useWidth";

export interface ForestPoint {
  value: number;
  low: number;
  high: number;
  color: string;
}

export interface ForestRow {
  id: string;
  label: string;
  points: ForestPoint[];
  valueText?: string;
  tooltip: ReactNode;
}

/**
 * Forest plot: one row per tag, a dot for the estimate and a whisker for the 90% interval,
 * on a shared axis centred at zero ("your average tag"). Built in plain SVG for full control.
 */
export function Forest({
  rows,
  ariaLabel,
  maxDomain = 500,
  zeroLabel = "avg",
}: {
  rows: ForestRow[];
  ariaLabel: string;
  maxDomain?: number;
  zeroLabel?: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  // Start the entrance animation one frame after the SVG first has a width.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    if (width <= 0 || mounted) return;
    const raf = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(raf);
  }, [width, mounted]);

  const multi = rows.some((r) => r.points.length > 1);
  const rowH = multi ? 34 : 28;
  const top = 6;
  const axisH = 22;
  const height = top + rows.length * rowH + axisH;
  const labelW = Math.min(170, Math.max(96, width * 0.34));
  const valueW = rows.some((r) => r.valueText) ? 44 : 8;
  const maxChars = Math.max(8, Math.floor(labelW / 7));
  const x0 = labelW + 8;
  const x1 = Math.max(x0 + 40, width - valueW - 8);

  // Axis covers every interval, always includes ±200 around zero, and is rounded to 100s.
  const all = rows.flatMap((r) => r.points.flatMap((p) => [p.low, p.high]));
  const lo = -Math.min(maxDomain, Math.ceil(Math.max(200, -Math.min(0, ...all)) / 100) * 100);
  const hi = Math.min(maxDomain, Math.ceil(Math.max(200, ...all) / 100) * 100);
  const span = hi - lo;
  const sx = (v: number) => x0 + ((Math.max(lo, Math.min(hi, v)) - lo) / span) * (x1 - x0);
  const step = span <= 600 ? 100 : span <= 1200 ? 200 : span <= 3000 ? 500 : 1000;
  const ticks: number[] = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) ticks.push(t);

  const hovered = hover != null ? rows[hover] : null;

  return (
    <div ref={ref} className="relative w-full" onPointerLeave={() => setHover(null)}>
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={ariaLabel} className="block">
          {ticks.map((t) => (
            <g key={t}>
              <line
                x1={sx(t)}
                x2={sx(t)}
                y1={top}
                y2={top + rows.length * rowH}
                stroke={t === 0 ? "var(--axis)" : "var(--grid)"}
                strokeWidth={1}
              />
              <text
                x={sx(t)}
                y={height - 6}
                textAnchor="middle"
                fontSize={11}
                fill="var(--muted)"
                className="tabular"
              >
                {t === 0 ? zeroLabel : t > 0 ? `+${t}` : `−${-t}`}
              </text>
            </g>
          ))}
          {rows.map((r, i) => {
            const cy = top + i * rowH + rowH / 2;
            const active = hover === i;
            return (
              <g
                key={r.id}
                tabIndex={0}
                role="listitem"
                aria-label={`${r.label}: ${r.valueText ?? ""}`}
                onPointerEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                style={{ outline: "none" }}
              >
                <rect
                  x={0}
                  y={cy - rowH / 2}
                  width={width}
                  height={rowH}
                  fill={active ? "var(--surface-2)" : "transparent"}
                  rx={6}
                />
                <text
                  x={labelW}
                  y={cy + 4}
                  textAnchor="end"
                  fontSize={12.5}
                  fill="var(--ink)"
                  fontWeight={active ? 600 : 400}
                >
                  {r.label.length > maxChars ? `${r.label.slice(0, maxChars - 1)}…` : r.label}
                </text>
                {r.points.map((p, j) => {
                  const py = r.points.length > 1 ? cy + (j === 0 ? -6 : 6) : cy;
                  return (
                    <g key={j}>
                      <line
                        x1={sx(p.low)}
                        x2={sx(p.high)}
                        y1={py}
                        y2={py}
                        stroke={p.color}
                        strokeOpacity={mounted ? 0.45 : 0}
                        strokeWidth={2}
                        strokeLinecap="round"
                        style={{ transition: `stroke-opacity 500ms ease ${400 + i * 35}ms` }}
                      />
                      {/* The dot slides in from "average" on first render. */}
                      <g
                        style={{
                          transform: `translate(${mounted ? sx(p.value) : sx(0)}px, ${py}px)`,
                          transition: `transform 800ms cubic-bezier(0.2, 0.7, 0.2, 1) ${i * 35}ms`,
                        }}
                      >
                        <circle
                          r={active ? 6.5 : 5}
                          fill={p.color}
                          stroke="var(--surface)"
                          strokeWidth={2}
                          style={{ transition: "r 150ms ease" }}
                        />
                      </g>
                    </g>
                  );
                })}
                {r.valueText && (
                  <text
                    x={width - 4}
                    y={cy + 4}
                    textAnchor="end"
                    fontSize={12}
                    fill="var(--ink-2)"
                    className="tabular"
                  >
                    {r.valueText}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      )}
      {hovered && hover != null && (
        <div
          className="card pointer-events-none absolute z-10 w-64 p-3 text-xs"
          style={{
            top: Math.min(top + (hover + 1) * rowH + 4, Math.max(0, height - 150)),
            left: Math.max(0, Math.min(labelW - 40, width - 264)),
          }}
        >
          {hovered.tooltip}
        </div>
      )}
    </div>
  );
}
