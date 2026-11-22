"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/utils";
import { dealStageLabel, money, salesApi, STATUS_TONE, type Deal, type Pipeline } from "./api";
import { DealDialog } from "./DealDialog";

/** The account's opportunities (deals): open ones first, then what was won or lost. */
export function AccountDeals({ accountId, accountName, onChange }: { accountId: number; accountName: string; onChange?: () => void }) {
  const { can } = useAuth();
  const [deals, setDeals] = useState<Deal[] | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [editing, setEditing] = useState<Deal | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    salesApi
      .deals({ account_id: accountId, status: "all", page_size: 10 })
      .then((page) => setDeals([...page.items].sort((a, b) => Number(a.status !== "open") - Number(b.status !== "open"))))
      .catch(() => setDeals([]));
  }, [accountId]);

  useEffect(() => {
    load();
    salesApi.pipelines().then(setPipelines).catch(() => setPipelines([]));
  }, [load]);

  return (
    <>
      <Panel>
        <PanelHeader
          title="Opportunities"
          description="Deals with this account."
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
        </PanelBody>
      </Panel>
      <DealDialog
        open={adding || editing !== null}
        deal={editing}
        pipelines={pipelines}
        account={{ id: accountId, name: accountName }}
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
