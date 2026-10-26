import Link from "next/link";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const base =
  "inline-flex items-center justify-center gap-2 rounded-[var(--radius-control)] font-medium tracking-[0.01em] transition-colors disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap";
const variants: Record<Variant, string> = {
  primary: "bg-accent text-on-accent hover:bg-accent-strong",
  secondary: "border border-ink/25 bg-transparent text-ink hover:border-ink hover:bg-surface",
  ghost: "text-ink hover:bg-sand",
  danger: "bg-danger text-on-danger hover:opacity-90",
};
const sizes: Record<Size, string> = {
  sm: "h-9 px-4 text-sm",
  md: "h-11 px-6 text-sm",
  lg: "h-13 px-8 text-[0.9375rem]",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", className?: string) {
  return cn(base, variants[variant], sizes[size], className);
}

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", className, type = "button", loading, ...props },
  ref,
) {
  return (
    <button ref={ref} type={type} className={cn(buttonClass(variant, size, className), loading && "opacity-70 cursor-not-allowed")}
      disabled={loading} {...props} aria-busy={loading}>
      {loading && <span className="flex items-center gap-1.5">
        <span className="relative h-3.5 w-3.5 rounded-full border-2 border-current border-transparent border-t-current animate-spin" />
      </span>}
      {!loading && props.children}
    </button>
  );
});

export function ButtonLink({
  href,
  variant = "primary",
  size = "md",
  className,
  ...props
}: React.ComponentProps<typeof Link> & { variant?: Variant; size?: Size }) {
  return <Link href={href} className={buttonClass(variant, size, className)} {...props} />;
}
