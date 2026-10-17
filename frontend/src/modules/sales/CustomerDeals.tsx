"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/utils";
import { dealStageLabel, money, salesApi, STATUS_TONE, type Deal, type Pipeline } from "./api";
import { DealDialog } from "./DealDialog";

/** The customer's deals: open ones first, then what was won or lost. This is the sales side of the record. */
export function CustomerDeals({ customerId, customerName, onChange }: { customerId: number; customerName: string; onChange?: () => void }) {
  const { can } = useAuth();
  const [deals, setDeals] = useState<Deal[] | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [editing, setEditing] = useState<Deal | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    salesApi
      .deals({ customer_id: customerId, status: "all", page_size: 5 })
      .then((page) => setDeals([...page.items].sort((a, b) => Number(a.status !== "open") - Number(b.status !== "open"))))
      .catch(() => setDeals([]));
  }, [customerId]);

  useEffect(() => {
    load();
    salesApi.pipelines().then(setPipelines).catch(() => setPipelines([]));
  }, [load]);

  return (
    <>
      <Panel>
        <PanelHeader
          title="Deals"
          description="Opportunities with this customer."
          actions={
            can("sales:edit_own") ? (
              <Button size="sm" variant="secondary" onClick={() => setAdding(true)}>
                New deal
              </Button>
            ) : undefined
          }
        />
        <PanelBody className="p-0">
          {deals === null ? (
            <p className="px-5 py-4 text-sm text-muted">Loading…</p>
          ) : deals.length === 0 ? (
            <p className="px-5 py-4 text-sm text-muted">No deals yet.</p>
          ) : (
            <ul className="divide-y divide-line">
              {deals.map((d) => (
                <li key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-5 py-3 text-sm">
                  <button type="button" onClick={() => setEditing(d)} className="min-w-0 flex-1 truncate text-left font-medium hover:text-accent-strong hover:underline">
                    {d.title}
                  </button>
                  <span className="num">{money(d.value, d.currency)}</span>
                  <Pill tone={STATUS_TONE[d.status]}>{dealStageLabel(d)}</Pill>
                  <span className="num text-xs text-muted">
                    {d.status === "open"
                      ? d.expected_close_on
                        ? `closes ${formatDate(d.expected_close_on)}`
                        : "no close date"
                      : `${d.status} ${formatDate(d.closed_at)}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {deals && deals.length > 0 && (
            <div className="border-t border-line px-5 py-2.5 text-sm">
              <Link href={`/sales?customer_id=${customerId}`} className="text-accent-strong hover:underline">
                All deals for this customer
              </Link>
            </div>
          )}
        </PanelBody>
      </Panel>
      <DealDialog
        open={adding || editing !== null}
        deal={editing}
        pipelines={pipelines}
        customer={{ id: customerId, name: customerName }}
        onClose={() => {
          setAdding(false);
          setEditing(null);
        }}
        onSaved={() => {
          load();
          onChange?.();
        }}
      />
    </>
  );
}
