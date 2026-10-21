"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL } from "@/lib/types";
import { cn, initials } from "@/lib/utils";
import { Icon } from "@/components/ui/Icon";
import { Logo } from "@/components/ui/Logo";
import { Popover } from "@/components/ui/Popover";
import { Badge } from "@/components/ui/Badge";
import { Avatar } from "@/components/ui/Avatar";
import { ToastProvider } from "@/components/ui/Toast";
import { NAV, isActive, titleFor } from "./nav";

function useTheme() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const stored = localStorage.getItem("wcw.theme") as "light" | "dark" | null;
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initial = stored ?? (prefersDark ? "dark" : "light");
    setTheme(initial);
    if (initial === "dark") document.documentElement.classList.add("dark");
    else document.documentElement.classList.remove("dark");
  }, []);

  const toggle = useCallback(() => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("wcw.theme", next);
    if (next === "dark") document.documentElement.classList.add("dark");
    else document.documentElement.classList.remove("dark");
  }, [theme]);

  return { theme, toggle };
}

function SidebarNav({ onNavigate, collapsed }: { onNavigate?: () => void; collapsed: boolean }) {
  const { can } = useAuth();
  const pathname = usePathname();
  return (
    <nav aria-label="CRM" className={cn("flex-1 overflow-y-auto px-2 py-3", collapsed ? "px-1" : "px-3")}>
      {NAV.map((group, gi) => {
        const items = group.items.filter((i) => !i.hidden && (!i.permission || can(i.permission)));
        if (items.length === 0) return null;
        return (
          <div key={group.label ?? gi} className={gi > 0 ? "mt-6 mb-2" : "mb-4"}>
            {!collapsed && group.label && (
              <p className="px-2 pb-1 text-[0.7rem] font-semibold tracking-wider text-night-muted/70 uppercase">
                {group.label}
              </p>
            )}
            <ul className="space-y-0.5">
              {items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      title={collapsed ? item.label : undefined}
                      className={cn(
                        "flex items-center gap-3 rounded-[var(--radius-control)] px-2.5 py-2 text-sm font-medium transition-colors focus-visible:outline-offset-0",
                        collapsed ? "px-2 justify-center" : "",
                        active ? "bg-accent-soft text-accent-strong" : "text-night-muted/80 hover:bg-night/20 hover:text-night",
                      )}>
                      {active && !collapsed && (
                        <span aria-hidden="true" className="absolute inset-y-1 left-0 w-[2px] rounded-r-full bg-accent" />
                      )}
                      <Icon name={item.icon} className={cn("size-5 shrink-0", active ? "text-accent-strong" : "text-night-muted/70")} />
                      {!collapsed && <span className="font-medium">{item.label}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-2 py-2 mb-4" aria-label="CRM home">
      <div className="grid size-6 place-items-center rounded-full bg-accent text-on-accent">
        <Icon name="dashboard" className="size-4" />
      </div>
      {!collapsed && <span className="font-semibold text-ink tracking-wide">WCW CRM</span>}
    </Link>
  );
}

/** Signed-in frame: collapsible sidebar, top bar, account menu. Redirects to /login when signed out. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const [drawer, setDrawer] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [loading, user, router, pathname]);

  useEffect(() => setDrawer(false), [pathname]);
  useEffect(() => {
    document.title = `${titleFor(pathname)} | WCW CRM`;
  }, [pathname]);

  if (!user) {
    return <div className="grid min-h-dvh place-items-center text-sm text-muted">Checking access…</div>;
  }

  return (
    <ToastProvider>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <div className="min-h-dvh lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className={cn("sticky top-0 hidden h-dvh flex-col bg-night text-night-muted lg:flex", collapsed ? "w-[4.5rem]" : "w-[15rem]")}>
          <div className="px-2 pb-3 pt-5">
            <Brand collapsed={collapsed} />
            <button
              type="button"
              onClick={() => setCollapsed((c) => !c)}
              className="ml-1 mr-1 grid size-9 place-items-center rounded-[var(--radius-control)] hover:bg-night/30 text-night-muted/70"
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
              <Icon name={collapsed ? "chevronRight" : "chevronLeft"} className="size-4" />
            </button>
          </div>
          <SidebarNav onNavigate={() => setDrawer(false)} collapsed={collapsed} />
        </aside>

        <div className="flex min-w-0 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-line bg-canvas/90 backdrop-blur px-4 sm:px-6 lg:px-8">
            <Dialog.Root open={drawer} onOpenChange={setDrawer}>
              <Dialog.Trigger className="-ml-1 grid size-10 place-items-center rounded-[var(--radius-control)] hover:bg-sand lg:hidden">
                <Icon name="menu" className="size-5" />
                <span className="sr-only">Open menu</span>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-50 bg-night/60 lg:hidden" />
                <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col bg-night text-night-muted shadow-xl lg:hidden">
                  <Dialog.Title className="sr-only">Menu</Dialog.Title>
                  <Dialog.Description className="sr-only">Go to a section of the CRM.</Dialog.Description>
                  <div className="flex items-center justify-between px-3 pb-3 pt-5">
                    <Brand collapsed={false} />
                    <Dialog.Close className="mr-1 grid size-9 place-items-center rounded-full text-night-muted hover:bg-white/10 hover:text-white">
                      <Icon name="close" className="size-5" />
                      <span className="sr-only">Close menu</span>
                    </Dialog.Close>
                  </div>
                  <SidebarNav onNavigate={() => setDrawer(false)} collapsed={false} />
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>

            <div className="ml-3 hidden sm:flex flex-1 max-w-[28rem]">
              <div className="relative">
                <Icon name="search" className="absolute left-2.5 top-2.5 size-4 text-muted" />
                <input
                  type="search"
                  placeholder="Search orders, customers, contacts…"
                  className="pl-9 pr-3 py-1.5 rounded-[var(--radius-control)] border border-line bg-surface text-sm text-ink focus:border-accent focus:outline-none w-full"
                />
              </div>
            </div>

            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                onClick={() => setNotificationsOpen((o) => !o)}
                className="relative grid size-10 place-items-center rounded-[var(--radius-control)] text-night-muted hover:bg-night/10 hover:text-night"
                title="Notifications">
                <Icon name="bell" className="size-5" />
                <span className="absolute right-1 top-1 grid size-2.5 place-items-center rounded-full bg-danger text-[0.55rem] font-bold text-on-accent shadow-sm">
                  <span className="leading-none">9+</span>
                </span>
              </button>
              <Popover
                label="Notifications"
                open={notificationsOpen}
                onOpenChange={setNotificationsOpen}
                trigger={<span className="sr-only">Notifications</span>}
                panelClassName="w-72 p-0"
                align="right">
                {() => (
                  <div className="border-t border-line">
                    <div className="px-3 py-2">
                      <p className="text-xs font-semibold text-ink">Notifications</p>
                      <p className="mt-0.5 text-xs text-muted">9 new this week</p>
                    </div>
                    <div className="divide-y divide-line">
                      <a href="/inbox" className="block px-3 py-2.5 text-sm hover:bg-sand">
                        <div className="flex items-center justify-between">
                          <span>New order #1042 delivered</span>
                          <span className="text-[0.65rem] text-muted">2h ago</span>
                        </div>
                      </a>
                      <a href="/customers" className="block px-3 py-2.5 text-sm hover:bg-sand">
                        <div className="flex items-center justify-between">
                          <span>Customer signed up</span>
                          <span className="text-[0.65rem] text-muted">5h ago</span>
                        </div>
                      </a>
                    </div>
                    <div className="px-3 py-2">
                      <a href="/inbox" className="block w-full text-left text-xs text-accent-strong hover:underline">
                        View all notifications
                      </a>
                    </div>
                  </div>
                )}
              </Popover>
              <button
                type="button"
                onClick={toggle}
                className="grid size-10 place-items-center rounded-[var(--radius-control)] text-night-muted hover:bg-night/10 hover:text-night"
                title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}>
                <Icon name={theme === "light" ? "moon" : "sun"} className="size-5" />
                <span className="sr-only">{theme === "light" ? "Dark mode" : "Light mode"}</span>
              </button>
              <Popover
                label="Account menu"
                trigger={
                  <div className="flex items-center gap-2">
                    <Avatar name={user.full_name ?? user.email} src={undefined} status="online" size="sm" />
                    <span className="hidden sm:inline truncate max-w-[14rem] text-sm font-medium text-ink">{user.full_name}</span>
                    <Icon name="chevronDown" className="size-4 text-muted" />
                  </div>
                }
                triggerClassName="border-transparent bg-transparent hover:bg-night/10"
                panelClassName="w-64">
                {(close) => (
                  <div>
                    <div className="px-3 py-2">
                      <p className="truncate text-sm font-medium text-ink">{user.full_name}</p>
                      <p className="truncate text-xs text-muted">{user.email}</p>
                      <p className="mt-1 text-xs text-muted">{ROLE_LABEL[user.role]} access</p>
                    </div>
                    <div className="border-t border-line pt-1">
                      <Link href="/settings" onClick={close} className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-sm hover:bg-sand">
                        <Icon name="sliders" className="size-4 text-muted" />
                        Settings
                      </Link>
                      <Link href="/account" onClick={close} className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-sm hover:bg-sand">
                        <Icon name="users" className="size-4 text-muted" />
                        Your account
                      </Link>
                      <button
                        type="button"
                        onClick={() => {
                          close();
                          logout();
                          router.push("/login");
                        }}
                        className="flex w-full items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-left text-sm hover:bg-sand">
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
    </ToastProvider>
  );
}
