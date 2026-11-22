"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { Segmented } from "@/components/ui/Segmented";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { channelsApi, type ChannelInfo, type EtsyConnection, type HandoverCheck, type HandoverResult } from "@/modules/channels/api";

const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 gap-y-0.5 py-2.5 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 text-right">{children}</dd>
    </div>
  );
}

function EtsyPanel() {
  const { can } = useAuth();
  const toast = useToast();
  const admin = can("channels:manage");
  const [conn, setConn] = useState<EtsyConnection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<{ ok: boolean; text: string } | null>(null);
  const [clientId, setClientId] = useState("");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    try {
      const c = await channelsApi.etsy.connection();
      setConn(c);
      setClientId((prev) => prev || c.client_id || "");
    } catch (e) {
      setError(errorText(e));
    }
  }, []);
  useEffect(() => {
    void load();
    const p = new URLSearchParams(window.location.search);
    if (p.get("etsy") === "connected") setOutcome({ ok: true, text: `Etsy is connected${p.get("shop") ? `: ${p.get("shop")}` : ""}.` });
    if (p.get("etsy") === "failed") setOutcome({ ok: false, text: `Etsy was not connected. ${p.get("reason") ?? ""}` });
  }, [load]);

  const save = async () => {
    setBusy(true);
    try {
      setConn(await channelsApi.etsy.saveCredentials(clientId.trim() || null, secret || null));
      setSecret("");
      toast.push({ title: "Etsy keys saved" });
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't save the Etsy keys", description: errorText(e) });
    } finally {
      setBusy(false);
    }
  };
  const connect = async () => {
    setBusy(true);
    try {
      window.location.href = (await channelsApi.etsy.connect()).url;
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't start connecting", description: errorText(e) });
      setBusy(false);
    }
  };
  const disconnect = async () => {
    setBusy(true);
    try {
      setConn(await channelsApi.etsy.disconnect());
      channelsApi.forget();
      toast.push({ title: "Etsy disconnected" });
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't disconnect", description: errorText(e) });
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      {outcome && <p role="status" className={outcome.ok ? "rounded-[var(--radius-control)] bg-success/12 px-4 py-3 text-sm text-success" : "rounded-[var(--radius-control)] bg-danger/12 px-4 py-3 text-sm text-danger"}>{outcome.text}</p>}
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <Panel>
        <PanelHeader title="Etsy connection" description="Listings and orders come in through Etsy's official API. Nothing is scraped, and buyers are only contacted through Etsy." />
        <PanelBody>
          {!conn ? <p className="text-sm text-muted">Loading…</p> : (
            <>
              <dl className="divide-y divide-line">
                <Row label="Status">{conn.connected ? <Pill tone="success">Connected</Pill> : <Pill tone="warning">Not connected</Pill>}</Row>
                {conn.connected && <Row label="Shop">{conn.shop_name}</Row>}
                {conn.connected_at && <Row label="Connected">{formatDateTime(conn.connected_at)}</Row>}
                {conn.connected && <Row label="Listings last synced">{conn.listings_synced_at ? formatDateTime(conn.listings_synced_at) : "Not yet"}</Row>}
                {conn.connected && <Row label="Orders last synced">{conn.orders_synced_at ? formatDateTime(conn.orders_synced_at) : "Not yet"}</Row>}
                {conn.last_error && <Row label="Last problem"><span className="text-danger">{conn.last_error}</span></Row>}
              </dl>
              {admin ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => void connect()} disabled={busy || !conn.client_id || !conn.secret_set}>
                    {conn.connected ? "Reconnect Etsy" : "Connect Etsy"}
                  </Button>
                  {conn.connected && <Button size="sm" variant="secondary" onClick={() => setConfirming(true)} disabled={busy}>Disconnect Etsy</Button>}
                </div>
              ) : <p className="mt-3 text-sm text-muted">Only an admin can connect or reconnect Etsy.</p>}
            </>
          )}
        </PanelBody>
      </Panel>
      {admin && conn && (
        <Panel>
          <PanelHeader title="Etsy app keys" description="From your app on Etsy's developer page. The shared secret is stored encrypted and never shown again." />
          <PanelBody className="grid grid-cols-[minmax(0,1fr)] gap-4">
            <Field label="Keystring">{(p) => <Input {...p} value={clientId} onChange={(e) => setClientId(e.target.value)} autoComplete="off" spellCheck={false} />}</Field>
            <Field label="Shared secret" hint={conn.secret_set ? "Saved. Type a new one only to replace it." : undefined}>
              {(p) => <Input {...p} type="password" value={secret} onChange={(e) => setSecret(e.target.value)} autoComplete="new-password" />}
            </Field>
            <div><Button size="sm" onClick={() => void save()} disabled={busy || !clientId.trim()}>Save Etsy keys</Button></div>
            <p className="text-sm text-muted">Add this exact callback URL to the Etsy app: <code className="break-all">{conn.redirect_uri}</code></p>
          </PanelBody>
        </Panel>
      )}
      {admin && conn?.connected && <ShopHandoverPanel />}
      <ConfirmDialog open={confirming} title="Disconnect Etsy?" confirmLabel="Disconnect Etsy" busy={busy}
        message="Syncing stops until you connect again. Orders and listings already brought in stay."
        onConfirm={() => void disconnect()} onCancel={() => setConfirming(false)} />
    </div>
  );
}

