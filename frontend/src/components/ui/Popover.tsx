"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

/**
 * Disclosure popover built on <details>: works without JavaScript state, closes on outside click and
 * Escape. `trigger` is the visible button content.
 */
export function Popover({
  trigger,
  label,
  children,
  align = "right",
  className,
  panelClassName,
  triggerClassName,
  onOpenChange,
}: {
  trigger: React.ReactNode;
  /** Accessible name for the button when `trigger` is only an icon. */
  label?: string;
  children: React.ReactNode | ((close: () => void) => React.ReactNode);
  align?: "left" | "right";
  className?: string;
  panelClassName?: string;
  triggerClassName?: string;
  onOpenChange?: (open: boolean) => void;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  const close = () => {
    if (ref.current) ref.current.open = false;
  };
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current?.open && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && ref.current?.open) {
        close();
        ref.current.querySelector("summary")?.focus();
      }
    };
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("click", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, []);
  return (
    <details ref={ref} className={cn("relative", className)} onToggle={(e) => onOpenChange?.(e.currentTarget.open)}>
      <summary
        className={cn(
          "flex h-9 cursor-pointer list-none items-center gap-2 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm font-medium hover:border-ink/40 [&::-webkit-details-marker]:hidden",
          triggerClassName,
        )}
      >
        {trigger}
        {label && <span className="sr-only">{label}</span>}
      </summary>
      <div
        className={cn(
          "absolute top-full z-50 mt-1.5 min-w-56 rounded-[var(--radius-card)] border border-line bg-surface p-1.5 shadow-[0_16px_40px_-16px_rgb(0_0_0/0.4)]",
          align === "right" ? "right-0" : "left-0",
          panelClassName,
        )}
      >
        {typeof children === "function" ? children(close) : children}
      </div>
    </details>
  );
}
