"use client";

import { useId, useState } from "react";
import { cn } from "@/lib/utils";

export interface LegendItem {
  label: string;
  color: string;
  muted?: boolean;
}

/**
 * Title, legend and a "Show as table" switch around a chart. A legend appears for two or more series;
 * the table is the non-visual twin of the chart (every value reachable without hover).
 */
export function ChartFrame({
  title,
  description,
  legend,
  actions,
  table,
  children,
  className,
}: {
  title: string;
  description?: string;
  legend?: LegendItem[];
  actions?: React.ReactNode;
  table?: { columns: string[]; rows: (string | number)[][] };
  children: React.ReactNode;
  className?: string;
}) {
  const [asTable, setAsTable] = useState(false);
  const id = useId();
  return (
    <section aria-labelledby={`${id}-t`} className={className}>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <div className="min-w-0">
          <h3 id={`${id}-t`} className="text-base">
            {title}
          </h3>
          {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
        </div>
        <div className="flex items-center gap-3">
          {legend && legend.length > 1 && (
            <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
              {legend.map((l) => (
                <li key={l.label} className="flex items-center gap-1.5">
                  <span className="h-0.5 w-3.5 rounded-full" style={{ background: l.color, opacity: l.muted ? 0.55 : 1 }} aria-hidden="true" />
                  {l.label}
                </li>
              ))}
            </ul>
          )}
          {actions}
          {table && (
            <button
              type="button"
              aria-pressed={asTable}
              onClick={() => setAsTable((v) => !v)}
              className="rounded-[var(--radius-control)] px-2 py-1 text-xs font-medium text-muted hover:bg-sand hover:text-ink"
            >
              {asTable ? "Show chart" : "Show as table"}
            </button>
          )}
        </div>
      </div>
      <div className="mt-4">
        {asTable && table ? (
          <div className="max-h-80 overflow-auto rounded-[var(--radius-control)] border border-line">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-surface text-xs text-muted">
                <tr>
                  {table.columns.map((c, i) => (
                    <th key={c} scope="col" className={cn("border-b border-line px-3 py-2 font-medium", i > 0 && "text-right")}>
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line [&>tr:nth-child(even)]:bg-sand/40">
                {table.rows.map((r, ri) => (
                  <tr key={ri}>
                    {r.map((cell, i) => (
                      <td key={i} className={cn("num px-3 py-1.5", i > 0 && "text-right")}>
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}
