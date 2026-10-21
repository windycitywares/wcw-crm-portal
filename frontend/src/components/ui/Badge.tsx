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
    success: "bg-[#e7f4ea] text-[#1d6b38]",
    warning: "bg-[#fdf3e0] text-[#9a5c00]",
    danger: "bg-[#fbeae7] text-[#a12a1e]",
    info: "bg-[#e7f1fb] text-[#1d6b9e]",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", VARIANTS[variant], className)}>
      {children}
    </span>
  );
}
