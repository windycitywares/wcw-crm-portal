"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/utils";
import { slaState, STATUS_LABEL, STATUS_TONE, ticketsApi, type Ticket } from "./api";
import { TicketDialog } from "./TicketDialog";

/** The customer's support tickets, newest first, with a shortcut to open a new one. */
export function CustomerTickets({ customerId, customerName, onChange }: { customerId: number; customerName: string; onChange?: () => void }) {
  const { can } = useAuth();
  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    ticketsApi
      .list({ customer_id: customerId, state: "all", page_size: 5 })
      .then((page) => setTickets(page.items))
      .catch(() => setTickets([]));
  }, [customerId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <Panel>
        <PanelHeader
          title="Tickets"
          description="Support conversations about this customer."
          actions={
            can("tickets:edit") ? (
              <Button size="sm" variant="secondary" onClick={() => setAdding(true)}>
                New ticket
              </Button>
            ) : undefined
          }
        />
        <PanelBody className="p-0">
          {tickets === null ? (
            <p className="px-5 py-4 text-sm text-muted">Loading…</p>
          ) : tickets.length === 0 ? (
            <p className="px-5 py-4 text-sm text-muted">No tickets yet.</p>
          ) : (
            <ul className="divide-y divide-line">
              {tickets.map((t) => {
                const sla = slaState(t);
                return (
                  <li key={t.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-5 py-3 text-sm">
                    <Link href={`/tickets/${t.id}`} className="min-w-0 flex-1 truncate font-medium hover:text-accent-strong hover:underline">
                      {t.subject}
                    </Link>
                    <Pill tone={STATUS_TONE[t.status]}>{STATUS_LABEL[t.status]}</Pill>
                    {sla && <Pill tone={sla.tone}>{sla.text}</Pill>}
                    <span className="num text-xs text-muted">
                      {t.number ?? `#${t.id}`} · {formatDate(t.created_at)}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
          {tickets && tickets.length > 0 && (
            <div className="border-t border-line px-5 py-2.5 text-sm">
              <Link href={`/tickets?customer_id=${customerId}&state=all`} className="text-accent-strong hover:underline">
                All tickets for this customer
              </Link>
            </div>
          )}
        </PanelBody>
      </Panel>
      <TicketDialog
        open={adding}
        ticket={null}
        customer={{ id: customerId, name: customerName }}
        onClose={() => setAdding(false)}
        onSaved={() => {
          load();
          onChange?.();
        }}
      />
    </>
  );
}
