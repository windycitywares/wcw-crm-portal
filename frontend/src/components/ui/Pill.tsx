import { cn } from "@/lib/utils";

export type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";

const TONES: Record<Tone, string> = {
  neutral: "bg-sand text-ink",
  accent: "bg-accent-soft text-accent-strong",
  success: "bg-success/12 text-success",
  warning: "bg-warning/14 text-warning",
  danger: "bg-danger/12 text-danger",
  info: "bg-[color-mix(in_oklab,var(--viz-1)_14%,transparent)] text-ink",
};
const DOTS: Record<Tone, string> = {
  neutral: "bg-muted",
  accent: "bg-accent",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-[var(--viz-1)]",
};

/** Status label: a coloured dot plus words, so colour never carries the meaning alone. */
export function Pill({ tone = "neutral", className, children, dot = true }: { tone?: Tone; className?: string; children: React.ReactNode; dot?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", TONES[tone], className)}>
      {dot && <span aria-hidden="true" className={cn("size-1.5 rounded-full", DOTS[tone])} />}
      {children}
    </span>
  );
}
