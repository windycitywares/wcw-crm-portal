"use client";

import { ColorTag } from "@/components/ui/ColorTag";
import { Pill } from "@/components/ui/Pill";
import { cn, timeAgo } from "@/lib/utils";
import { useLookups } from "@/modules/settings/useLookups";
import { slaState, STATUS_LABEL, STATUS_TONE, type Ticket } from "@/modules/tickets/api";

/**
 * The inbox's list: one row per conversation, closer together than the queue's table because the
 * thread sits beside it. Picking a row is a selection, not a navigation — the reply box is right there.
 */
export function InboxList({ tickets, selected, onPick }: { tickets: Ticket[] | null; selected: number | null; onPick: (t: Ticket) => void }) {
  const lookups = useLookups();

  if (tickets === null) return <p className="px-4 py-6 text-sm text-muted">Loading…</p>;
  if (tickets.length === 0) return <p className="px-4 py-6 text-sm text-muted">Nothing here. Nice.</p>;

  return (
    <ul className="divide-y divide-line">
      {tickets.map((t) => {
        const sla = slaState(t);
        const channel = lookups.find("ticket_channel", t.channel);
        const active = t.id === selected;
        return (
          <li key={t.id}>
            <button
              type="button"
              aria-current={active ? "true" : undefined}
              onClick={() => onPick(t)}
              className={cn(
                "grid w-full gap-1.5 px-4 py-3 text-left hover:bg-sand focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent",
                active && "bg-accent-soft",
              )}
            >
              <span className="flex items-start justify-between gap-3">
                <span className="min-w-0 truncate font-medium">{t.subject}</span>
                <span className="shrink-0 text-xs text-muted">{timeAgo(t.updated_at)}</span>
              </span>
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
                <span className="num">{t.number ?? `#${t.id}`}</span>
                <span className="max-w-40 truncate">{t.customer_name ?? "No customer"}</span>
                <ColorTag color={channel?.color}>{channel?.label ?? t.channel}</ColorTag>
                <Pill tone={STATUS_TONE[t.status]}>{STATUS_LABEL[t.status]}</Pill>
                {sla && (
                  <span title={sla.title}>
                    <Pill tone={sla.tone}>{sla.text}</Pill>
                  </span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
