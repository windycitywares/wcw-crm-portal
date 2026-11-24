"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea, FieldActions } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/utils";
import { money, Thumb } from "@/modules/channels/ui";
import { STATE_BADGE, STATE_LABEL, urnsApi, type UrnDetail, type UrnVariation } from "@/modules/urns/api";
import { ExtrasPanel } from "@/modules/urns/ExtrasPanel";
import { useSupplierRecords, useTypes } from "@/modules/urns/useSupplierRecords";

const err = (e: unknown) => (e instanceof Error ? e.message : undefined);
type Run = (fn: () => Promise<unknown>, title: string, description?: string) => Promise<boolean>;

/** One product: its supplier, the supplier's price per size (dated), every Etsy variation with its pieces and SKU,
 *  and its extra costs. */
export default function UrnPage() {
  const { id } = useParams<{ id: string }>();
  const urnId = Number(id);
  const router = useRouter();
  const { can } = useAuth();
  const toast = useToast();
  const canEdit = can("channels:edit");
  const canManage = can("channels:manage");
  const types = useTypes();
  const suppliers = useSupplierRecords();
  const [urn, setUrn] = useState<UrnDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [drafts, setDrafts] = useState<Record<number, Record<string, string>>>({});
  const [showRemoved, setShowRemoved] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [retype, setRetype] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const u = await urnsApi.get(urnId);
      setUrn(u);
      setName(u.name);
      setNotes(u.notes ?? "");
      setDrafts({});
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't load the product", description: err(e) });
    }
  }, [urnId, toast]);
  useEffect(() => { void load(); }, [load]);

  const run: Run = async (fn, title, description) => {
    setBusy(true);
    try {
      await fn();
      toast.push({ title, description });
      await load();
      return true;
    } catch (e) {
      toast.push({ tone: "danger", title: "That didn't work", description: err(e) });
      return false;
    } finally {
      setBusy(false);
    }
  };

  const sizes = urn?.sizes ?? [];
  const active = urn?.has_sizes ? sizes.filter((s) => s.active) : [{ code: "item", label: "Items", active: true }];
  const draftFor = (v: UrnVariation) =>
    drafts[v.id] ?? Object.fromEntries(active.map((s) => [s.code, v.quantities[s.code] ? String(v.quantities[s.code]) : ""]));
  const setDraft = (v: UrnVariation, code: string, value: string) =>
    setDrafts((d) => ({ ...d, [v.id]: { ...draftFor(v), [code]: value } }));
  const dirty = (v: UrnVariation) => drafts[v.id] !== undefined;
  const quantities = (v: UrnVariation) =>
    Object.fromEntries(Object.entries(draftFor(v)).filter(([, q]) => Number(q) > 0).map(([c, q]) => [c, Number(q)]));

  const variations = useMemo(() => (urn?.variations ?? []).filter((v) => showRemoved || !v.removed), [urn, showRemoved]);
  const proposed = (urn?.variations ?? []).filter((v) => v.state === "proposed" && !v.removed);

  if (!urn) return <PageHeader title="Product" description="Loading…" back={{ href: "/channels/etsy/products", label: "Products" }} />;

  return (
    <div className="space-y-5">
      <PageHeader title={urn.name}
        description={`Product #${urn.id} · ${urn.type_name ?? "no type"}${urn.supplier_name ? ` · supplied by ${urn.supplier_name} (#${urn.supplier_id})` : ""}`}
        back={{ href: "/channels/etsy/products", label: "Products" }}
        actions={canManage ? <Button size="sm" variant="ghost" onClick={() => setDeleting(true)}>Delete product</Button> : undefined} />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Product" description="Its name in the CRM and who supplies it. The supplier's number goes into the SKU." />
          <PanelBody>
            <div className="mb-4 flex items-center gap-3">
              <Thumb src={urn.image} size="lg" />
              <div className="min-w-0 text-sm">
                <div className="text-muted">Etsy listing</div>
                {urn.listing_url
                  ? <a href={urn.listing_url} target="_blank" rel="noreferrer" className="line-clamp-2 text-accent-strong hover:underline">{urn.listing_title}</a>
                  : <span>{urn.listing_title ?? "—"}</span>}
                {urn.listing_state && urn.listing_state !== "active" && <Badge variant="warning">{urn.listing_state}</Badge>}
              </div>
            </div>
            <form className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2"
              onSubmit={(e) => { e.preventDefault(); void run(() => urnsApi.update(urn.id, { name, notes: notes || null }), "Product saved", name); }}>
              <Field label="Name">{(p) => <Input {...p} required value={name} maxLength={120} disabled={!canEdit} onChange={(e) => setName(e.target.value)} />}</Field>
              <Field label="Supplier" hint="Changing it changes this product's SKUs in the CRM.">
                {(p) => (
                  <Select {...p} value={urn.supplier_id ?? ""} disabled={!canEdit || busy}
                    onChange={(e) => void run(() => urnsApi.update(urn.id, { supplier_id: e.target.value ? Number(e.target.value) : null }), "Supplier saved")}>
                    <option value="">No supplier</option>
                    {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name} (#{s.id})</option>)}
                  </Select>
                )}
              </Field>
              <Field label="Product type" hint="Its SKU format and sizes come from the type.">
                {(p) => (
                  <Select {...p} value={urn.type_id} disabled={!canEdit || busy} onChange={(e) => setRetype(Number(e.target.value))}>
                    {types.filter((t) => t.active || t.id === urn.type_id).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </Select>
                )}
              </Field>
              <Field label="Notes" className="sm:col-span-2">{(p) => <Textarea {...p} maxLength={2000} rows={2} value={notes} disabled={!canEdit} onChange={(e) => setNotes(e.target.value)} />}</Field>
              {canEdit && <div className="sm:col-span-2"><Button type="submit" size="sm" loading={busy}>Save product</Button></div>}
            </form>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="Supplier price per piece" description="What one piece of each size costs. A new price applies from its date; older orders keep theirs." />
          <PanelBody className="space-y-4">
            {active.map((s) => <PriceRow key={s.code} urn={urn} code={s.code} label={urn.has_sizes ? s.label : "One item"} canManage={canManage} busy={busy} run={run} />)}
            {urn.price_history.length > 0 && (
              <details className="text-sm">
                <summary className="cursor-pointer text-muted">Price history ({urn.price_history.length})</summary>
                <ul className="mt-2 divide-y divide-line">
                  {urn.price_history.map((p) => (
                    <li key={p.id} className="flex items-center justify-between gap-2 py-1.5">
                      <span>{p.size_code === "item" ? "One item" : sizes.find((s) => s.code === p.size_code)?.label ?? p.size_code} · {money(p.amount)} from {formatDate(p.effective_from)}</span>
                      {canManage && <Button size="sm" variant="ghost" disabled={busy}
                        onClick={() => void run(() => urnsApi.removePrice(urn.id, p.id), "Price removed")}>Remove</Button>}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </PanelBody>
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="Variations and SKUs"
          description="How many pieces of each size every Etsy variation holds, read from its name. Check them, fix any that are wrong, and approve."
          actions={<div className="flex flex-wrap items-center gap-2">
            {urn.variations.some((v) => v.removed) && (
              <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={showRemoved} onChange={(e) => setShowRemoved(e.target.checked)} />Show removed</label>
            )}
            {canEdit && <Button size="sm" variant="secondary" disabled={busy}
              onClick={() => void run(() => urnsApi.refresh(urn.id), "Listing re-read", "New variations were read; approved ones were left as they are.")}>Re-read listing</Button>}
            {canEdit && proposed.length > 0 && <Button size="sm" disabled={busy}
              onClick={() => void run(() => urnsApi.approve({ urn_ids: [urn.id] }), "Variations approved", `${proposed.length} approved as read.`)}>Approve {proposed.length} as read</Button>}
          </div>} />
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <caption className="sr-only">Variations of {urn.name}</caption>
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <th scope="col" className="px-4 py-2 font-semibold">Etsy variation</th>
                {active.map((s) => <th key={s.code} scope="col" className="px-2 py-2 text-right font-semibold">{s.label}</th>)}
                <th scope="col" className="px-2 py-2 font-semibold">State</th>
                <th scope="col" className="px-2 py-2 font-semibold">SKU: CRM / on Etsy now</th>
                {canEdit && <th scope="col" className="px-4 py-2"><span className="sr-only">Save</span></th>}
              </tr>
            </thead>
            <tbody>
              {variations.map((v) => (
                <tr key={v.id} className={`border-b border-line last:border-0 ${v.removed ? "opacity-60" : ""}`}>
                  <td className="px-4 py-2">
                    <div className="font-medium">{v.label}</div>
                    {v.note && <div className="text-xs text-danger">{v.note}</div>}
                    {v.removed && <div className="text-xs text-muted">No longer on the listing</div>}
                  </td>
                  {active.map((s) => (
                    <td key={s.code} className="px-2 py-2 text-right">
                      {canEdit && !v.removed ? (
                        <>
                          <label className="sr-only" htmlFor={`q-${v.id}-${s.code}`}>{s.label} pieces in {v.label}</label>
                          <input id={`q-${v.id}-${s.code}`} type="number" min={0} max={500} inputMode="numeric"
                            className="num w-16 rounded-[var(--radius-control)] border border-line bg-surface px-2 py-1 text-right focus-visible:outline-2 focus-visible:outline-accent"
                            value={draftFor(v)[s.code] ?? ""} onChange={(e) => setDraft(v, s.code, e.target.value)} />
                        </>
                      ) : <span className="num">{v.quantities[s.code] ?? "—"}</span>}
                    </td>
                  ))}
                  <td className="px-2 py-2"><Badge variant={STATE_BADGE[v.state]}>{STATE_LABEL[v.state]}</Badge></td>
                  <td className="px-2 py-2 font-mono text-xs">
                    <div>{v.sku ?? <span className="font-sans text-muted">{urn.supplier_id ? "After approval" : "Needs a supplier"}</span>}</div>
                    <div className={v.etsy_sku && v.etsy_sku !== v.sku ? "text-warning" : "text-muted"}>{v.etsy_sku ?? "none on Etsy"}</div>
                  </td>
                  {canEdit && (
                    <td className="px-4 py-2 text-right">
                      {!v.removed && (dirty(v) || v.state !== "approved") && (
                        <Button size="sm" variant={dirty(v) ? "primary" : "secondary"} disabled={busy || Object.keys(quantities(v)).length === 0}
                          onClick={() => void run(() => urnsApi.setVariation(urn.id, v.id, quantities(v)), "Variation approved", v.label)}>
                          {dirty(v) ? "Save" : "Approve"}
                        </Button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
              {variations.length === 0 && (
                <tr><td colSpan={active.length + 4} className="px-4 py-6 text-center text-muted">No variations. Re-read the listing.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <ExtrasPanel urnId={urn.id} extras={urn.extras} sizes={sizes} canManage={canManage} onChange={() => void load()}
        description="Costs on top of the supplier price for this product, plus the ones for its type and for every product (Settings → Extra costs). Minus amounts subtract." />

      <ConfirmDialog open={retype !== null} title="Change this product's type?" confirmLabel="Change type" tone="primary" busy={busy}
        message={`${urn.name} becomes ${types.find((t) => t.id === retype)?.name ?? "another type"}. Its variations are read again with that type's sizes (approved ones go back to “to check”), its SKUs follow that type's format, and it needs prices for that type's sizes. Orders already costed keep their costs.`}
        onConfirm={() => { const id = retype; setRetype(null); if (id) void run(() => urnsApi.update(urn.id, { type_id: id }), "Type changed", types.find((t) => t.id === id)?.name); }}
        onCancel={() => setRetype(null)} />

      <ConfirmDialog open={deleting} title="Delete this product?" confirmLabel="Move to Trash" busy={busy}
        message={`${urn.name} goes to the Trash (restorable from Settings → Trash). New orders of its listing won't be costed from SKUs until it's restored.`}
        onConfirm={() => void run(() => urnsApi.remove(urn.id), "Product moved to the Trash", urn.name).then((ok) => { if (ok) router.push("/channels/etsy/products"); })}
        onCancel={() => setDeleting(false)} />
    </div>
  );
}

function PriceRow({ urn, code, label, canManage, busy, run }: {
  urn: UrnDetail; code: string; label: string; canManage: boolean; busy: boolean; run: Run;
}) {
  const [amount, setAmount] = useState("");
  const [from, setFrom] = useState("");
  const current = urn.prices[code];
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-medium">{label}</span>
        <span className="num text-lg font-semibold">{current ? money(current) : <span className="text-sm font-normal text-warning">Not set</span>}</span>
      </div>
      {canManage && (
        <form className="mt-2 grid grid-cols-[minmax(0,1fr)] items-start gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => urnsApi.setPrice(urn.id, { size_code: code, amount, effective_from: from || null }),
              "Price saved", `${label}: ${money(amount)} from ${from ? formatDate(from) : "today"}`)
              .then((ok) => { if (ok) { setAmount(""); setFrom(""); } });
          }}>
          <Field label={`New ${label} price`}>{(p) => <Input {...p} type="number" min="0" max="100000" step="0.01" inputMode="decimal" required value={amount} onChange={(e) => setAmount(e.target.value)} />}</Field>
          <Field label="From" hint="Empty = today">{(p) => <Input {...p} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />}</Field>
          <FieldActions><Button type="submit" size="sm" loading={busy}>Save price</Button></FieldActions>
        </form>
      )}
    </div>
  );
}
