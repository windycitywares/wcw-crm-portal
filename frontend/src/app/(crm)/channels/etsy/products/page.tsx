"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { money, Stat, Thumb } from "@/modules/channels/ui";
import { urnsApi, type Needs, type Urn, type UrnSummary } from "@/modules/urns/api";
import { useSizes, useSupplierRecords, useTypes } from "@/modules/urns/useSupplierRecords";

const PAGE_SIZE = 50;

/** Products: every Etsy listing as a product with a supplier, a price per size and SKUs. The cards on top are the
 *  setup to-do list; each one filters the table to what still needs doing. */
export default function UrnsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const canEdit = can("channels:edit");
  const sizes = useSizes();
  const types = useTypes();
  const suppliers = useSupplierRecords();
  const [typeId, setTypeId] = useState<number | "">("");
  useEffect(() => { // ?type=<id> from Settings → Types
    const t = Number(new URLSearchParams(window.location.search).get("type"));
    if (t) setTypeId(t);
  }, []);
  const [bulkType, setBulkType] = useState("");
  const [summary, setSummary] = useState<UrnSummary | null>(null);
  const [needs, setNeeds] = useState<Needs>("");
  const [supplier, setSupplier] = useState<number | "">("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Urn> | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [bulkSupplier, setBulkSupplier] = useState("");
  const [confirmType, setConfirmType] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, d] = await Promise.all([urnsApi.summary(), urnsApi.list({ q, supplier_id: supplier, type_id: typeId, needs, page, page_size: PAGE_SIZE })]);
      setSummary(s);
      setData(d);
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't load products", description: err instanceof Error ? err.message : undefined });
    } finally {
      setLoading(false);
    }
  }, [q, supplier, typeId, needs, page, toast]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const t = setTimeout(() => { setQ(search.trim()); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const filter = (n: Needs) => { setNeeds((cur) => (cur === n ? "" : n)); setPage(1); setPicked(new Set()); };

  const setup = async () => {
    setBusy(true);
    try {
      const r = await urnsApi.setup();
      toast.push({ title: "Products set up", description: r.created ? `${r.created} new products from your listings; their variations were read.` : "Every listing already has a product; variations re-read." });
      await load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't set up products", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  };

  const assign = async () => {
    if (!picked.size) return;
    setBusy(true);
    try {
      const id = bulkSupplier ? Number(bulkSupplier) : null;
      const r = await urnsApi.assignSupplier([...picked], id);
      toast.push({ title: "Supplier assigned", description: `${r.updated} product${r.updated === 1 ? "" : "s"} → ${suppliers.find((s) => s.id === id)?.name ?? "no supplier"}.` });
      setPicked(new Set());
      await load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't assign the supplier", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  };

  const retype = async () => {
    if (!picked.size || !bulkType) return;
    setBusy(true);
    try {
      const r = await urnsApi.assignType([...picked], Number(bulkType));
      toast.push({ title: "Type set", description: `${r.updated} product${r.updated === 1 ? "" : "s"} → ${types.find((t) => t.id === Number(bulkType))?.name}. Their variations were read again.` });
      setPicked(new Set());
      await load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't set the type", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  };

  const priceText = (u: Urn) => {
    if (!u.has_sizes) return u.prices.item ? `${money(u.prices.item)} each` : null;
    const parts = Object.entries(u.prices).filter(([, v]) => v)
      .map(([code, v]) => `${sizes.find((s) => s.type_id === u.type_id && s.code === code)?.label ?? code} ${money(v)}`);
    return parts.length ? parts.join(" · ") : null;
  };

  const rows = data?.items ?? [];
  const allPicked = rows.length > 0 && rows.every((r) => picked.has(r.id));
  const toggle = (id: number) => setPicked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  const columns: Column<Urn>[] = [
    ...(canEdit ? [{
      key: "pick", header: <input type="checkbox" aria-label="Select every product on this page" checked={allPicked}
        onChange={() => setPicked(allPicked ? new Set() : new Set(rows.map((r) => r.id)))} />,
      cell: (u: Urn) => <input type="checkbox" aria-label={`Select ${u.name}`} checked={picked.has(u.id)} onChange={() => toggle(u.id)} />,
    }] : []),
    {
      key: "name", header: "Product",
      cell: (u) => (
        <div className="flex min-w-0 items-center gap-3">
          <Thumb src={u.image} />
          <div className="min-w-0">
            <Link href={`/channels/etsy/products/${u.id}`} className="font-medium text-ink hover:text-accent-strong hover:underline">{u.name}</Link>
            <div className="truncate text-xs text-muted">#{u.id}{u.listing_title ? ` · ${u.listing_title}` : ""}</div>
          </div>
        </div>
      ),
    },
    { key: "supplier", header: "Supplier", hide: "sm", cell: (u) => u.supplier_name ?? <Badge variant="warning">No supplier</Badge> },
    { key: "type", header: "Type", hide: "md", cell: (u) => u.type_name ?? "—" },
    { key: "prices", header: "Supplier price", hide: "md", cell: (u) => priceText(u) ?? <span className="text-xs text-muted">—</span> },
    {
      key: "vars", header: "Variations", hide: "md",
      cell: (u) => u.variations_unclear ? <Badge variant="danger">{u.variations_unclear} need you</Badge>
        : u.variations_open ? <Badge variant="warning">{u.variations_open} to check</Badge>
          : <Badge variant="success">{u.variations_total} approved</Badge>,
    },
    { key: "sku", header: "SKUs on Etsy", hide: "lg", cell: (u) => u.skus_differ ? <span className="text-xs text-warning">{u.skus_differ} differ</span> : <span className="text-xs text-muted">Match</span> },
  ];

  const s = summary;
  return (
    <div className="space-y-5">
      <PageHeader title="Products" description="Each Etsy listing as a product: its supplier, what one piece of each size costs, and the SKU of every variation."
        back={{ href: "/channels/etsy", label: "Etsy" }}
        actions={<div className="flex flex-wrap gap-2">
          <Link href="/channels/etsy/products/review" className="inline-flex items-center rounded-[var(--radius-control)] border border-line px-3 py-1.5 text-sm hover:bg-sand">Check variations</Link>
          <Link href="/channels/etsy/skus" className="inline-flex items-center rounded-[var(--radius-control)] border border-line px-3 py-1.5 text-sm hover:bg-sand">SKUs vs Etsy</Link>
        </div>} />

      {s && (
        <section aria-label="Setup" className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <div className="col-span-2 flex flex-col justify-between rounded-[var(--radius-card)] bg-surface p-4 shadow-[var(--shadow-card,0_0_0_1px_var(--color-line))] md:col-span-1">
            <span className="text-sm text-muted">Listings without a product</span>
            <span className="num font-admin mt-1 block text-2xl font-bold">{s.listings_without_urn}</span>
            {canEdit && <Button size="sm" className="mt-2" disabled={busy} onClick={() => void setup()}>{busy ? "Working…" : s.listings_without_urn ? "Create products" : "Re-read listings"}</Button>}
          </div>
          <Stat label="No supplier" value={s.no_supplier} tone={s.no_supplier ? "warning" : "success"} onClick={() => filter("supplier")} active={needs === "supplier"} sub="Needed for SKUs" />
          <Stat label="Variations to check" value={s.to_review} tone={s.unclear ? "danger" : s.to_review ? "warning" : "success"}
            sub={s.unclear ? `${s.unclear} need you` : "Read from Etsy"} onClick={() => filter("review")} active={needs === "review"} />
          <Stat label="No prices" value={s.no_prices} tone={s.no_prices ? "warning" : "success"} onClick={() => filter("prices")} active={needs === "prices"} sub="Needed for costs" />
          <Stat label="Ready" value={`${s.ready} / ${s.urns}`} tone={s.urns && s.ready === s.urns ? "success" : undefined} sub="Supplier, prices, all approved" onClick={() => filter("ready")} active={needs === "ready"} />
        </section>
      )}

      <Panel>
        <div className="grid grid-cols-[minmax(0,1fr)] items-end gap-3 p-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <Field label="Search">{(p) => <Input {...p} maxLength={120} type="search" placeholder="Product name or number" value={search} onChange={(e) => setSearch(e.target.value)} />}</Field>
          <Field label="Type">
            {(p) => (
              <Select {...p} value={String(typeId)} onChange={(e) => { setTypeId(e.target.value ? Number(e.target.value) : ""); setPage(1); }}>
                <option value="">All types</option>
                {types.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.products})</option>)}
              </Select>
            )}
          </Field>
          <Field label="Supplier">
            {(p) => (
              <Select {...p} value={String(supplier)} onChange={(e) => { setSupplier(e.target.value ? Number(e.target.value) : ""); setPage(1); }}>
                <option value="">All suppliers</option>
                {suppliers.map((x) => <option key={x.id} value={x.id}>{x.name} (#{x.id})</option>)}
              </Select>
            )}
          </Field>
        </div>
      </Panel>

      {canEdit && picked.size > 0 && (
        <div role="region" aria-label="Selected products" className="sticky top-2 z-10 flex flex-wrap items-end gap-3 rounded-[var(--radius-card)] bg-surface p-3 shadow-md ring-1 ring-accent">
          <span className="self-center text-sm font-medium">{picked.size} selected</span>
          <Field label="Supplier for the selected products">
            {(p) => (
              <Select {...p} value={bulkSupplier} onChange={(e) => setBulkSupplier(e.target.value)}>
                <option value="">No supplier</option>
                {suppliers.map((x) => <option key={x.id} value={x.id}>{x.name} (#{x.id})</option>)}
              </Select>
            )}
          </Field>
          <Button size="sm" disabled={busy} onClick={() => void assign()}>Assign supplier</Button>
          {types.length > 1 && (
            <>
              <Field label="Type for the selected products">
                {(p) => (
                  <Select {...p} value={bulkType} onChange={(e) => setBulkType(e.target.value)}>
                    <option value="">Choose a type</option>
                    {types.filter((t) => t.active).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </Select>
                )}
              </Field>
              <Button size="sm" variant="secondary" disabled={busy || !bulkType} onClick={() => setConfirmType(true)}>Set type</Button>
            </>
          )}
          <Button size="sm" variant="ghost" onClick={() => setPicked(new Set())}>Clear selection</Button>
        </div>
      )}

      <div className="relative">
        <DataTable caption="Products" columns={columns} rows={data ? rows : null} rowKey={(u) => u.id} loading={loading}
          empty={needs ? "Nothing here — this step is done." : "No products yet. Press “Create products” to make one for every Etsy listing."} />
      </div>
      {data && data.total > PAGE_SIZE && <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
      <ConfirmDialog open={confirmType} title="Change the type of these products?" confirmLabel="Set type" tone="primary" busy={busy}
        message={`${picked.size} product${picked.size === 1 ? "" : "s"} become ${types.find((t) => t.id === Number(bulkType))?.name ?? "the chosen type"}. Their variations are read again with that type's sizes (approved ones go back to “to check”) and they need prices for that type. Orders already costed keep their costs.`}
        onConfirm={() => { setConfirmType(false); void retype(); }} onCancel={() => setConfirmType(false)} />
    </div>
  );
}
