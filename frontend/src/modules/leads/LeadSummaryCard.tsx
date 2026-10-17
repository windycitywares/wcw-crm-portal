"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { leadsApi, type LeadSummary } from "./api";

/** Dashboard: who is new in the funnel, what is being worked, and what has already become a customer. */
export function LeadSummaryCard() {
  const [summary, setSummary] = useState<LeadSummary | null>(null);

  useEffect(() => {
    leadsApi
      .summary()
      .then(setSummary)
      .catch(() => setSummary(null));
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
        title="Leads"
        description="Before they become customers."
        actions={
          <Link href="/leads" className="text-sm text-accent-strong underline">
            Open leads
          </Link>
        }
      />
      <PanelBody>
        {summary === null ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : (
          <dl className="grid grid-cols-2 gap-4">
            {figure("New", String(summary.new), summary.unassigned ? `${summary.unassigned} unassigned` : "nobody has picked them up yet")}
            {figure("In progress", String(summary.contacted + summary.qualified), "contacted or qualified")}
            {figure("Converted", String(summary.converted), "became customers")}
            {figure("Not interested", String(summary.unqualified))}
          </dl>
        )}
      </PanelBody>
    </Panel>
  );
}
