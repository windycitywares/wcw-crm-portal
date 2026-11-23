"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody } from "@/components/ui/Panel";
import { Segmented } from "@/components/ui/Segmented";
import { useToast } from "@/components/ui/Toast";
import { urnsApi, type SkuRow } from "@/modules/urns/api";

const STATUS: Record<SkuRow["status"], { label: string; badge: "success" | "warning" | "info" | "neutral" }> = {
  same: { label: "Same on Etsy", badge: "success" },
  different: { label: "Etsy differs", badge: "warning" },
  new: { label: "Not on Etsy yet", badge: "info" },
  not_ready: { label: "Not ready", badge: "neutral" },
};

function csv(rows: SkuRow[]): string {
  const esc = (v: string | number | null) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const head = ["Urn #", "Urn", "Etsy variation", "SKU on Etsy now", "SKU from the CRM", "Status"];
  return [head, ...rows.map((r) => [r.urn_id, r.urn_name, r.label, r.etsy_sku, r.crm_sku, STATUS[r.status].label])]
    .map((line) => line.map(esc).join(",")).join("\n");
}

/** The SKU each Etsy variation should carry next to the one it has now. Read-only: writing them to Etsy is
 *  switched off until the owner turns it on. */
export default function SkusPage() {
  const toast = useToast();
  const [show, setShow] = useState<"different" | "all">("different");
  const [rows, setRows] = useState<SkuRow[] | null>(null);
  const [pushEnabled, setPushEnabled] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await urnsApi.skuPreview(show === "different");
      setRows(r.items);
      setPushEnabled(r.etsy_push_enabled);
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't load SKUs", description: e instanceof Error ? e.message : undefined });
    }
  }, [show, toast]);
  useEffect(() => { void load(); }, [load]);

  const shared = useMemo(() => (rows ?? []).filter((r) => r.shared).length, [rows]);

  const download = () => {
    const blob = new Blob([csv(rows ?? [])], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `skus-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast.push({ title: "SKU list downloaded", description: `${rows?.length ?? 0} rows.` });
  };

  const columns: Column<SkuRow>[] = [
    { key: "urn", header: "Urn", cell: (r) => (
      <div className="min-w-0">
        <Link href={`/channels/etsy/urns/${r.urn_id}`} className="font-medium hover:text-accent-strong hover:underline">{r.urn_name}</Link>
        <div className="truncate text-xs text-muted">{r.label}</div>
      </div>
    ) },
    { key: "etsy", header: "On Etsy now", hide: "sm", cell: (r) => <span className="font-mono text-xs">{r.etsy_sku ?? "—"}</span> },
    { key: "crm", header: "From the CRM", cell: (r) => (
      <span className="font-mono text-xs">{r.crm_sku ?? <span className="font-sans text-muted">{r.state === "approved" ? "Needs a supplier" : "Approve the variation first"}</span>}
        {r.shared && <span className="ml-1 font-sans text-warning">(shared)</span>}</span>
    ) },
    { key: "status", header: "Status", hide: "md", cell: (r) => <Badge variant={STATUS[r.status].badge}>{STATUS[r.status].label}</Badge> },
  ];

  return (
    <div className="space-y-5">
      <PageHeader title="SKUs vs Etsy" description="The SKU every Etsy variation should carry, worked out from its urn, supplier and pieces, next to what Etsy has now."
        back={{ href: "/channels/etsy/urns", label: "Urns" }}
        actions={<div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" disabled={!rows?.length} onClick={download}>Download CSV</Button>
          <Button size="sm" disabled={!pushEnabled} title={pushEnabled ? undefined : "Switched off for now"}>Update SKUs on Etsy</Button>
        </div>} />

      {!pushEnabled && (
        <Panel>
          <PanelBody className="text-sm">
            <strong>Updating Etsy is switched off.</strong> The CRM keeps these SKUs and uses them to work out order costs and what
            suppliers are owed; nothing is sent to Etsy. When you want Etsy updated, ask for it to be turned on — you&apos;ll then
            reconnect Etsy once to allow editing listings, and see this list as a preview before anything is sent.
          </PanelBody>
        </Panel>
      )}
      {shared > 0 && (
        <p role="status" className="text-sm text-warning">
          {shared} variations share a SKU with another one in the same urn (e.g. two colours of the same size). Etsy accepts that only when they have the same stock.
        </p>
      )}

      <Segmented label="Show" value={show} onChange={(v) => setShow(v as "different" | "all")}
        options={[{ value: "different", label: "Different from Etsy" }, { value: "all", label: "All variations" }]} />
      <div className="relative">
        <DataTable caption="SKUs" columns={columns} rows={rows} rowKey={(r) => r.variation_id}
          empty={show === "different" ? "Every ready SKU already matches Etsy." : "No variations yet. Set up urns first."} />
      </div>
    </div>
  );
}
