"use client";

import Link from "next/link";
import { ColorTag } from "@/components/ui/ColorTag";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Pill } from "@/components/ui/Pill";
import { useLookups } from "@/modules/settings/useLookups";
import { timeAgo } from "@/lib/utils";
import { slaState, STATUS_LABEL, STATUS_TONE, type Ticket } from "./api";

/** The ticket queue as a table: number and subject, priority, channel, status, SLA badge, assignee, age. */
export function TicketList({ tickets, loading, empty }: { tickets: Ticket[] | null; loading?: boolean; empty?: React.ReactNode }) {
  const lookups = useLookups();

  const columns: Column<Ticket>[] = [
    {
      key: "ticket",
      header: "Ticket",
      cell: (t) => (
        <div className="min-w-0">
          <Link href={`/tickets/${t.id}`} className="font-medium hover:text-accent-strong hover:underline">
            {t.subject}
          </Link>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted">
            <span className="num">{t.number ?? `#${t.id}`}</span>
            {t.customer_name ? (
              t.customer_id ? (
                <Link href={`/customers/${t.customer_id}`} className="hover:text-ink hover:underline">
                  {t.customer_name}
                </Link>
              ) : (
                <span>{t.customer_name}</span>
              )
            ) : (
              <span>No customer</span>
            )}
          </div>
        </div>
      ),
    },
    {
      key: "priority",
      header: "Priority",
      hide: "sm",
      cell: (t) => {
        const p = lookups.find("ticket_priority", t.priority);
        return <ColorTag color={p?.color}>{p?.label ?? t.priority}</ColorTag>;
      },
    },
    {
      key: "channel",
      header: "Channel",
      hide: "md",
      cell: (t) => {
        const c = lookups.find("ticket_channel", t.channel);
        return <span className="text-muted">{c?.label ?? t.channel}</span>;
      },
    },
    {
      key: "status",
      header: "Status",
      cell: (t) => <Pill tone={STATUS_TONE[t.status]}>{STATUS_LABEL[t.status]}</Pill>,
    },
    {
      key: "sla",
      header: "Response time",
      hide: "sm",
      cell: (t) => {
        const sla = slaState(t);
        return sla ? (
          <span title={sla.title}>
            <Pill tone={sla.tone}>{sla.text}</Pill>
          </span>
        ) : (
          <span className="text-muted">—</span>
        );
      },
    },
    {
      key: "assignee",
      header: "Assignee",
      hide: "md",
      cell: (t) => (t.assignee_name ? <span>{t.assignee_name}</span> : <span className="text-muted">Unassigned</span>),
    },
    {
      key: "updated",
      header: "Updated",
      hide: "lg",
      align: "right",
      cell: (t) => <span className="text-muted">{timeAgo(t.updated_at)}</span>,
    },
  ];

  return <DataTable columns={columns} rows={tickets} rowKey={(t) => t.id} caption="Tickets" loading={loading} empty={empty ?? "No tickets match."} />;
}
