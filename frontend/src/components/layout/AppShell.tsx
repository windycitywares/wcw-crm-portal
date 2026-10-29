"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";
import { Logo, LogoMark } from "@/components/ui/Logo";
import { Popover } from "@/components/ui/Popover";
import { TestModeBanner } from "@/components/ui/TestModeBanner";
import { ToastProvider } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { LiveProvider } from "@/lib/live";
import { applyTheme, readTheme, saveTheme, type Theme } from "@/lib/theme";
import { ROLE_LABEL } from "@/lib/types";
import { cn } from "@/lib/utils";
import { NotificationBell } from "./NotificationBell";
import { NAV, SETTINGS_NAV, activeHref, inSettings, titleFor, type NavGroup } from "./nav";

/*
 * The signed-in frame, built like the shop admin (wcw-shop-portal components/admin/AdminShell.tsx) so the team
 * moves between the two without noticing: a white sidebar with a soft shadow, small uppercase section headings,
 * the current page tinted with an accent bar and accent icon, a white top bar, a soft grey-blue work area.
 */

/** Light/dark, shared with windycitywares.com and the shop through the wcw-theme cookie (lib/theme.ts). */
function useTheme() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const initial = readTheme();
    setTheme(initial);
    applyTheme(initial);
    // Switched on the shop or the main site in another tab: follow it when this tab is shown again.
    const onShow = () => {
      if (document.visibilityState !== "visible") return;
      const saved = readTheme();
      setTheme(saved);
      applyTheme(saved);
    };
    document.addEventListener("visibilitychange", onShow);
    return () => document.removeEventListener("visibilitychange", onShow);
  }, []);

  const toggle = useCallback(() => {
    const next: Theme = theme === "light" ? "dark" : "light";
    setTheme(next);
    saveTheme(next);
    applyTheme(next);
  }, [theme]);

  return { theme, toggle };
}

