"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV } from "@/components/layout/nav";
import { Icon } from "@/components/ui/Icon";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

/** Settings frame: the sections on the left (a scrolling row on phones), the chosen section on the right. */
export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { can } = useAuth();
  const sections = (NAV.find((g) => g.label === "Administration")?.items ?? []).filter(
    (i) => i.hidden && (!i.permission || can(i.permission)),
  );
  return (
    <div className="lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:gap-8">
      <nav aria-label="Settings sections" className="-mx-1 mb-4 px-1 lg:mx-0 lg:mb-0 lg:px-0">
        <div className="flex gap-1 overflow-x-auto pb-1 lg:sticky lg:top-20 lg:block lg:space-y-1 lg:overflow-visible lg:pb-0">
          {sections.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-2 rounded-[var(--radius-control)] px-3 py-1.5 text-sm lg:py-2",
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
