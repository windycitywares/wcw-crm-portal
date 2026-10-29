"use client";

import { useEffect, useState } from "react";
import { ButtonLink } from "@/components/ui/Button";
import { IconLink } from "@/components/ui/IconButton";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { formatDateTime } from "@/lib/utils";
import type { Page } from "@/lib/types";
import {
  campaignsApi,
  formatPercent,
  STATUS_LABEL,
  STATUS_TONE,
  type CampaignReport,
  type CampaignStats,
  type CampaignSummary,
} from "@/modules/campaigns/api";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Page<CampaignSummary> | null>(null);
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<CampaignReport | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [page, summary] = await Promise.all([campaignsApi.list(), campaignsApi.stats()]);
        setCampaigns(page);
        setStats(summary);
        if (page.items[0]) {
          setSelected(await campaignsApi.report(page.items[0].id));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Couldn't load campaigns");
      }
    })();
  }, []);

  const openReport = async (campaign: CampaignSummary) => {
    try {
      setSelected(await campaignsApi.report(campaign.id));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the campaign report");
    }
  };

  const columns: Column<CampaignSummary>[] = [
    {
      key: "name",
      header: "Campaign",
      cell: (row) => (
        <div className="flex items-center gap-2">
          <button type="button" className="text-left font-medium text-ink hover:text-accent-strong hover:underline" onClick={() => void openReport(row)}>
            {row.name}
          </button>
          <IconLink icon="eye" label={`Open ${row.name}`} href={`/campaigns/${row.id}`} />
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => <Pill tone={STATUS_TONE[row.status]}>{STATUS_LABEL[row.status]}</Pill>,
    },
    {
      key: "audience",
      header: "Reach",
      align: "right",
      cell: (row) => (
        <span className="num text-muted">
          {row.reachable}/{row.audience}
        </span>
      ),
    },
    {
      key: "template_name",
      header: "Template",
      cell: (row) => <span className="text-muted">{row.template_name ?? "—"}</span>,
      hide: "md",
    },
    {
      key: "target_list_name",
      header: "Audience",
      cell: (row) => <span className="text-muted">{row.target_list_name ?? "—"}</span>,
      hide: "lg",
    },
    {
      key: "scheduled_at",
      header: "Scheduled",
      align: "right",
      cell: (row) => <span className="num text-muted">{formatDateTime(row.scheduled_at)}</span>,
      hide: "lg",
    },
  ];

  const metricCards = [
    { label: "Campaigns", value: stats?.campaigns ?? 0, hint: `in the last ${stats?.days ?? 7} days` },
    { label: "Sent", value: stats?.sent ?? 0, hint: "messages handed to SMTP" },
    { label: "Opened", value: stats?.opened ?? 0, hint: formatPercent(stats?.open_rate) },
    { label: "Clicked", value: stats?.clicked ?? 0, hint: formatPercent(stats?.click_rate) },
  ];

  return (
    <>
      <PageHeader
        title="Campaigns"
        description="Email templates, target lists and campaign performance in one view."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <ButtonLink href="/campaigns/new" size="sm">
              New campaign
            </ButtonLink>
            <ButtonLink href="/campaigns/templates" size="sm" variant="secondary">
              Templates
            </ButtonLink>
            <ButtonLink href="/campaigns/lists" size="sm" variant="secondary">
              Audiences
            </ButtonLink>
            <ButtonLink href="/campaigns/suppressions" size="sm" variant="secondary">
              Suppressions
            </ButtonLink>
          </div>
        }
      />

      <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metricCards.map((card) => (
          <Panel key={card.label} className="p-4">
            <div className="text-sm text-muted">{card.label}</div>
            <div className="mt-2 text-2xl font-semibold">{card.value}</div>
            <div className="mt-1 text-xs text-muted">{card.hint}</div>
          </Panel>
        ))}
      </div>

      {error && (
        <div className="mb-4 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</div>
      )}

      <Panel>
        <PanelHeader
          title="Campaign list"
          description="Drafts, scheduled sends and the ones already out the door."
        />
        <DataTable columns={columns} rows={campaigns?.items ?? null} rowKey={(row) => row.id} caption="Campaigns" empty="No campaigns created yet." />
      </Panel>

      {selected && (
        <Panel className="mt-6">
          <PanelHeader title={selected.name} description={`${STATUS_LABEL[selected.status]} campaign report`} />
          <PanelBody>
            <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {[
                { label: "Delivered", value: selected.delivered },
                { label: "Opened", value: `${selected.opened} · ${formatPercent(selected.open_rate)}` },
                { label: "Clicked", value: `${selected.clicked} · ${formatPercent(selected.click_rate)}` },
                { label: "Unsubscribed", value: selected.unsubscribed },
                { label: "Recipients", value: selected.recipients.total },
              ].map((item) => (
                <div key={item.label} className="rounded border border-line bg-canvas p-3">
                  <div className="text-xs uppercase tracking-wide text-muted">{item.label}</div>
                  <div className="mt-2 text-xl font-semibold">{item.value}</div>
                </div>
              ))}
            </div>

            <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
              <div>
                <h3 className="mb-2 text-sm font-medium uppercase tracking-wide text-muted">Top links</h3>
                {selected.links.length === 0 ? (
                  <p className="text-sm text-muted">No tracked links for this campaign yet.</p>
                ) : (
                  <ul className="space-y-2">
                    {selected.links.map((link) => (
                      <li key={link.url} className="flex items-center justify-between gap-3 rounded border border-line px-3 py-2">
                        <span className="truncate text-sm text-ink">{link.url}</span>
                        <span className="text-sm font-medium text-muted">{link.recipients} clicks</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <h3 className="mb-2 text-sm font-medium uppercase tracking-wide text-muted">Summary</h3>
                <dl className="space-y-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-muted">Template</dt>
                    <dd>{selected.template_name ?? "—"}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-muted">Audience</dt>
                    <dd>{selected.target_list_name ?? "—"}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-muted">Started</dt>
                    <dd>{formatDateTime(selected.started_at)}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <dt className="text-muted">Sent</dt>
                    <dd>{selected.recipients.sent}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </PanelBody>
        </Panel>
      )}
    </>
  );
}
