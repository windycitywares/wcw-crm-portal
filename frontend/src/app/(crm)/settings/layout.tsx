"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV } from "@/components/layout/nav";
import { Icon } from "@/components/ui/Icon";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

/** Settings frame: the sections on the left, the chosen section on the right. */
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { can } = useAuth();
  const sections = (NAV.find((g) => g.label === "Administration")?.items ?? []).filter(
    (i) => i.hidden && (!i.permission || can(i.permission)),
  );
  return (
    <div className="lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-8">
      <nav aria-label="Settings sections" className="hidden lg:block">
        <div className="sticky top-20 space-y-1">
          {sections.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-[var(--radius-control)] px-3 py-2 text-sm",
                  active ? "bg-sand font-medium text-ink" : "text-muted hover:bg-sand/60 hover:text-ink",
                )}
              >
                <Icon name={item.icon} className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
