import { cn } from "@/lib/utils";

/**
 * A row of mutually exclusive buttons — how the queue and the inbox pick a view, and how the reply
 * box picks note-or-reply. One control, so those three look and behave the same.
 */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  className,
}: {
  label: string;
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div role="group" aria-label={label} className={cn("inline-flex flex-wrap rounded-[var(--radius-control)] border border-line bg-surface p-0.5", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-[calc(var(--radius-control)-2px)] px-3 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-accent",
            value === o.value ? "bg-accent text-on-accent" : "text-ink hover:bg-sand",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
