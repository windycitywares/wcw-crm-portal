"use client";

import { cn } from "@/lib/utils";
import { Button } from "./Button";
import { Icon } from "./Icon";

/** Primary action button with an optional loading state. */
export function LoadingButton({ loading, label, disabled, size = "md", className, ...props }: {
  loading?: boolean;
  label?: string;
  disabled?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <Button variant="primary" size={size} className={className} disabled={disabled || loading} loading={loading} {...props}>
      {label}
    </Button>
  );
}

/** Icon-only button (toolbar / table action). */
export function IconButton({ variant = "ghost", size = "sm", title, className, ...props }: {
  variant?: "ghost" | "primary" | "secondary" | "danger";
  size?: "sm" | "md";
  title?: string;
  className?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" title={title} className={cn(buttonClass(variant, size, className),
      variant === "danger" && "bg-transparent text-danger hover:bg-danger/10", size === "sm" && "p-1.5", size === "md" && "p-2")}
      {...props} />
  );
}

function buttonClass(variant = "primary", size = "md", className?: string) {
  const base = "inline-flex items-center justify-center gap-2 rounded-[var(--radius-control)] font-medium tracking-[0.01em] transition-colors disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap";
  const variants: Record<string, string> = {
    primary: "bg-accent text-on-accent hover:bg-accent-strong",
    secondary: "border border-ink/25 bg-transparent text-ink hover:border-ink hover:bg-surface",
    ghost: "text-ink hover:bg-sand",
    danger: "bg-danger text-white hover:opacity-90",
  };
  const sizes: Record<string, string> = { sm: "h-9 px-3 text-sm", md: "h-11 px-6 text-sm", lg: "h-13 px-8 text-[0.9375rem]" };
  return cn(base, variants[variant], sizes[size], className);
}
