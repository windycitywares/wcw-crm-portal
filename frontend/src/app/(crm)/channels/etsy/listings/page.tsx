"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { LISTING_STATES, listingsApi, type Listing, type ListingFilters } from "@/modules/channels/api";
import { SupplierFilter, useSuppliers } from "@/modules/channels/SupplierFilter";

const PAGE_SIZE = 25;
const money = (v: string | null, currency = "USD") =>
  v === null ? "—" : new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(v));

function EditDialog({ listing, onClose, onSaved }: { listing: Listing | null; onClose: () => void; onSaved: (l: Listing) => void }) {
  const toast = useToast();
  const suppliers = useSuppliers();
  const [supplier, setSupplier] = useState("");
  const [cost, setCost] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!listing) return;
    setSupplier(listing.supplier_account_id ? String(listing.supplier_account_id) : "");
    setCost(listing.purchase_cost ?? "");
    setNotes(listing.notes ?? "");
  }, [listing]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!listing) return;
    setBusy(true);
    try {
      const saved = await listingsApi.update(listing.id, {
        supplier_account_id: supplier ? Number(supplier) : null, purchase_cost: cost.trim() || null, notes: notes.trim() || null,
      });
      toast.push({ title: "Listing saved", description: saved.title });
      onSaved(saved);
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save the listing", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={listing !== null} onClose={onClose} title="Supplier and cost" description={listing?.title} size="md">
      <form onSubmit={save} className="grid grid-cols-[minmax(0,1fr)] gap-3">
        <Field label="Supplier" hint="A supplier account. Add one under Purchasing → Suppliers.">
          {(p) => (
            <Select {...p} value={supplier} onChange={(e) => setSupplier(e.target.value)}>
              <option value="">No supplier</option>
              {suppliers.map((s) => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
              {listing?.supplier_account_id && !suppliers.some((s) => s.id === listing.supplier_account_id) && (
                <option value={String(listing.supplier_account_id)}>{listing.supplier_name ?? `Account #${listing.supplier_account_id}`}</option>
              )}
            </Select>
          )}
        </Field>
        <Field label="Purchase cost (per item)" hint="What one costs us. New orders of this listing start with it.">
          {(p) => <Input {...p} type="number" min="0" step="0.01" inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} />}
        </Field>
        <Field label="Notes">{(p) => <Textarea {...p} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
        <div className="flex justify-end gap-2">
          <Button type="button" size="sm" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" size="sm" disabled={busy}>{busy ? "Saving…" : "Save listing"}</Button>
        </div>
      </form>
    </Modal>
  );
}

export default function EtsyListingsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const [filters, setFilters] = useState<ListingFilters>({ q: "", state: "", supplier: "", page: 1 });
  const [search, setSearch] = useState("");
  const [data, setData] = useState<Page<Listing> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Listing | null>(null);
  const [syncing, setSyncing] = useState(false);
  const canEdit = can("channels:edit");

  const load = useCallback(async (f: ListingFilters) => {
    setLoading(true);
    setError(null);
    try {
      setData(await listingsApi.list({ ...f, page_size: PAGE_SIZE }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load listings");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void load(filters); }, [filters, load]);
  useEffect(() => {
    if (search === (filters.q ?? "")) return;
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search, page: 1 })), 300);
    return () => clearTimeout(t);
  }, [search, filters.q]);
  const update = (patch: Partial<ListingFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  const sync = async () => {
    setSyncing(true);
    try {
      const r = (await listingsApi.sync()).listings as { total?: number; error?: string; skipped?: string };
      if (r.error) toast.push({ tone: "danger", title: "Etsy didn't answer", description: r.error });
      else if (r.skipped) toast.push({ title: "Not synced", description: r.skipped === "not connected" ? "Connect Etsy in Settings → Sales channels." : r.skipped });
      else toast.push({ title: "Listings synced", description: `${r.total ?? 0} listings from Etsy.` });
      void load(filters);
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't sync", description: e instanceof Error ? e.message : undefined });
    } finally {
      setSyncing(false);
    }
  };

  const columns: Column<Listing>[] = [
    {
      key: "title", header: "Listing",
      cell: (l) => (
        <div className="flex min-w-0 items-center gap-3">
          {l.image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={l.image} alt="" className="size-12 shrink-0 rounded-[var(--radius-control)] object-cover" loading="lazy" />
          ) : <span aria-hidden="true" className="size-12 shrink-0 rounded-[var(--radius-control)] bg-sand" />}
          <div className="min-w-0">
            {l.url ? <a href={l.url} target="_blank" rel="noreferrer" className="line-clamp-2 font-medium text-ink hover:text-accent-strong hover:underline">{l.title}</a>
              : <span className="line-clamp-2 font-medium">{l.title}</span>}
            <div className="truncate text-xs text-muted">{l.skus.join(", ") || "No SKU"}{l.variations.length > 1 ? ` · ${l.variations.length} variations` : ""}</div>
          </div>
        </div>
      ),
    },
    { key: "state", header: "Status", hide: "md", cell: (l) => <Badge variant={l.state === "active" ? "success" : l.state === "removed" ? "danger" : "neutral"}>{LISTING_STATES[l.state] ?? l.state}</Badge> },
    { key: "price", header: "Price", align: "right", cell: (l) => <span className="num">{money(l.price, l.currency)}</span> },
    { key: "cost", header: "Our cost", align: "right", hide: "sm", cell: (l) => l.purchase_cost ? <span className="num">{money(l.purchase_cost, l.currency)}</span> : <span className="text-xs text-warning">Not set</span> },
    { key: "supplier", header: "Supplier", hide: "lg", cell: (l) => l.supplier_name ?? <span className="text-xs text-muted">—</span> },
    { key: "qty", header: "In stock", align: "right", hide: "lg", cell: (l) => l.quantity ?? "—" },
    ...(canEdit ? [{ key: "edit", header: <span className="sr-only">Edit</span>, align: "right" as const,
      cell: (l: Listing) => <Button size="sm" variant="secondary" onClick={() => setEditing(l)}>Edit</Button> }] : []),
  ];

  return (
    <div>
      <PageHeader title="Etsy listings" description="Your Etsy products as Etsy lists them (read-only), with the supplier and what each one costs you."
        back={{ href: "/channels/etsy", label: "Etsy" }}
        actions={canEdit ? <Button size="sm" variant="secondary" disabled={syncing} onClick={() => void sync()}>{syncing ? "Syncing…" : "Sync from Etsy"}</Button> : undefined} />
      <Panel className="mb-4">
        <div className="grid grid-cols-[minmax(0,1fr)] items-end gap-3 p-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <Field label="Search">{(p) => <Input {...p} type="search" placeholder="Title or SKU" value={search} onChange={(e) => setSearch(e.target.value)} />}</Field>
          <Field label="Status">
            {(p) => (
              <Select {...p} value={filters.state ?? ""} onChange={(e) => update({ state: e.target.value })}>
                <option value="">Any status</option>
                {Object.entries(LISTING_STATES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </Select>
            )}
          </Field>
          <SupplierFilter value={filters.supplier ?? ""} onChange={(supplier) => update({ supplier })} />
        </div>
      </Panel>
      {error && <p role="alert" className="mb-3 text-sm text-danger">{error}</p>}
      <div className="relative">
        <DataTable columns={columns} rows={data?.items ?? null} rowKey={(l) => l.id} caption="Etsy listings" loading={loading}
          empty="No listings yet. Connect Etsy in Settings → Sales channels, then sync." />
      </div>
      {data && data.total > PAGE_SIZE && (
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(p) => setFilters((f) => ({ ...f, page: p }))} />
      )}
      <EditDialog listing={editing} onClose={() => setEditing(null)}
        onSaved={(l) => { setEditing(null); setData((d) => d && { ...d, items: d.items.map((x) => (x.id === l.id ? l : x)) }); }} />
    </div>
  );
}