const CHECK_LABEL: Record<string, string> = {
  orders: "Orders", orders_with_cost: "Orders with a purchase cost", orders_with_supplier: "Orders with a supplier",
  orders_paid: "Orders the supplier was paid for",
};

/** The one-time copy of what the team entered on Etsy orders in the shop, checked by counts. */
function ShopHandoverPanel() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<HandoverResult | null>(null);
  const [check, setCheck] = useState<HandoverCheck | null>(null);
  useEffect(() => { void channelsApi.etsy.importCheck().then(setCheck).catch(() => setCheck(null)); }, []);
  const run = async () => {
    setBusy(true);
    try {
      const r = await channelsApi.etsy.importFromShop();
      setResult(r);
      setCheck(r.check);
      toast.push({ title: "Copied from the shop", description: `${r.orders} orders and ${r.listings} listings updated, ${r.events} history lines added.` });
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't copy from the shop", description: errorText(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Panel>
      <PanelHeader title="Copy Etsy work from the shop" description="Costs, suppliers, notes, tracking, supplier payments, statuses and history the team entered in the shop. Only fills what the CRM doesn't have yet, so running it again is safe." />
      <PanelBody className="grid gap-4">
        {check && (
          <div className="relative overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Shop and CRM counts</caption>
              <thead><tr className="text-left text-muted"><th className="py-1 font-medium">What</th><th className="py-1 text-right font-medium">Shop</th><th className="py-1 text-right font-medium">CRM</th></tr></thead>
              <tbody>
                {Object.keys(CHECK_LABEL).map((k) => (
                  <tr key={k} className="border-t border-line">
                    <td className="py-1.5">{CHECK_LABEL[k]}</td>
                    <td className="num py-1.5 text-right">{check.shop[k] ?? "—"}</td>
                    <td className={(check.crm[k] ?? 0) < (check.shop[k] ?? 0) ? "num py-1.5 text-right text-danger" : "num py-1.5 text-right"}>{check.crm[k] ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-sm">{check.matches ? <Pill tone="success">Everything is in the CRM</Pill> : <Pill tone="warning">Not copied yet</Pill>}</p>
          </div>
        )}
        {result && (result.orders_not_in_crm > 0 || result.suppliers_not_found.length > 0) && (
          <p className="text-sm text-muted">
            {result.orders_not_in_crm > 0 && `${result.orders_not_in_crm} shop orders are older than the CRM's Etsy history. `}
            {result.suppliers_not_found.length > 0 && `No supplier account for: ${result.suppliers_not_found.join(", ")}.`}
          </p>
        )}
        <div><Button size="sm" onClick={() => void run()} disabled={busy}>{busy ? "Copying…" : "Copy from the shop"}</Button></div>
      </PanelBody>
    </Panel>
  );
}

export default function SalesChannelsPage() {
  const [channels, setChannels] = useState<ChannelInfo[]>([]);
  const [tab, setTab] = useState("etsy");
  useEffect(() => { void channelsApi.list().then(setChannels).catch(() => setChannels([])); }, []);
  const current = channels.find((c) => c.key === tab);
  const options: { key: string; label: string }[] = channels.length ? channels : [{ key: "etsy", label: "Etsy" }];
  return (
    <>
      <PageHeader title="Sales channels" description="The external shops you sell on. Each one connected here shows under External shops in the sidebar." />
      <Segmented label="Marketplace" className="mb-6" value={tab} onChange={setTab}
        options={options.map((c) => ({ value: c.key, label: c.label }))} />
      {tab === "etsy" ? <EtsyPanel /> : (
        <Panel><PanelBody><p className="text-sm text-muted">{current?.label ?? "This marketplace"} isn&apos;t available yet. It will be set up here the same way as Etsy.</p></PanelBody></Panel>
      )}
    </>
  );
}
