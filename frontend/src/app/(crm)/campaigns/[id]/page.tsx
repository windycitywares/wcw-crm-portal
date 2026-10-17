"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { formatDateTime } from "@/lib/utils";
import { campaignsApi, formatPercent, STATUS_LABEL, STATUS_TONE, type CampaignReport, type CampaignSummary } from "@/modules/campaigns/api";

export default function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const [id, setId] = useState<number | null>(null);
  const [campaign, setCampaign] = useState<CampaignSummary | null>(null);
  const [report, setReport] = useState<CampaignReport | null>(null);
  const [scheduledAt, setScheduledAt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void (async () => {
      const { id: routeId } = await params;
      const numericId = Number(routeId);
      setId(numericId);
      if (!numericId) return;
      await loadCampaign(numericId);
    })();
  }, [params]);

  const loadCampaign = async (campaignId: number) => {
    try {
      const [row, reportRow] = await Promise.all([campaignsApi.get(campaignId), campaignsApi.report(campaignId)]);
      setCampaign(row);
      setReport(reportRow);
      setScheduledAt(row.scheduled_at ? new Date(row.scheduled_at).toISOString().slice(0, 16) : "");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the campaign");
    }
  };

  const refresh = async () => {
    if (!id) return;
    await loadCampaign(id);
  };

  const doAction = async (fn: () => Promise<CampaignSummary | void>) => {
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Campaign action failed");
    } finally {
      setBusy(false);
    }
  };

  const saveSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setBusy(true);
    setError(null);
    try {
      await campaignsApi.schedule(id, new Date(scheduledAt).toISOString());
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save the schedule");
    } finally {
      setBusy(false);
    }
  };

  const removeCampaign = async () => {
    if (!id) return;
    const confirmed = window.confirm(`Delete ${campaign?.name ?? "this campaign"}? This cannot be undone.`);
    if (!confirmed) return;

    setBusy(true);
    setError(null);
    try {
      await campaignsApi.delete(id);
      router.push("/campaigns");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete this campaign");
    } finally {
      setBusy(false);
    }
  };

  if (!campaign) {
    return <PageHeader title="Campaign" description={error ?? "Loading…"} />;
  }

  return (
    <>
      <PageHeader
        title={campaign.name}
        description={campaign.template_name ? `Template: ${campaign.template_name}` : "Campaign details"}
        back={{ href: "/campaigns", label: "Campaigns" }}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {campaign.status === "draft" && (
              <Button size="sm" onClick={() => void doAction(() => campaignsApi.send(id!))}>Send now</Button>
            )}
            {campaign.status === "sending" && (
              <Button size="sm" variant="secondary" onClick={() => void doAction(() => campaignsApi.pause(id!))}>Pause</Button>
            )}
            {campaign.status === "paused" && (
              <Button size="sm" variant="secondary" onClick={() => void doAction(() => campaignsApi.resume(id!))}>Resume</Button>
            )}
            <Button size="sm" variant="ghost" className="text-danger" onClick={() => void removeCampaign()} disabled={busy}>
              Delete
            </Button>
            <Button size="sm" variant="secondary" onClick={() => void refresh()} disabled={busy}>Refresh</Button>
          </div>
        }
      />

      {error && <div className="mb-4 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</div>}

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <Pill tone={STATUS_TONE[campaign.status]}>{STATUS_LABEL[campaign.status]}</Pill>
        <span className="text-sm text-muted">Audience: {campaign.target_list_name ?? "—"}</span>
        <span className="text-sm text-muted">Scheduled: {formatDateTime(campaign.scheduled_at)}</span>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel>
          <PanelHeader title="Campaign summary" description="The counts the backend keeps for this campaign." />
          <PanelBody>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {[
                { label: "Delivered", value: report?.delivered ?? 0 },
                { label: "Opened", value: `${report?.opened ?? 0} · ${formatPercent(report?.open_rate)}` },
                { label: "Clicked", value: `${report?.clicked ?? 0} · ${formatPercent(report?.click_rate)}` },
                { label: "Unsubscribed", value: report?.unsubscribed ?? 0 },
                { label: "Recipients", value: campaign.recipients.total },
                { label: "Reachable", value: `${campaign.reachable}/${campaign.audience}` },
              ].map((item) => (
                <div key={item.label} className="rounded border border-line bg-canvas p-3">
                  <div className="text-xs uppercase tracking-wide text-muted">{item.label}</div>
                  <div className="mt-2 text-xl font-semibold">{item.value}</div>
                </div>
              ))}
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Schedule" description="Move the campaign between draft and send-time." />
          <PanelBody>
            <form onSubmit={saveSchedule} className="space-y-4">
              <Field label="Scheduled at">
                {(p) => (
                  <Input
                    {...p}
                    type="datetime-local"
                    value={scheduledAt}
                    onChange={(e) => setScheduledAt(e.target.value)}
                  />
                )}
              </Field>
              <Button type="submit" size="sm" disabled={!scheduledAt || busy}>
                Save schedule
              </Button>
            </form>
          </PanelBody>
        </Panel>
      </div>

      {report && report.links.length > 0 && (
        <Panel className="mt-6">
          <PanelHeader title="Top links" description="Tracked clicks from the message." />
          <PanelBody>
            <ul className="space-y-2">
              {report.links.map((link) => (
                <li key={link.url} className="flex items-center justify-between gap-3 rounded border border-line px-3 py-2">
                  <span className="truncate text-sm text-ink">{link.url}</span>
                  <span className="text-sm text-muted">{link.recipients} clicks</span>
                </li>
              ))}
            </ul>
          </PanelBody>
        </Panel>
      )}
    </>
  );
}
