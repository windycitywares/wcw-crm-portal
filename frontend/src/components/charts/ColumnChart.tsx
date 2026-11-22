"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { dayLabel, labelIndices, niceTicks } from "./format";
import { useWidth } from "./useWidth";

interface Props {
  x: string[];
  values: number[];
  yFormat?: (n: number) => string;
  xFormat?: (x: string, long?: boolean) => string;
  /** What the values are called in the tooltip ("Orders"). */
  seriesLabel: string;
  label: string;
  height?: number;
  color?: string;
  loading?: boolean;
  className?: string;
}

const M = { top: 12, right: 8, bottom: 26 };

/** Vertical bars over time (orders per day, signups…). Bars are capped at 24px with 2px gaps. */
export function ColumnChart({
  x,
  values,
  yFormat = String,
  xFormat = (v, long) => dayLabel(v, long ? "long" : "short"),
  seriesLabel,
  label,
  height = 200,
  color = "var(--color-accent)",
  loading,
  className,
}: Props) {
  const [ref, w] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const { ticks, yMax } = useMemo(() => {
    const t = niceTicks(0, Math.max(...values, 1), 3);
    return { ticks: t, yMax: t[t.length - 1] || 1 };
  }, [values]);
  const left = 8 + Math.max(...ticks.map((t) => yFormat(t).length)) * 7 + 6;
  const n = x.length;
  const plotW = Math.max(10, w - left - M.right);
  const plotH = height - M.top - M.bottom;
  const slot = n ? plotW / n : plotW;
  const barW = Math.max(2, Math.min(24, slot - 2));
  const bx = (i: number) => left + i * slot + (slot - barW) / 2;
  const py = (v: number) => M.top + plotH - (v / yMax) * plotH;
  const idx = labelIndices(n, w < 480 ? 4 : 7);

  if (n === 0) {
    return (
      <div ref={ref} className={cn("grid place-items-center text-sm text-muted", className)} style={{ height }}>
        No data for this period yet.
      </div>
    );
  }
  return (
    <div
      ref={ref}
      className={cn("relative transition-opacity duration-200", loading && "opacity-50", className)}
      style={{ height }}
      tabIndex={0}
      role="group"
      aria-label={`${label}. Use the arrow keys to read each bar.`}
      onFocus={() => setActive((a) => a ?? n - 1)}
      onBlur={() => setActive(null)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") setActive((a) => Math.min(n - 1, (a ?? -1) + 1));
        else if (e.key === "ArrowLeft") setActive((a) => Math.max(0, (a ?? n) - 1));
        else return;
        e.preventDefault();
      }}
    >
      <svg width={w} height={height} role="img" aria-label={label} className="block overflow-visible">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={left} x2={w - M.right} y1={py(t)} y2={py(t)} stroke={t === 0 ? "var(--color-line)" : "color-mix(in oklab, var(--color-line) 55%, transparent)"} />
            <text x={left - 8} y={py(t)} dy="0.32em" textAnchor="end" fontSize={11} fill="var(--color-muted)" className="num">
              {yFormat(t)}
            </text>
          </g>
        ))}
        {values.map((v, i) => {
          const h = Math.max(v > 0 ? 2 : 0, (v / yMax) * plotH);
          const r = Math.min(4, barW / 2, h);
          const X = bx(i);
          const Y = py(0) - h;
          return (
            <g key={x[i]}>
              {/* 4px rounded data end, square at the baseline */}
              <path
                d={h > 0 ? `M${X} ${Y + h} V${Y + r} Q${X} ${Y} ${X + r} ${Y} H${X + barW - r} Q${X + barW} ${Y} ${X + barW} ${Y + r} V${Y + h} Z` : ""}
                fill={color}
                opacity={active == null || active === i ? 1 : 0.55}
              />
              {/* full-height hit area, wider than the bar */}
              <rect x={left + i * slot} y={M.top} width={slot} height={plotH} fill="transparent" className="viz-hit" onPointerEnter={() => setActive(i)} onPointerLeave={() => setActive(null)} />
            </g>
          );
        })}
        {idx.map((i) => (
          <text key={i} x={left + i * slot + slot / 2} y={height - 6} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"} fontSize={11} fill="var(--color-muted)">
            {xFormat(x[i])}
          </text>
        ))}
      </svg>
      {active != null && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute top-1 z-10 rounded-[var(--radius-control)] border border-line bg-surface px-3 py-2 text-xs shadow-[0_8px_24px_-12px_rgb(0_0_0/0.35)]"
          style={bx(active) > w * 0.6 ? { right: w - bx(active) + 8 } : { left: bx(active) + barW + 8 }}
        >
          <p className="font-medium text-muted">{xFormat(x[active], true)}</p>
          <p>
            <span className="num text-sm font-semibold text-ink">{yFormat(values[active])}</span> <span className="text-muted">{seriesLabel}</span>
          </p>
        </div>
      )}
    </div>
  );
}
