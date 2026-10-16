"use client";

import * as Dialog from "@radix-ui/react-dialog";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { ROLE_LABEL } from "@/lib/types";
import { cn, initials } from "@/lib/utils";
import { Icon } from "@/components/ui/Icon";
import { Logo } from "@/components/ui/Logo";
import { Popover } from "@/components/ui/Popover";
import { ToastProvider } from "@/components/ui/Toast";
import { NAV, isActive, titleFor } from "./nav";

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  const pathname = usePathname();
  return (
    <nav aria-label="CRM" className="flex-1 overflow-y-auto px-3 py-2">
      {NAV.map((group, gi) => {
        const items = group.items.filter((i) => !i.permission || can(i.permission));
        if (items.length === 0) return null;
        return (
          <div key={group.label ?? gi} className={gi > 0 ? "mt-5" : undefined}>
            {group.label && <p className="px-3 pb-1.5 text-xs font-medium text-night-muted/80">{group.label}</p>}
            <ul className="space-y-0.5">
              {items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "relative flex items-center gap-3 rounded-[var(--radius-control)] px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-offset-0",
                        active ? "bg-white/10 text-white" : "text-night-muted hover:bg-white/5 hover:text-white",
                      )}
                    >
                      {active && <span aria-hidden="true" className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-gold" />}
                      <Icon name={item.icon} className="size-[1.15rem]" />
                      {item.label}
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

function Brand() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-1" aria-label="CRM home">
      <Logo tone="reverse" className="h-8 w-auto" />
      <span className="rounded-full border border-white/20 px-2 py-0.5 text-[0.7rem] font-semibold tracking-wide text-night-muted">CRM</span>
    </Link>
  );
}

/** Signed-in frame: sidebar, top bar, account menu. Redirects to /login when signed out. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [drawer, setDrawer] = useState(false);

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
        <aside className="sticky top-0 hidden h-dvh flex-col bg-night text-night-muted lg:flex">
          <div className="px-3 pb-3 pt-5">
            <Brand />
          </div>
          <SidebarNav />
        </aside>

        <div className="flex min-w-0 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-canvas/90 px-4 backdrop-blur sm:px-6 lg:px-8">
            <Dialog.Root open={drawer} onOpenChange={setDrawer}>
              <Dialog.Trigger className="-ml-2 grid size-10 place-items-center rounded-full hover:bg-sand lg:hidden">
                <Icon name="menu" />
                <span className="sr-only">Open menu</span>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-50 bg-night/55 lg:hidden" />
                <Dialog.Content className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col bg-night text-night-muted shadow-xl lg:hidden">
                  <Dialog.Title className="sr-only">Menu</Dialog.Title>
                  <Dialog.Description className="sr-only">Go to a section of the CRM.</Dialog.Description>
                  <div className="flex items-center justify-between px-3 pb-3 pt-5">
                    <Brand />
                    <Dialog.Close className="mr-1 grid size-9 place-items-center rounded-full text-night-muted hover:bg-white/10 hover:text-white">
                      <Icon name="close" />
                      <span className="sr-only">Close menu</span>
                    </Dialog.Close>
                  </div>
                  <SidebarNav onNavigate={() => setDrawer(false)} />
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>

            <p className="text-sm font-medium text-muted lg:hidden">{titleFor(pathname)}</p>

            <div className="ml-auto flex items-center gap-1">
              <Popover
                label="Account menu"
                trigger={
                  <>
                    <span aria-hidden="true" className="grid size-6 place-items-center rounded-full bg-accent text-[0.65rem] font-semibold text-on-accent">
                      {initials(user.full_name, user.email)}
                    </span>
                    <span className="hidden max-w-40 truncate sm:inline">{user.full_name || user.email}</span>
                    <Icon name="chevronDown" className="size-4 text-muted" />
                  </>
                }
                triggerClassName="border-transparent bg-transparent hover:border-line"
                panelClassName="w-60"
              >
                {(close) => (
                  <div>
                    <div className="px-3 py-2">
                      <p className="truncate text-sm font-medium">{user.full_name}</p>
                      <p className="truncate text-xs text-muted">{user.email}</p>
                      <p className="mt-1 text-xs text-muted">{ROLE_LABEL[user.role]} access</p>
                    </div>
                    <div className="border-t border-line pt-1">
                      <Link href="/account" onClick={close} className="flex items-center gap-2.5 rounded-[var(--radius-control)] px-3 py-2 text-sm hover:bg-sand">
                        <Icon name="customers" className="size-4 text-muted" />
                        Your account
                      </Link>
                      <button
                        type="button"
                        onClick={() => {
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

          <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[88rem] flex-1 px-4 py-6 focus:outline-none sm:px-6 lg:px-8 lg:py-8">
            {children}
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
