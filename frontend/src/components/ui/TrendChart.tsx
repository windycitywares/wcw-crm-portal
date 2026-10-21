"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { Icon } from "./Icon";
import { Pill } from "./Pill";

interface TrendPoint {
  date: string;
  count: number;
  value: number;
}

/**
 * Interactive trend chart: an area line chart with a hover tooltip.
 * Pure SVG — no charting dependency. Hover a point to see its value.
 */
export function TrendChart({ points, height = 120, showValue = false }: { points: TrendPoint[]; height?: number; showValue?: boolean }) {
  const [hover, setHover] = useState<number | null>(null);
  const hasData = points.some((p) => p.count > 0);

  const maxCount = Math.max(1, ...points.map((p) => p.count));
  const maxValue = Math.max(1, ...points.map((p) => p.value));
  const padding = { top: 16, right: 10, bottom: 30, left: 36 };
  const width = points.length * 24 + 60;

  const series = useMemo(() => {
    const xs = points.map((_, i) => padding.left + (i / Math.max(points.length - 1, 1)) * (width - padding.left - padding.right));
    const ys = points.map((p) => padding.top + height - (p.count / maxCount) * (height - padding.top - padding.bottom));
    return points.map((p, i) => ({ x: xs[i], y: ys[i], p }));
  }, [points, maxCount, width, height, padding]);

  const areaPoints = series.map((s) => `${s.x},${s.y}`).join(" ");
  const baselineY = padding.top + height;

  return (
    <div className="w-full">
      <div className="relative" style={{ width, height: height + padding.top + padding.bottom }}>
        <svg width={width} height={height + padding.top + padding.bottom} className="w-full h-auto block" role="img" aria-label="Orders trend">
          <defs>
            <linearGradient id="trend-gradient" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#2563eb" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#2563eb" stopOpacity="0" />
            </linearGradient>
          </defs>
          {/* Area fill */}
          {hasData && (
            <path
              d={`M${padding.left},${baselineY} L${areaPoints} L${series[series.length - 1]?.x ?? padding.left},${baselineY} Z`}
              fill="url(#trend-gradient)" />
          )}
          {/* Line */}
          {hasData && (
            <path
              d={series.map((s, i) => (i === 0 ? `M${s.x},${s.y}` : `L${s.x},${s.y}`)).join(" ")}
              fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          )}
          {/* Points + hover */}
          {series.map((s, i) => {
            const isHover = hover === i;
            const p = s.p;
            return (
              <circle
                key={i}
                cx={s.x}
                cy={s.y}
                r={isHover ? 5 : 3}
                fill={isHover ? "#2563eb" : "#ffffff"}
                stroke="#2563eb"
                strokeWidth={2}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
                className="cursor-pointer transition-all duration-150"
              />
            );
          })}
          {/* X axis labels */}
          {points.map((p, i) => (
            <text key={i} x={series[i]?.x ?? padding.left} y={baselineY + 20} textAnchor="middle" fontSize="11" fill="#6b7280">
              {new Date(p.date).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
            </text>
          ))}
          {/* Y axis labels */}
          <text x={padding.left - 8} y={padding.top} textAnchor="end" fontSize="11" fill="#6b7280">{maxCount.toLocaleString()}</text>
          <text x={padding.left - 8} y={baselineY} textAnchor="end" fontSize="11" fill="#6b7280">0</text>
        </svg>
        {/* Tooltip */}
        {hover !== null && hasData && series[hover] && (
          <div className="absolute left-[calc(50%-6rem)] top-0 z-20 flex items-center gap-2 rounded-[var(--radius-card)] border border-line bg-surface px-3 py-2 text-sm shadow-lg pointer-events-none">
            <Icon name="calendar" className="size-4 text-muted" />
            <span className="font-medium">{new Date(points[hover].date).toLocaleDateString()}</span>
            <span className="text-muted">{points[hover].count.toLocaleString()} orders</span>
          </div>
        )}
      </div>
      {showValue && (
        <div className="mt-2 flex items-center gap-2 text-xs text-muted">
          <Icon name="truck" className="size-3" />
          <span>Peak value ${maxValue.toLocaleString()}</span>
        </div>
      )}
    </div>
  );
}
