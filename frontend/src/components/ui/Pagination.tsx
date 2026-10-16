import { Icon } from "./Icon";
import { cn } from "@/lib/utils";

const btn =
  "inline-flex h-8 items-center gap-1 rounded-[var(--radius-control)] border border-line bg-surface px-2.5 text-sm font-medium hover:border-ink/40 disabled:pointer-events-none disabled:opacity-40";

/** "26–50 of 105" with previous/next. Hidden when everything fits on one page. */
export function Pagination({
  page,
  pageSize,
  total,
  onPage,
  className,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  className?: string;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <nav aria-label="Pagination" className={cn("flex items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm", className)}>
      <p className="num text-muted">
        {from}–{to} of {total.toLocaleString("en-US")}
      </p>
      <div className="flex items-center gap-2">
        <button type="button" className={btn} disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <Icon name="chevronLeft" className="size-4" />
          Previous
        </button>
        <span className="num text-muted" aria-live="polite">
          Page {page} of {pages}
        </span>
        <button type="button" className={btn} disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
          <Icon name="chevronRight" className="size-4" />
        </button>
      </div>
    </nav>
  );
}
