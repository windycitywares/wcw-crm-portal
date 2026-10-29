import Link from "next/link";
import { cn } from "@/lib/utils";
import { Icon, type IconName } from "./Icon";

/* Icon-only actions, the same API as the shop admin's (components/admin/ui/IconButton.tsx): `label` is both the tooltip and the accessible name. */
const base = "grid size-8 place-items-center rounded-full text-muted transition-colors focus-visible:outline-2 disabled:pointer-events-none disabled:opacity-50";
const tones = { default: "hover:bg-sand hover:text-ink", danger: "hover:bg-danger/10 hover:text-danger" };

export function IconButton({ icon, label, tone = "default", className, type = "button", ...props }: {
  icon: IconName;
  label: string;
  tone?: "default" | "danger";
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children" | "title">) {
  return (
    <button type={type} title={label} aria-label={label} className={cn(base, tones[tone], className)} {...props}>
      <Icon name={icon} className="size-4" />
    </button>
  );
}

/** An icon-only link. `external` opens another site in a new tab; otherwise it is a normal in-app link. */
export function IconLink({ icon, label, href, external = false, className }: { icon: IconName; label: string; href: string; external?: boolean; className?: string }) {
  const body = <Icon name={icon} className="size-4" />;
  const cls = cn(base, tones.default, className);
  return external ? (
    <a href={href} title={label} aria-label={`${label} (new tab)`} target="_blank" rel="noopener noreferrer" className={cls}>
      {body}
    </a>
  ) : (
    <Link href={href} title={label} aria-label={label} className={cls}>
      {body}
    </Link>
  );
}

/** Right-aligned group of row actions. */
export function RowActions({ children }: { children: React.ReactNode }) {
  return <div className="flex items-center justify-end gap-1">{children}</div>;
}
