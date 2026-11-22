import Link from "next/link";
import { cn } from "@/lib/utils";

export interface BarItem {
  label: string;
  value: number;
  /** Secondary text under the label ("14 orders"). */
  sub?: string;
  href?: string;
  /** Override the shown value ("$1,240"). */
  display?: string;
  color?: string;
}

/**
 * Ranked horizontal bars: label and value on one line, a thin bar beneath. For top products, sources,
 * search terms… Values are always readable as text, so nothing depends on the bar.
 */
export function BarList({
  items,
  format = String,
  color = "var(--color-accent)",
  empty = "Nothing to show for this period yet.",
  max,
  className,
}: {
  items: BarItem[];
  format?: (n: number) => string;
  color?: string;
  empty?: string;
  max?: number;
  className?: string;
}) {
  if (items.length === 0) return <p className="py-6 text-center text-sm text-muted">{empty}</p>;
  const top = max ?? Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className={cn("space-y-3.5", className)}>
      {items.map((it) => {
        const label = it.href ? (
          <Link href={it.href} className="truncate font-medium hover:underline">
            {it.label}
          </Link>
        ) : (
          <span className="truncate font-medium">{it.label}</span>
        );
        return (
          <li key={it.label}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              {label}
              <span className="num shrink-0 font-semibold">{it.display ?? format(it.value)}</span>
            </div>
            {it.sub && <p className="text-xs text-muted">{it.sub}</p>}
            <div className="mt-1.5 h-1.5 rounded-full bg-sand" role="presentation">
              <div className="h-full rounded-full" style={{ width: `${Math.max(1.5, (it.value / top) * 100)}%`, background: it.color ?? color }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
