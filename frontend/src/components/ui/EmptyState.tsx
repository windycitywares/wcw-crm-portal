"use client";

import Link from "next/link";
import { Icon, type IconName } from "./Icon";

export interface EmptyStateProps {
  title: string;
  subtitle?: string;
  icon?: IconName;
  action?: { label: string; href: string; variant?: "primary" | "secondary" | "ghost" };
}

/** Consistent empty state across lists: illustration + clear next step. */
export function EmptyState({ title, subtitle, icon, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center sm:py-24">
      {icon && (
        <div className="mb-4 grid size-16 place-items-center rounded-full bg-surface/50 border border-line">
          <Icon name={icon} className="size-6 text-muted" />
        </div>
      )}
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      {action && (
        <Link href={action.href} key="action" className="mt-5 inline-flex items-center gap-2 rounded-[var(--radius-control)] border border-ink/25 bg-transparent px-4 py-2 text-sm font-medium text-ink hover:border-ink hover:bg-surface">
          <Icon name="plus" className="size-4" />
          {action.label}
        </Link>
      )}
    </div>
  );
}