function NavGroups({ groups, onNavigate, collapsed }: { groups: NavGroup[]; onNavigate?: () => void; collapsed: boolean }) {
  const { can } = useAuth();
  const pathname = usePathname();
  const current = activeHref(pathname, groups);
  return (
    <>
      {groups.map((group, gi) => {
        const items = group.items.filter((i) => !i.hidden && (!i.permission || can(i.permission)));
        if (items.length === 0) return null;
        return (
          <div key={group.label ?? gi} className={gi > 0 ? "mt-4" : ""}>
            {group.label &&
              (collapsed ? (
                <hr className="mx-2 mb-2 border-line" />
              ) : (
                <p className="font-admin px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-muted">{group.label}</p>
              ))}
            <ul className="space-y-0.5">
              {items.map((item) => {
                const active = item.href === current;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      title={collapsed ? item.label : undefined}
                      className={cn(
                        "font-admin group relative flex items-center gap-3 rounded-[var(--radius-control)] py-2 text-[0.95rem] transition-[color,background-color,transform] duration-150 focus-visible:outline-offset-0",
                        collapsed ? "justify-center px-2" : item.child ? "ml-4 px-3 text-[0.875rem]" : "px-3",
                        active ? "bg-sand font-bold text-ink" : "text-ink hover:bg-sand/60 hover:text-accent motion-safe:hover:translate-x-0.5",
                      )}
                    >
                      {active && <span aria-hidden="true" className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-accent" />}
                      <Icon name={item.icon} className={cn("size-[1.15rem] shrink-0", active ? "text-accent" : "text-muted group-hover:text-accent")} />
                      {collapsed ? <span className="sr-only">{item.label}</span> : <span>{item.label}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </>
  );
}

/** The main menu; in Settings it becomes a way back plus the settings sections (as in the shop admin). */
function SidebarNav({ onNavigate, collapsed }: { onNavigate?: () => void; collapsed: boolean }) {
  const pathname = usePathname();
  const settings = inSettings(pathname);
  return (
    <nav aria-label={settings ? "Settings" : "CRM"} className={cn("flex-1 overflow-y-auto pb-6 pt-2", collapsed ? "px-2" : "px-4")}>
      {settings ? (
        <>
          <Link
            href="/dashboard"
            onClick={onNavigate}
            title={collapsed ? "Back to dashboard" : undefined}
            className={cn(
              "font-admin mb-4 flex items-center gap-2 rounded-[var(--radius-control)] border border-line py-2 text-sm font-semibold text-ink hover:border-accent hover:text-accent",
              collapsed ? "justify-center px-2" : "px-3",
            )}
          >
            <Icon name="chevronLeft" className="size-4 shrink-0" />
            {collapsed ? <span className="sr-only">Back to dashboard</span> : "Back to dashboard"}
          </Link>
          <NavGroups groups={[{ items: [{ href: "/settings", label: "All settings", icon: "dashboard" }] }, ...SETTINGS_NAV]} onNavigate={onNavigate} collapsed={collapsed} />
        </>
      ) : (
        <NavGroups groups={NAV} onNavigate={onNavigate} collapsed={collapsed} />
      )}
    </nav>
  );
}

/** The WindyCityWares logo (the same artwork as the shop and the website). `compact` is the emblem alone, for the narrow sidebar. */
function Brand({ compact = false, className = "h-[22px] w-auto" }: { compact?: boolean; className?: string }) {
  return (
    <Link href="/dashboard" className="flex min-w-0 items-center rounded-[var(--radius-control)] px-1 py-1" aria-label="WindyCityWares CRM home">
      {compact ? <LogoMark className="size-9" /> : <Logo className={className} />}
    </Link>
  );
}

/** One box for everything: an email or a name finds the customer, a ticket number (T-123 or #123) opens the queue. */
function searchTarget(raw: string): string | null {
  const q = raw.trim();
  if (!q) return null;
  if (/^(t-?|#)\d+$/i.test(q)) return `/tickets?q=${encodeURIComponent(q.replace(/^#/, ""))}`;
  return `/customers?q=${encodeURIComponent(q)}`;
}

/** Signed-in frame: collapsible sidebar, top bar, account menu. Redirects to /login when signed out. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const [drawer, setDrawer] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, router, pathname]);

  // Remember a collapsed sidebar for next time (a per-browser convenience only).
  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem("crm.sidebar") === "collapsed");
    } catch {
      /* private mode */
    }
  }, []);
  const toggleCollapsed = () =>
    setCollapsed((c) => {
      try {
        localStorage.setItem("crm.sidebar", c ? "open" : "collapsed");
      } catch {
        /* private mode */
      }
      return !c;
    });

  useEffect(() => setDrawer(false), [pathname]);
  useEffect(() => {
    document.title = `${titleFor(pathname)} | WCW CRM`;
  }, [pathname]);

  if (!user) {
    return <div className="grid min-h-dvh place-items-center text-sm text-muted">Checking access…</div>;
  }

  return (
    <ToastProvider>
      <LiveProvider>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <div className={cn("min-h-dvh lg:grid", collapsed ? "lg:grid-cols-[4.5rem_minmax(0,1fr)]" : "lg:grid-cols-[16rem_minmax(0,1fr)]")}>
        {/* Sidebar: a white menu with a soft shadow; the current page has a tint, an accent bar and an accent icon */}
        <aside className="sticky top-0 z-20 hidden h-dvh flex-col bg-surface shadow-[var(--shadow-card)] lg:flex">
          <div className={cn("flex h-16 shrink-0 items-center gap-2", collapsed ? "flex-col justify-center px-2" : "justify-between pl-4 pr-3")}>
            <Brand compact={collapsed} />
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-expanded={!collapsed}
              className="grid size-9 shrink-0 place-items-center rounded-[var(--radius-control)] text-muted hover:bg-sand hover:text-accent"
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              <Icon name="menu" className="size-5" />
              <span className="sr-only">{collapsed ? "Expand sidebar" : "Collapse sidebar"}</span>
            </button>
          </div>
          <SidebarNav onNavigate={() => setDrawer(false)} collapsed={collapsed} />
        </aside>

        <div className="flex min-w-0 flex-col">
          <TestModeBanner label="Test mode" text="Test mode: you're working on a copy of the CRM's data. Nothing here changes the live data.">
            {" "}
            <Link href="/settings/environment" className="underline underline-offset-4">
              Test mode settings
            </Link>
          </TestModeBanner>
          <header className="sticky top-0 z-30 flex h-16 items-center gap-2 bg-surface px-4 shadow-[var(--shadow-card)] sm:px-6 lg:px-8">
            <Dialog.Root open={drawer} onOpenChange={setDrawer}>
              <Dialog.Trigger className="-ml-1 grid size-10 place-items-center rounded-[var(--radius-control)] hover:bg-sand lg:hidden">
                <Icon name="menu" className="size-5" />
                <span className="sr-only">Open menu</span>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-50 bg-night/50 lg:hidden" />
                <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col bg-surface shadow-[var(--shadow-raised)] lg:hidden">
                  <Dialog.Title className="sr-only">Menu</Dialog.Title>
                  <Dialog.Description className="sr-only">Go to a section of the CRM.</Dialog.Description>
                  <div className="flex h-16 items-center justify-between pl-4 pr-3">
                    <Brand className="h-6 w-auto" />
                    <Dialog.Close className="grid size-9 place-items-center rounded-full text-muted hover:bg-sand hover:text-ink">
                      <Icon name="close" className="size-5" />
                      <span className="sr-only">Close menu</span>
                    </Dialog.Close>
                  </div>
                  <SidebarNav onNavigate={() => setDrawer(false)} collapsed={false} />
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>

            <form
              role="search"
              className="ml-2 hidden max-w-[26rem] flex-1 sm:flex"
              onSubmit={(e) => {
                e.preventDefault();
                const target = searchTarget(String(new FormData(e.currentTarget).get("q") || ""));
                if (!target) return;
                // Already on that page: reload so it reads the new search; otherwise a normal client-side move.
                if (pathname === target.split("?")[0]) window.location.assign(target);
                else router.push(target);
              }}
            >
              <label htmlFor="crm-search" className="sr-only">
                Search the CRM
              </label>
              <div className="relative w-full">
                <Icon name="search" className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
                <input
                  id="crm-search"
                  name="q"
                  type="search"
                  placeholder="Customer name or email, ticket T-123…"
                  className="w-full rounded-full border border-line bg-canvas py-2 pl-10 pr-4 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none"
                />
              </div>
            </form>

            <div className="ml-auto flex items-center gap-2">
              <NotificationBell />
              <button
                type="button"
                onClick={toggle}
                className="grid size-10 place-items-center rounded-full text-muted hover:bg-sand hover:text-ink"
                title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
              >
                <Icon name={theme === "light" ? "moon" : "sun"} className="size-5" />
                <span className="sr-only">{theme === "light" ? "Switch to dark mode" : "Switch to light mode"}</span>
              </button>
              <Popover
                label="Account menu"
                trigger={
                  <div className="flex items-center gap-2">
                    <Avatar name={user.full_name ?? user.email} status="online" size="sm" />
                    <span className="hidden max-w-[14rem] truncate text-sm font-medium text-ink sm:inline">{user.full_name || user.email}</span>
                    <Icon name="chevronDown" className="size-4 text-muted" />
                  </div>
                }
                triggerClassName="border-transparent bg-transparent hover:bg-sand"
                panelClassName="w-64"
              >
                {(close) => (
                  <div>
                    <div className="px-3 py-2">
                      <p className="truncate text-sm font-medium text-ink">{user.full_name || "Signed in"}</p>
                      <p className="truncate text-xs text-muted">{user.email}</p>
                      <p className="mt-1 text-xs text-muted">{ROLE_LABEL[user.role]} access</p>
                    </div>
                    <div className="border-t border-line pt-1">
                      <Link href="/settings" onClick={close} className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-sm hover:bg-sand">
                        <Icon name="sliders" className="size-4 text-muted" />
                        Settings
                      </Link>
                      <Link href="/account" onClick={close} className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-sm hover:bg-sand">
                        <Icon name="customers" className="size-4 text-muted" />
                        Your account
                      </Link>
                      <button
                        type="button"
                        onClick={() => {
                          close();
                          logout();
                          router.push("/login");
                        }}
                        className="flex w-full items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-left text-sm hover:bg-sand"
                      >
                        <Icon name="logout" className="size-4 text-muted" />
                        Sign out
                      </button>
                    </div>
                  </div>
                )}
              </Popover>
            </div>
          </header>

          <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[92rem] flex-1 px-4 py-6 focus:outline-none sm:px-6 lg:px-8 lg:py-8">
            {children}
          </main>
        </div>
      </div>
      </LiveProvider>
    </ToastProvider>
  );
}
