"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill, type Tone } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { formatDateTime, timeAgo } from "@/lib/utils";
import { newSecret, shopApi, type ShopEvent, type ShopEventStatus, type ShopSettings, type ShopStatus } from "@/modules/integrations/api";
import { errorText, settingsApi } from "@/modules/settings/api";

const TONE: Record<ShopEventStatus, Tone> = { done: "success", failed: "danger", pending: "warning", ignored: "neutral" };
const LABEL: Record<ShopEventStatus, string> = { done: "Applied", failed: "Failed", pending: "Waiting", ignored: "Ignored" };

function CopyButton({ value, label }: { value: string; label: string }) {
  const toast = useToast();
  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      onClick={() =>
        navigator.clipboard
          .writeText(value)
          .then(() => toast.push({ title: `${label} copied` }))
          .catch(() => toast.push({ tone: "danger", title: "Couldn't copy", description: "Select the text and copy it by hand." }))
      }
    >
      Copy {label.toLowerCase()}
    </Button>
  );
}

export default function IntegrationsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const allowed = can("settings:manage");
  const [status, setStatus] = useState<ShopStatus | null>(null);
  const [form, setForm] = useState<{ enabled: boolean; shop_api_url: string; webhook_secret: string; shop_api_token: string } | null>(null);
  const [saved, setSaved] = useState<ShopSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<ShopEventStatus | "">("");
  const [page, setPage] = useState(1);
  const [events, setEvents] = useState<Page<ShopEvent> | null>(null);
  const [retrying, setRetrying] = useState<number | null>(null);

  const loadStatus = useCallback(() => shopApi.status().then(setStatus).catch(() => setStatus(null)), []);
  const loadEvents = useCallback(
    () =>
      shopApi
        .events(filter, page)
        .then(setEvents)
        .catch((err) => toast.push({ tone: "danger", title: "Couldn't load events", description: errorText(err) })),
    [filter, page, toast],
  );

  useEffect(() => {
    if (!allowed) return;
    void loadStatus();
    settingsApi
      .get<ShopSettings>("shop")
      .then(({ values }) => {
        setSaved(values);
        setForm({ enabled: values.enabled, shop_api_url: values.shop_api_url, webhook_secret: "", shop_api_token: "" });
      })
      .catch((err) => setError(errorText(err)));
  }, [allowed, loadStatus]);

  useEffect(() => {
    if (allowed) void loadEvents();
  }, [allowed, loadEvents]);

  if (!allowed) return <PageHeader title="Integrations" description="Only admins can change integrations." />;
  if (!form || !saved) return <PageHeader title="Integrations" description={error ?? "Loading…"} />;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      const { values } = await settingsApi.save<ShopSettings>("shop", form);
      setSaved(values);
      setForm({ ...form, webhook_secret: "", shop_api_token: "" });
      toast.push({ title: "Shop connection saved", description: values.enabled ? "The CRM now accepts events from the shop." : "Events from the shop are refused while it's off." });
      void loadStatus();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function retry(ev: ShopEvent) {
    setRetrying(ev.id);
    try {
      const res = await shopApi.retry(ev.id);
      toast.push(res.status === "done" ? { title: "Event applied" } : { tone: "danger", title: "Still failing", description: res.error ?? undefined });
      void loadEvents();
      void loadStatus();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't retry", description: errorText(err) });
    } finally {
      setRetrying(null);
    }
  }

  const columns: Column<ShopEvent>[] = [
    { key: "type", header: "Event", cell: (ev) => <code className="text-xs">{ev.event_type}</code> },
    { key: "status", header: "Result", cell: (ev) => <Pill tone={TONE[ev.status]}>{LABEL[ev.status]}</Pill> },
    {
      key: "customer",
      header: "Customer",
      hide: "sm",
      cell: (ev) =>
        ev.customer_id ? (
          <Link className="text-accent-strong underline" href={`/customers/${ev.customer_id}`}>
            #{ev.customer_id}
          </Link>
        ) : (
          <span className="text-muted">—</span>
        ),
    },
    { key: "received", header: "Received", hide: "md", cell: (ev) => <span title={formatDateTime(ev.received_at)}>{timeAgo(ev.received_at)}</span> },
    {
      key: "error",
      header: "Details",
      cell: (ev) =>
        ev.status === "failed" ? (
          <div className="grid gap-2">
            <span className="break-words text-xs text-danger">{ev.error}</span>
            <span className="text-xs text-muted">{ev.attempts} attempt{ev.attempts === 1 ? "" : "s"}</span>
            <Button size="sm" variant="secondary" disabled={retrying === ev.id} onClick={() => void retry(ev)}>
              {retrying === ev.id ? "Retrying…" : "Retry now"}
            </Button>
          </div>
        ) : (
          <span className="text-xs text-muted">{ev.processed_at ? `Applied ${formatDateTime(ev.processed_at)}` : ""}</span>
        ),
    },
  ];

  const counts = status?.counts ?? {};

  return (
    <>
      <PageHeader
        title="Integrations"
        description="Connections to Windy City Wares' other systems."
        actions={saved.enabled ? <Pill tone="success">Shop connected</Pill> : <Pill>Shop off</Pill>}
      />

      <form onSubmit={save} className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-2">
        {error && (
          <p role="alert" className="rounded-[var(--radius-control)] border border-danger/30 bg-danger/8 px-3 py-2 text-sm text-danger xl:col-span-2">
            {error}
          </p>
        )}
        <Panel>
          <PanelHeader
            title="Shop → CRM events"
            description="shop.windycitywares.com tells the CRM about new accounts, orders and newsletter sign-ups. Each message is signed with a secret both sides know."
          />
          <PanelBody className="grid gap-4">
            {status && (
              <div className="grid gap-2">
                <span className="text-sm font-medium">Webhook address (give this to the shop)</span>
                <code className="block break-all rounded-[var(--radius-control)] bg-sand px-3 py-2 text-xs">{status.webhook_url}</code>
                <div>
                  <CopyButton value={status.webhook_url} label="Address" />
                </div>
              </div>
            )}
            <Field
              label="Webhook secret"
              hint={
                form.webhook_secret
                  ? "Copy it now and set it in the shop as CRM_WEBHOOK_SECRET, then save. It won't be shown again."
                  : saved.webhook_secret_set
                    ? "Saved and encrypted. Generate a new one only if you also change it in the shop."
                    : "Not set yet. Generate one, copy it to the shop, then save."
              }
            >
              {(p) => (
                <Input {...p} readOnly value={form.webhook_secret} placeholder={saved.webhook_secret_set ? "••••••••" : ""} className="font-mono text-xs" />
              )}
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" variant="secondary" onClick={() => setForm({ ...form, webhook_secret: newSecret() })}>
                Generate secret
              </Button>
              {form.webhook_secret && <CopyButton value={form.webhook_secret} label="Secret" />}
            </div>
            <label className="flex items-center gap-3 text-sm font-medium">
              <input
                type="checkbox"
                className="size-4 accent-[var(--color-accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />
              Accept events from the shop
            </label>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Reading from the shop" description="Used to bring in past customers and show order history (coming next)." />
          <PanelBody className="grid gap-4">
            <Field label="Shop API address">
              {(p) => <Input {...p} value={form.shop_api_url} onChange={(e) => setForm({ ...form, shop_api_url: e.target.value })} autoComplete="off" />}
            </Field>
            <Field label="Shop API token" hint={saved.shop_api_token_set ? "Saved and encrypted. Leave blank to keep it." : "Made in the shop's admin. Stored encrypted."}>
              {(p) => (
                <Input
                  {...p}
                  type="password"
                  value={form.shop_api_token}
                  onChange={(e) => setForm({ ...form, shop_api_token: e.target.value })}
                  autoComplete="new-password"
                  placeholder={saved.shop_api_token_set ? "••••••••" : ""}
                />
              )}
            </Field>
          </PanelBody>
        </Panel>

        <div className="xl:col-span-2">
          <Button type="submit" size="sm" disabled={busy}>
            {busy ? "Saving…" : "Save shop connection"}
          </Button>
        </div>
      </form>

      <Panel className="mt-6">
        <PanelHeader
          title="Recent events"
          description={
            status
              ? `Last 24 hours: ${counts.done ?? 0} applied, ${counts.failed ?? 0} failed, ${counts.ignored ?? 0} ignored. ${
                  status.last_event_at ? `Last event ${timeAgo(status.last_event_at)}.` : "Nothing received yet."
                } Failed events are retried automatically every minute (5 tries).`
              : undefined
          }
          actions={
            <Field label="Show" className="min-w-40">
              {(p) => (
                <Select
                  {...p}
                  value={filter}
                  onChange={(e) => {
                    setFilter(e.target.value as ShopEventStatus | "");
                    setPage(1);
                  }}
                >
                  <option value="">All events</option>
                  <option value="failed">Failed</option>
                  <option value="done">Applied</option>
                  <option value="ignored">Ignored</option>
                  <option value="pending">Waiting</option>
                </Select>
              )}
            </Field>
          }
        />
        <div className="relative overflow-x-auto">
          <DataTable caption="Events received from the shop" columns={columns} rows={events?.items ?? null} rowKey={(ev) => ev.id} empty="No events yet." />
        </div>
      </Panel>
      {events && events.total > 20 && <Pagination className="mt-4" page={page} pageSize={20} total={events.total} onPage={setPage} />}
    </>
  );
}
