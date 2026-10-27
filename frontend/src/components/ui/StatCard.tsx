"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { Icon, type IconName } from "./Icon";

/**
 * A headline number (the shop admin's metric card): label, value, one line of context and an icon in a soft
 * circle. With `href` the whole card links to the page behind the number.
 */
export function StatCard({
  title,
  value,
  subtitle,
  icon,
  tone = "neutral",
  href,
  loading = false,
}: {
  title: string;
  value: React.ReactNode;
  subtitle?: React.ReactNode;
  icon?: IconName;
  /** Colours the subtitle: "danger" for something that needs attention. */
  tone?: "neutral" | "danger" | "success";
  href?: string;
  loading?: boolean;
}) {
  const body = (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="font-admin text-sm font-semibold text-muted">{title}</p>
        {loading ? (
          <div className="skeleton mt-2 h-8 w-24" aria-hidden="true" />
        ) : (
          <p className="num mt-1 text-[1.75rem] font-bold leading-tight text-ink">{value}</p>
        )}
        {subtitle && !loading && (
          <p className={cn("mt-1 text-xs", tone === "danger" ? "font-medium text-danger" : tone === "success" ? "text-success" : "text-muted")}>{subtitle}</p>
        )}
      </div>
      {icon && (
        <span aria-hidden="true" className="grid size-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
          <Icon name={icon} className="size-5" />
        </span>
      )}
    </div>
  );
  const frame = "block rounded-[var(--radius-card)] bg-surface p-5 shadow-[var(--shadow-card)]";
  return href ? (
    <Link href={href} className={cn(frame, "transition-shadow hover:shadow-[var(--shadow-raised)] focus-visible:outline-offset-2")}>
      {body}
    </Link>
  ) : (
    <div className={frame}>{body}</div>
  );
}
