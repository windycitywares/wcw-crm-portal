import Link from "next/link";
import { cn } from "@/lib/utils";

/** Title, one line of context, and the page's primary actions. One per page, always the first thing. */
export function PageHeader({
  title,
  description,
  actions,
  back,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  /** Parent page, shown as a quiet link above the title. */
  back?: { href: string; label: string };
  className?: string;
}) {
  return (
    <header className={cn("mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3", className)}>
      <div className="min-w-0">
        {back && (
          <Link href={back.href} className="mb-1 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
            <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 6l-6 6 6 6" />
            </svg>
            {back.label}
          </Link>
        )}
        <h1 className="text-[1.625rem]">{title}</h1>
        {description && <p className="admin-prose mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
