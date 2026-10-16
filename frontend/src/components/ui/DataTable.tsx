"use client";

import { cn } from "@/lib/utils";
import { Icon } from "./Icon";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  cell: (row: T, index: number) => React.ReactNode;
  align?: "left" | "right" | "center";
  /** Hide this column below a breakpoint (the key info stays in the first column). */
  hide?: "sm" | "md" | "lg";
  /** Makes the header a sort button; `onSort` gets this key. */
  sort?: string;
  className?: string;
}

const HIDE = { sm: "hidden sm:table-cell", md: "hidden md:table-cell", lg: "hidden lg:table-cell" } as const;
const ALIGN = { left: "text-left", right: "text-right", center: "text-center" } as const;

/**
 * Standard admin table. `rows === null` shows skeleton rows on first load; while refetching, pass
 * `loading` to dim the existing rows instead of flashing them away.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  empty,
  loading,
  sort,
  onSort,
  className,
  rowClassName,
}: {
  columns: Column<T>[];
  rows: T[] | null;
  rowKey: (row: T) => string | number;
  /** Read by screen readers; not shown. */
  caption: string;
  empty?: React.ReactNode;
  loading?: boolean;
  sort?: { key: string; dir: "asc" | "desc" };
  onSort?: (key: string) => void;
  className?: string;
  rowClassName?: (row: T) => string | undefined;
}) {
  return (
    <div className={cn("relative overflow-x-auto", className)}>
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="border-b border-line text-xs text-muted">
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.sort;
              return (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={c.sort && active ? (sort?.dir === "asc" ? "ascending" : "descending") : undefined}
                  className={cn("whitespace-nowrap px-4 py-2.5 font-medium", ALIGN[c.align ?? "left"], c.hide && HIDE[c.hide], c.className)}
                >
                  {c.sort && onSort ? (
                    <button type="button" onClick={() => onSort(c.sort as string)} className={cn("inline-flex items-center gap-1 hover:text-ink", active && "text-ink")}>
                      {c.header}
                      <Icon name={active && sort?.dir === "asc" ? "arrowUp" : "arrowDown"} className={cn("size-3", !active && "opacity-30")} strokeWidth={2} />
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className={cn("divide-y divide-line transition-opacity duration-200", loading && "opacity-50")}>
          {rows === null
            ? Array.from({ length: 6 }, (_, i) => (
                <tr key={i} aria-hidden="true">
                  {columns.map((c) => (
                    <td key={c.key} className={cn("px-4 py-3.5", c.hide && HIDE[c.hide])}>
                      <div className="skeleton h-4 w-3/4" />
                    </td>
                  ))}
                </tr>
              ))
            : rows.map((row, i) => (
                <tr key={rowKey(row)} className={cn("hover:bg-canvas/70", rowClassName?.(row))}>
                  {columns.map((c) => (
                    <td key={c.key} className={cn("px-4 py-3 align-middle", ALIGN[c.align ?? "left"], c.hide && HIDE[c.hide], c.className)}>
                      {c.cell(row, i)}
                    </td>
                  ))}
                </tr>
              ))}
        </tbody>
      </table>
      {rows !== null && rows.length === 0 && <div className="px-4 py-12 text-center text-sm text-muted">{empty ?? "Nothing here yet."}</div>}
    </div>
  );
}
