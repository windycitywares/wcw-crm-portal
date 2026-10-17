"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { salesApi, money, type Board, type SalesSummary } from "./api";

/** Dashboard: what the pipeline is worth right now, and what closed this month. */
export function SalesSummaryCard() {
  const [summary, setSummary] = useState<SalesSummary | null>(null);
  const [board, setBoard] = useState<Board | null>(null);

  useEffect(() => {
    salesApi.summary().then(setSummary).catch(() => setSummary(null));
    salesApi.board().then(setBoard).catch(() => setBoard(null));
  }, []);

  const figure = (label: string, value: string, hint?: string) => (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="num mt-0.5 text-lg font-medium">{value}</dd>
      {hint && <dd className="text-xs text-muted">{hint}</dd>}
    </div>
  );

  return (
    <Panel>
      <PanelHeader
        title="Pipeline"
        description={board ? board.pipeline_name : undefined}
        actions={
          <Link href="/sales" className="text-sm text-accent-strong underline">
            Open the board
          </Link>
        }
      />
      <PanelBody>
        {summary === null ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : (
          <dl className="grid grid-cols-2 gap-4">
            {figure("Open", money(summary.open_value), `${summary.open_count} ${summary.open_count === 1 ? "deal" : "deals"}`)}
            {figure("Weighted", money(summary.weighted_value), "value × probability")}
            {figure("Won this month", money(summary.won_value), `${summary.won_count} ${summary.won_count === 1 ? "deal" : "deals"}`)}
            {figure("Lost this month", String(summary.lost_count))}
          </dl>
        )}
      </PanelBody>
    </Panel>
  );
}
