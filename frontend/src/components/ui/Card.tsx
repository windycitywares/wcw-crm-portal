import { cn } from "@/lib/utils";

/** Elevated container with optional header and footer. Use instead of Panel for most pages. */
export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("rounded-[var(--radius-card)] border border-line bg-surface shadow-sm", className)} {...props} />
  );
}

export function CardHeader({
  title,
  description,
  actions,
  className,
}: {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4", className)}>
      <div className="min-w-0 flex-1">
        {title && <h3 className="text-base font-semibold text-ink">{title}</h3>}
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}

export function CardFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("border-t border-line px-5 py-4 flex flex-wrap items-center justify-between gap-3", className)} {...props} />
  );
}
