"use client";

import { cn } from "@/lib/utils";
import { Icon } from "./Icon";

/** Metric card: headline number, label, optional trend and icon. No link wrapper - pages wrap as needed. */
export function StatCard({
  title,
  value,
  subtitle,
  icon,
  trend,
}: {
  title: string;
  value: React.ReactNode;
  subtitle?: string;
  icon?: string;
  trend?: { label: string; delta: number; up: boolean };
}) {
  return (
    <div className="rounded-[var(--radius-card)] border border-line bg-surface p-5 shadow-sm hover:shadow-md transition-all hover:border-accent/40 cursor-pointer">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-xs text-muted font-medium">{title}</p>
          <div className="mt-1">
            <span className="text-[1.5rem] font-semibold text-ink tabular-nums">{value}</span>
          </div>
          {subtitle && <p className="mt-1 text-xs text-muted">{subtitle}</p>}
        </div>
        {icon && (
          <div className="ml-3 grid size-8 place-items-center rounded-full bg-accent-soft">
            <Icon name={icon as any} className="size-5 text-accent-strong" />
          </div>
        )}
      </div>
      {trend && (
        <div className="mt-3 flex items-center gap-1.5 text-xs font-medium">
          <span className={trend.up ? "text-[#1d6b38]" : "text-[#a12a1e]"}>
            {trend.delta !== undefined && <span className="size-1.5 rounded-full" style={{ background: trend.up ? "#1d6b38" : "#a12a1e" }} />}
            {trend.label}
          </span>
        </div>
      )}
    </div>
  );
}
