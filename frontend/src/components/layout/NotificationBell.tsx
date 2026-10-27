"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Popover } from "@/components/ui/Popover";
import { apiFetch } from "@/lib/client-api";
import { useLive, useLiveMode } from "@/lib/live";
import { cn, timeAgo } from "@/lib/utils";

/** The bell in the top bar (as in the shop admin): a count of new activity and the latest items, each a link. */

export interface Activity {
  id: string;
  type: "subscriber" | "ticket" | "reply" | "customer" | "lead" | "task" | "deal_won";
  at: string;
  unread: boolean;
  title: string;
  detail: string;
  href: string;
  tone: "success" | "warning" | "danger" | "info" | "accent" | "neutral";
}
interface Feed {
  items: Activity[];
  unread: number;
  seen_at: string | null;
  kinds: Activity["type"][];
}

const ICON: Record<Activity["type"], IconName> = {
  subscriber: "mail",
  ticket: "ticket",
  reply: "inbox",
  customer: "customers",
  lead: "funnel",
  task: "tasks",
  deal_won: "briefcase",
};
const TONE: Record<Activity["tone"], string> = {
  success: "bg-success/12 text-success",
  warning: "bg-warning/14 text-warning",
  danger: "bg-danger/12 text-danger",
  info: "bg-accent-soft text-accent",
  accent: "bg-accent-soft text-accent-strong",
  neutral: "bg-sand text-muted",
};
const POLL_MS = 60_000;

export function NotificationBell() {
  const [feed, setFeed] = useState<Feed | null>(null);
  const mode = useLiveMode();

  const load = useCallback(() => {
    apiFetch<Feed>("/notifications?limit=12").then(setFeed, () => undefined);
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => document.visibilityState === "visible" && load(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  // Something changed (a ticket, a subscriber, a lead…): the badge and the list follow within seconds.
  useLive([], () => load());

  async function opened(open: boolean) {
    if (!open) return;
    const fresh = await apiFetch<Feed>("/notifications?limit=12").catch(() => null);
    if (fresh) setFeed(fresh);
    if ((fresh ?? feed)?.unread) {
      // The list keeps its "new" marks while it's open; the badge clears.
      await apiFetch("/notifications/seen", { method: "POST" }).catch(() => undefined);
      setFeed((f) => (f ? { ...f, unread: 0 } : f));
    }
  }

  const unread = feed?.unread ?? 0;
  return (
    <Popover
      label={unread ? `Notifications, ${unread} new` : "Notifications"}
      onOpenChange={opened}
      trigger={
        <span className="relative grid place-items-center text-muted hover:text-ink">
          <Icon name="bell" className="size-5" />
          {unread > 0 && (
            <span aria-hidden="true" className="num absolute -right-2 -top-1.5 min-w-4 rounded-full bg-danger px-1 text-center text-[10px] font-semibold leading-4 text-on-danger">
              {unread > 98 ? "99+" : unread}
            </span>
          )}
        </span>
      }
      triggerClassName="border-transparent bg-transparent px-2 hover:bg-sand"
      panelClassName="w-[22rem] max-w-[calc(100vw-1.5rem)] p-0"
    >
      {(close) => (
        <div>
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <p className="font-admin text-sm font-semibold">Activity</p>
            <span className="text-xs text-muted">Last 30 days</span>
          </div>
          {feed === null ? (
            <div className="skeleton m-4 h-20" />
          ) : feed.items.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-muted">Nothing new in the last 30 days.</p>
          ) : (
            <ul className="max-h-[min(28rem,70dvh)] overflow-y-auto p-1.5">
              {feed.items.map((item) => (
                <li key={item.id}>
                  <Link
                    href={item.href}
                    onClick={close}
                    className={cn("flex items-start gap-3 rounded-[var(--radius-control)] px-3 py-2.5 hover:bg-sand", item.unread && "bg-accent-soft/40")}
                  >
                    <span className={cn("mt-0.5 grid size-8 shrink-0 place-items-center rounded-full", TONE[item.tone])}>
                      <Icon name={ICON[item.type] ?? "bell"} className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className={cn("block truncate text-sm", item.unread ? "font-semibold" : "font-medium")}>{item.title}</span>
                      {item.detail && <span className="block truncate text-xs text-muted">{item.detail}</span>}
                      <span className="block text-xs text-muted">{timeAgo(item.at)}</span>
                    </span>
                    {item.unread && (
                      <span className="mt-2 size-2 shrink-0 rounded-full bg-accent">
                        <span className="sr-only">New</span>
                      </span>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-line px-4 py-2 text-xs text-muted">
            {mode === "on" ? "Live updates on" : mode === "connecting" ? "Connecting…" : "Live updates paused — reconnecting"}
          </div>
        </div>
      )}
    </Popover>
  );
}
