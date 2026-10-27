import { cn } from "@/lib/utils";

/** Compact status label - smaller and more prominent than Pill. Use in tables and cards. */
export function Badge({
  variant = "neutral",
  className,
  children,
}: {
  variant?: "neutral" | "accent" | "success" | "warning" | "danger" | "info";
  className?: string;
  children: React.ReactNode;
}) {
  const VARIANTS: Record<string, string> = {
    neutral: "bg-sand text-ink",
    accent: "bg-accent-soft text-accent-strong",
    success: "bg-success/12 text-success",
    warning: "bg-warning/14 text-warning",
    danger: "bg-danger/12 text-danger",
    info: "bg-accent-soft text-accent-strong",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", VARIANTS[variant], className)}>
      {children}
    </span>
  );
}
