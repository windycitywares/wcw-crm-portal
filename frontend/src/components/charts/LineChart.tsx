"use client";

import { useId, useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { smoothPath } from "./curve";
import { dayLabel, labelIndices, niceTicks, seriesColor } from "./format";
import { useWidth } from "./useWidth";

export interface LineSeries {
  key: string;
  label: string;
  values: (number | null)[];
  /** CSS colour; defaults to the theme accent (one series) or the categorical palette. */
  color?: string;
  /** Drawn light and thin — used for "previous period" comparison lines. */
  muted?: boolean;
}

interface Props {
  /** One label per point: an ISO date ("2026-10-14") or any text. */
  x: string[];
  series: LineSeries[];
  height?: number;
  yFormat?: (n: number) => string;
  xFormat?: (x: string, long?: boolean) => string;
  /** Fill under the line (default: on for a single series). */
  area?: boolean;
  /** Accessible description of what is plotted. */
  label: string;
  loading?: boolean;
  className?: string;
}

const M = { top: 14, right: 18, bottom: 26, left: 8 };

/** Colour for series i among the non-muted ones. */
function colorFor(s: LineSeries, i: number, single: boolean) {
  return s.color ?? (single ? "var(--color-accent)" : seriesColor(i));
}

/**
 * Time-series line/area chart drawn in SVG: 2px lines, hairline grid, an end dot on each line, and a
 * crosshair + tooltip listing every series at the hovered point (arrow keys work too). The same data is
 * available as a table through <ChartFrame table={…}>.
 */
export function LineChart({
  x,
  series,
  height = 260,
  yFormat = (n) => String(n),
  xFormat = (v, long) => dayLabel(v, long ? "long" : "short"),
  area,
  label,
  loading,
  className,
}: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const gid = useId().replace(/:/g, "");
  const live = series.filter((s) => !s.muted);
  const single = live.length === 1;
  const showArea = area ?? single;

  const { ticks, yMax } = useMemo(() => {
    let max = 0;
    for (const s of series) for (const v of s.values) if (v != null && v > max) max = v;
    const t = niceTicks(0, max || 1, 4);
    return { ticks: t, yMax: t[t.length - 1] || 1 };
  }, [series]);

  // Left margin grows with the widest tick label (≈7px per character at 11px).
  const left = M.left + Math.max(...ticks.map((t) => yFormat(t).length)) * 7 + 6;
  const w = width;
  const plotW = Math.max(10, w - left - M.right);
  const plotH = height - M.top - M.bottom;
  const n = x.length;
  const px = (i: number) => left + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const py = (v: number) => M.top + plotH - (v / yMax) * plotH;

  if (n === 0) {
    return (
      <div ref={ref} className={cn("grid place-items-center text-sm text-muted", className)} style={{ height }}>
        No data for this period yet.
      </div>
    );
  }

  const idx = labelIndices(n, w < 480 ? 4 : w < 760 ? 6 : 8);

  function path(values: (number | null)[], close: boolean) {
    let d = "";
    let run: [number, number][] = [];
    const flush = () => {
      if (run.length === 0) return;
      d += (d ? " " : "") + smoothPath(run);
      if (close) d += ` L${run[run.length - 1][0].toFixed(1)} ${py(0).toFixed(1)} L${run[0][0].toFixed(1)} ${py(0).toFixed(1)} Z`;
      run = [];
    };
    values.forEach((v, i) => {
      if (v == null) flush();
      else run.push([px(i), py(v)]);
    });
    flush();
    return d;
  }

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = e.clientX - rect.left;
    setActive(Math.max(0, Math.min(n - 1, Math.round((rel / plotW) * (n - 1)))));
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowRight") setActive((a) => Math.min(n - 1, (a ?? -1) + 1));
    else if (e.key === "ArrowLeft") setActive((a) => Math.max(0, (a ?? n) - 1));
    else if (e.key === "Home") setActive(0);
    else if (e.key === "End") setActive(n - 1);
    else if (e.key === "Escape") setActive(null);
    else return;
    e.preventDefault();
  }

  const tipRight = active != null && px(active) > w * 0.6;

  return (
    <div
      ref={ref}
      className={cn("relative transition-opacity duration-200", loading && "opacity-50", className)}
      style={{ height }}
      tabIndex={0}
      role="group"
      aria-label={`${label}. Use the arrow keys to read each point.`}
      onKeyDown={onKey}
      onFocus={() => setActive((a) => a ?? n - 1)}
      onBlur={() => setActive(null)}
    >
      <svg width={w} height={height} role="img" aria-label={label} className="block overflow-visible">
        {showArea && (
          <defs>
            {/* soft fill under each line, fading towards the axis */}
            {live.map((s, i) => (
              <linearGradient key={s.key} id={`${gid}-${i}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={colorFor(s, i, single)} stopOpacity={0.24} />
                <stop offset="100%" stopColor={colorFor(s, i, single)} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
        )}
        {/* grid + y labels */}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={left} x2={w - M.right} y1={py(t)} y2={py(t)} stroke={t === 0 ? "var(--color-line)" : "color-mix(in oklab, var(--color-line) 55%, transparent)"} strokeWidth={1} />
            <text x={left - 8} y={py(t)} dy="0.32em" textAnchor="end" fontSize={11} fill="var(--color-muted)" className="num">
              {yFormat(t)}
            </text>
          </g>
        ))}
        {/* x labels */}
        {idx.map((i) => (
          <text key={i} x={px(i)} y={height - 6} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"} fontSize={11} fill="var(--color-muted)">
            {xFormat(x[i])}
          </text>
        ))}

        {/* areas first so lines sit on top */}
        {showArea &&
          live.map((s, i) => (
            <path key={`a-${s.key}`} d={path(s.values, true)} fill={`url(#${gid}-${i})`} />
          ))}
        {series.map((s) => {
          const li = live.indexOf(s);
          const c = s.muted ? "var(--color-muted)" : colorFor(s, li, single);
          return (
            <path
              key={s.key}
              d={path(s.values, false)}
              fill="none"
              stroke={c}
              strokeOpacity={s.muted ? 0.55 : 1}
              strokeWidth={s.muted ? 1.5 : 2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          );
        })}

        {/* end dots (2px surface ring) */}
        {live.map((s, i) => {
          let last = s.values.length - 1;
          while (last >= 0 && s.values[last] == null) last--;
          if (last < 0) return null;
          return <circle key={`e-${s.key}`} cx={px(last)} cy={py(s.values[last] as number)} r={4} fill={colorFor(s, i, single)} stroke="var(--color-surface)" strokeWidth={2} />;
        })}

        {/* crosshair */}
        {active != null && (
          <g aria-hidden="true">
            <line x1={px(active)} x2={px(active)} y1={M.top} y2={M.top + plotH} stroke="var(--color-ink)" strokeOpacity={0.35} strokeWidth={1} />
            {series.map((s) => {
              const v = s.values[active];
              if (v == null) return null;
              const li = live.indexOf(s);
              const c = s.muted ? "var(--color-muted)" : colorFor(s, li, single);
              return <circle key={s.key} cx={px(active)} cy={py(v)} r={4} fill={c} stroke="var(--color-surface)" strokeWidth={2} />;
            })}
          </g>
        )}
        {/* hit layer (much larger than the marks) */}
        <rect x={left} y={M.top} width={plotW} height={plotH} fill="transparent" className="viz-hit" onPointerMove={onMove} onPointerLeave={() => setActive(null)} />
      </svg>

      {active != null && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute top-2 z-10 min-w-40 rounded-[var(--radius-control)] border border-line bg-surface px-3 py-2 text-xs shadow-[0_8px_24px_-12px_rgb(0_0_0/0.35)]"
          style={tipRight ? { right: w - px(active) + 12 } : { left: px(active) + 12 }}
        >
          <p className="mb-1 font-medium text-muted">{xFormat(x[active], true)}</p>
          <ul className="space-y-0.5">
            {series.map((s) => {
              const v = s.values[active];
              const li = live.indexOf(s);
              const c = s.muted ? "var(--color-muted)" : colorFor(s, li, single);
              return (
                <li key={s.key} className="flex items-center gap-2">
                  <span className="h-0.5 w-3 shrink-0 rounded-full" style={{ background: c, opacity: s.muted ? 0.55 : 1 }} />
                  <span className="num text-sm font-semibold text-ink">{v == null ? "—" : yFormat(v)}</span>
                  <span className="text-muted">{s.label}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Rows for <ChartFrame table={…}> from the same data the chart draws. */
export function lineTable(
  x: string[],
  series: LineSeries[],
  yFormat: (n: number) => string = String,
  xFormat: (x: string, long?: boolean) => string = (v) => dayLabel(v, "long"),
) {
  return {
    columns: ["Date", ...series.map((s) => s.label)],
    rows: x.map((d, i) => [xFormat(d, true), ...series.map((s) => (s.values[i] == null ? "—" : yFormat(s.values[i] as number)))]),
  };
}
