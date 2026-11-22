"use client";

import { cn } from "@/lib/utils";
import { Icon } from "@/components/ui/Icon";
import { EXCEPTIONS, MAIN_PATH, STATUS_LABEL } from "./orders";

/** A listing photo, or a quiet placeholder of the same size. */
export function Thumb({ src, size = "md", className }: { src?: string | null; size?: "sm" | "md" | "lg"; className?: string }) {
  const box = { sm: "size-9", md: "size-12", lg: "size-16" }[size];
  return src ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt="" loading="lazy" className={cn(box, "shrink-0 rounded-md object-cover ring-1 ring-line", className)} />
  ) : (
    <span aria-hidden="true" className={cn(box, "grid shrink-0 place-items-center rounded-md bg-sand text-muted", className)}>
      <Icon name="products" className="size-4" />
    </span>
  );
}

const words = (s: string) => s.split(/\s+/).filter(Boolean);

/**
 * Etsy titles are long and alike ("Cowboy Hat Cremation Urns for Human Ashes - Personalised …"). For lists, keep the
 * part before " - " and drop the words every title in the list ends with, so what differs is what you read.
 */
export function shortTitles(titles: string[]): string[] {
  const heads = titles.map((t) => t.split(" - ")[0].trim());
  if (heads.length < 2) return heads;
  const lists = heads.map(words);
  let common = 0;
  for (;;) {
    const w = lists[0][lists[0].length - 1 - common]?.toLowerCase();
    if (!w || !lists.every((l) => l.length - common > 1 && l[l.length - 1 - common]?.toLowerCase() === w)) break;
    common++;
  }
  return common >= 2 ? lists.map((l) => l.slice(0, l.length - common).join(" ")) : heads;
}

/** The main path as steps, with the current one marked; an exception status is shown beside it. */
export function StatusSteps({ status, className }: { status: string; className?: string }) {
  const at = MAIN_PATH.indexOf(status);
  const exception = EXCEPTIONS.includes(status);
  return (
    <div className={cn("grid gap-2", className)}>
      <ol className="flex items-center" aria-label="Order progress">
        {MAIN_PATH.map((s, i) => {
          const done = at >= 0 && i < at;
          const current = i === at;
          return (
            <li key={s} className="flex flex-1 items-center last:flex-none" aria-current={current ? "step" : undefined}>
              <span className="flex flex-col items-center gap-1">
                <span
                  className={cn(
                    "grid size-7 place-items-center rounded-full border-2 text-xs font-bold",
                    done && "border-accent bg-accent text-on-accent",
                    current && !exception && "border-accent bg-accent-soft text-accent",
                    !done && !current && "border-line bg-surface text-muted",
                  )}
                >
                  {done ? <Icon name="check" className="size-3.5" strokeWidth={3} /> : i + 1}
                </span>
                <span className={cn("whitespace-nowrap text-[11px]", current ? "font-semibold text-ink" : "text-muted")}>
                  {STATUS_LABEL[s].replace(" (paid)", "")}
                </span>
              </span>
              {i < MAIN_PATH.length - 1 ? <span aria-hidden="true" className={cn("mx-1 mb-5 h-0.5 flex-1 rounded", done ? "bg-accent" : "bg-line")} /> : null}
            </li>
          );
        })}
      </ol>
      {exception ? (
        <p className="flex items-center gap-1.5 text-sm font-medium text-danger">
          <Icon name="alert" className="size-4" /> {STATUS_LABEL[status]}
        </p>
      ) : null}
    </div>
  );
}

/** A small headline figure for summary rows. */
export function Stat({ label, value, sub, tone, onClick, active }: {
  label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: "danger" | "warning" | "success"; onClick?: () => void; active?: boolean;
}) {
  const body = (
    <>
      <span className="text-sm text-muted">{label}</span>
      <span className={cn("num font-admin mt-1 block text-2xl font-bold", tone === "danger" && "text-danger", tone === "warning" && "text-warning", tone === "success" && "text-success")}>{value}</span>
      {sub ? <span className="mt-0.5 block text-xs text-muted">{sub}</span> : null}
    </>
  );
  const cls = cn(
    "block rounded-[var(--radius-card)] bg-surface p-4 text-left shadow-[var(--shadow-card,0_0_0_1px_var(--color-line))]",
    onClick && "transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-2 focus-visible:outline-accent",
    active && "ring-2 ring-accent",
  );
  return onClick ? <button type="button" onClick={onClick} aria-pressed={active} className={cls}>{body}</button> : <div className={cls}>{body}</div>;
}

/** Money as the order's currency (Etsy sends strings like "12.50"). */
export function money(v: string | number | null | undefined, currency = "USD") {
  if (v === null || v === undefined || v === "") return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(v));
}
