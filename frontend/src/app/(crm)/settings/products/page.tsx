"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { cn, formatDate } from "@/lib/utils";
import { money } from "@/modules/channels/ui";
import { orderCostsApi, urnsApi, type CostExtra, type ProductType, type RecalcRow, type UrnSize } from "@/modules/urns/api";
import { ExtrasPanel } from "@/modules/urns/ExtrasPanel";

const err = (e: unknown) => (e instanceof Error ? e.message : undefined);

/** Settings → Product settings: product types (each with its SKU format, sizes and extras), extra costs for every
 *  product, and bringing older orders' costs in line with the SKUs. */
export default function ProductSettingsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const canManage = can("channels:manage");
  const [types, setTypes] = useState<ProductType[]>([]);
  const [current, setCurrent] = useState<number | null>(null);
  const [extras, setExtras] = useState<CostExtra[]>([]);
  const [typeExtras, setTypeExtras] = useState<CostExtra[]>([]);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [t, e] = await Promise.all([urnsApi.types(), urnsApi.sharedExtras()]);
      setTypes(t);
      setExtras(e);
      setCurrent((c) => (c && t.some((x) => x.id === c) ? c : t[0]?.id ?? null));
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't load product settings", description: err(e) });
    }
  }, [toast]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!current) return;
    urnsApi.sharedExtras(current).then(setTypeExtras).catch(() => setTypeExtras([]));
  }, [current, types]);

  const type = types.find((t) => t.id === current) ?? null;
  const allSizes = types.flatMap((t) => t.sizes);

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const t = await urnsApi.addType({ name: newName.trim() });
      toast.push({ title: "Product type added", description: `${t.name} starts as one item, one price. Add sizes if it comes in sizes.` });
      setNewName("");
      await load();
      setCurrent(t.id);
    } catch (e2) {
      toast.push({ tone: "danger", title: "Couldn't add the type", description: err(e2) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Product settings" description="Product types with their own SKU format and sizes, and costs that apply to every product." />

      <Panel>
        <PanelHeader title="Product types" description="Each kind of product you sell has its own SKU format and sizes. A type without sizes is sold as one item at one price." />
        <PanelBody className="space-y-4">
          <div role="tablist" aria-label="Product types" className="flex flex-wrap gap-2">
            {types.map((t) => (
              <button key={t.id} type="button" role="tab" aria-selected={t.id === current} onClick={() => setCurrent(t.id)}
                className={cn("rounded-[var(--radius-control)] border px-3 py-1.5 text-sm",
                  t.id === current ? "border-accent bg-accent/10 font-semibold text-ink" : "border-line hover:bg-sand", !t.active && "opacity-60")}>
                {t.name} <span className="text-xs text-muted">· {t.products}</span>
              </button>
            ))}
          </div>
          {canManage && (
            <form onSubmit={add} className="flex flex-wrap items-end gap-2">
              <Field label="New product type">{(p) => <Input {...p} placeholder="Jewelry, Candles…" value={newName} maxLength={60} onChange={(e) => setNewName(e.target.value)} />}</Field>
              <Button type="submit" size="sm" disabled={busy || !newName.trim()}>Add type</Button>
            </form>
          )}
        </PanelBody>
      </Panel>

      {type && (
        <>
          <TypePanel key={type.id} type={type} canManage={canManage} onChange={() => void load()} />
          <SizesPanel type={type} canManage={canManage} onChange={() => void load()} />
          <ExtrasPanel urnId={null} typeId={type.id} extras={typeExtras} sizes={type.sizes} canManage={canManage}
            onChange={() => { void load(); }}
            title={`Extra costs for every ${type.name.toLowerCase()}`}
            description={`Added to or taken off the supplier price of every product of type ${type.name}. Minus amounts subtract.`} />
        </>
      )}

      <ExtrasPanel urnId={null} extras={extras} sizes={allSizes} canManage={canManage} onChange={() => void load()}
        title="Extra costs for every product" description="Whatever the type, e.g. a shipping box per order. Minus amounts subtract." />
      {canManage && <RecalculatePanel />}
    </div>
  );
}

function TypePanel({ type, canManage, onChange }: { type: ProductType; canManage: boolean; onChange: () => void }) {
  const toast = useToast();
  const [draft, setDraft] = useState({ name: type.name, code: type.code ?? "", template: type.template, size_format: type.size_format, separator: type.separator });
  const [check, setCheck] = useState<{ problems: string[]; examples: string[] }>({ problems: type.problems, examples: type.examples });
  const [busy, setBusy] = useState(false);
  const hasSizes = type.sizes.some((s) => s.active);
  const changed = draft.name !== type.name || draft.code !== (type.code ?? "") || draft.template !== type.template
    || draft.size_format !== type.size_format || draft.separator !== type.separator;

  useEffect(() => {
    const t = setTimeout(() => {
      urnsApi.checkType(type.id, { template: draft.template, size_format: draft.size_format, separator: draft.separator, code: draft.code })
        .then(setCheck).catch(() => undefined);
    }, 300);
    return () => clearTimeout(t);
  }, [draft.template, draft.size_format, draft.separator, draft.code, type.id]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await urnsApi.editType(type.id, { ...draft, code: draft.code.trim() || null });
      toast.push({ title: "Product type saved", description: `${draft.name}: its products' SKUs follow the new format in the CRM. Nothing was sent to Etsy.` });
      onChange();
    } catch (e2) {
      toast.push({ tone: "danger", title: "Couldn't save the type", description: err(e2) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title={`${type.name}: SKU format`}
        description={`${type.products} product${type.products === 1 ? "" : "s"} · ${hasSizes ? "comes in sizes" : "sold as one item, one price"}`}
        actions={canManage ? <Button size="sm" variant="ghost" disabled={busy}
          onClick={() => void urnsApi.editType(type.id, { active: !type.active }).then(onChange)}>{type.active ? "Turn off" : "Turn on"}</Button> : undefined} />
      <PanelBody>
        <form onSubmit={save} className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-6">
          <Field label="Name" className="sm:col-span-2">{(p) => <Input {...p} value={draft.name} maxLength={60} disabled={!canManage} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />}</Field>
          <Field label="Short code" hint="What {type} writes, e.g. U">{(p) => <Input {...p} className="font-mono" value={draft.code} maxLength={10} disabled={!canManage} onChange={(e) => setDraft({ ...draft, code: e.target.value.toUpperCase() })} />}</Field>
          <Field label="Template" className="sm:col-span-3"
            hint={`{supplier:3} supplier number · {product:4} product number${hasSizes ? " · {sizes} the pieces" : ""} · {type} the short code · {-option} reserved`}>
            {(p) => <Input {...p} className="font-mono" value={draft.template} maxLength={80} disabled={!canManage} onChange={(e) => setDraft({ ...draft, template: e.target.value })} />}
          </Field>
          {hasSizes && (
            <>
              <Field label="One size" hint="{code} and {qty}">{(p) => <Input {...p} className="font-mono" value={draft.size_format} maxLength={20} disabled={!canManage} onChange={(e) => setDraft({ ...draft, size_format: e.target.value })} />}</Field>
              <Field label="Between sizes">{(p) => <Input {...p} className="font-mono" value={draft.separator} maxLength={3} disabled={!canManage} onChange={(e) => setDraft({ ...draft, separator: e.target.value })} />}</Field>
            </>
          )}
          <div className="sm:col-span-6">
            {check.problems.length > 0 ? (
              <ul role="alert" className="space-y-1 text-sm text-danger">{check.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            ) : (
              <p className="text-sm text-muted">Examples: {check.examples.map((x) => <code key={x} className="mr-2 rounded bg-sand px-1.5 py-0.5 text-ink">{x}</code>)}</p>
            )}
          </div>
          {canManage && (
            <div className="flex gap-2 sm:col-span-6">
              <Button type="submit" size="sm" disabled={busy || !changed || !draft.name.trim() || check.problems.length > 0}>Save type</Button>
              {changed && <Button type="button" size="sm" variant="ghost"
                onClick={() => setDraft({ name: type.name, code: type.code ?? "", template: type.template, size_format: type.size_format, separator: type.separator })}>Undo changes</Button>}
            </div>
          )}
        </form>
      </PanelBody>
    </Panel>
  );
}

function SizesPanel({ type, canManage, onChange }: { type: ProductType; canManage: boolean; onChange: () => void }) {
  const sizes: UrnSize[] = type.sizes;
  const toast = useToast();
  const [editing, setEditing] = useState<number | null>(null);
  const [label, setLabel] = useState("");
  const [aliases, setAliases] = useState("");
  const [code, setCode] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [busy, setBusy] = useState(false);

  const act = async (fn: () => Promise<unknown>, title: string, description?: string) => {
    setBusy(true);
    try {
      await fn();
      toast.push({ title, description });
      setEditing(null);
      onChange();
    } catch (e) {
      toast.push({ tone: "danger", title: "That didn't work", description: err(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title={`${type.name}: sizes`} description={sizes.length ? "In the order they appear in a SKU. Words that mean a size in Etsy variation names help the CRM read them." : "None: each product of this type is one item at one price. Add a size if it comes in sizes."} />
      <PanelBody className="space-y-4">
        <ul className="divide-y divide-line">
          {sizes.map((s) => (
            <li key={s.id} className="py-3">
              {editing === s.id ? (
                <form className="grid grid-cols-[minmax(0,1fr)] gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]"
                  onSubmit={(e) => { e.preventDefault(); void act(() => urnsApi.editSize(s.id, { label, aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean) }), "Size saved", label); }}>
                  <Field label="Name">{(p) => <Input {...p} value={label} maxLength={40} onChange={(e) => setLabel(e.target.value)} />}</Field>
                  <Field label="Words that mean this size" hint="Separated by commas, e.g. large, adult">{(p) => <Input {...p} value={aliases} onChange={(e) => setAliases(e.target.value)} />}</Field>
                  <div className="flex items-end gap-1">
                    <Button type="submit" size="sm" disabled={busy || !label.trim()}>Save size</Button>
                    <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                  </div>
                </form>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 font-medium">{s.label} <code className="rounded bg-sand px-1.5 text-xs">{s.code}</code>{!s.active && <Badge>Off</Badge>}</div>
                    <div className="text-xs text-muted">{s.aliases.length ? `Also read from: ${s.aliases.join(", ")}` : "No extra words"}</div>
                  </div>
                  {canManage && (
                    <div className="flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => { setEditing(s.id); setLabel(s.label); setAliases(s.aliases.join(", ")); }}>Edit</Button>
                      <Button size="sm" variant="ghost" disabled={busy}
                        onClick={() => void act(() => urnsApi.editSize(s.id, { active: !s.active }), s.active ? "Size turned off" : "Size turned on", s.label)}>
                        {s.active ? "Turn off" : "Turn on"}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
        {canManage && (
          <form className="grid grid-cols-[minmax(0,1fr)] items-end gap-2 border-t border-line pt-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]"
            onSubmit={(e) => { e.preventDefault(); void act(() => urnsApi.addSize({ type_id: type.id, code: code.trim(), label: newLabel.trim() || `${code.trim()} inch` }), "Size added", code)
              .then(() => { setCode(""); setNewLabel(""); }); }}>
            <Field label="Code in the SKU" hint="E.g. 7">{(p) => <Input {...p} value={code} maxLength={10} onChange={(e) => setCode(e.target.value)} />}</Field>
            <Field label="Name">{(p) => <Input {...p} placeholder="7 inch" value={newLabel} maxLength={40} onChange={(e) => setNewLabel(e.target.value)} />}</Field>
            <Button type="submit" size="sm" disabled={busy || !code.trim()}>Add size</Button>
          </form>
        )}
      </PanelBody>
    </Panel>
  );
}

function RecalculatePanel() {
  const toast = useToast();
  const [rows, setRows] = useState<RecalcRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);

  const look = async () => {
    setBusy(true);
    try {
      setRows((await orderCostsApi.preview()).items);
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't check orders", description: err(e) });
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    if (!rows?.length) return;
    setBusy(true);
    try {
      const r = await orderCostsApi.apply(rows.map((x) => x.order_id));
      toast.push({ title: "Order costs updated", description: `${r.updated} orders now use their SKU costs.` });
      setConfirm(false);
      await look();
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't update the costs", description: err(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title="Older orders" description="Orders not yet paid to the supplier and not typed in by hand, whose SKU costs differ from what they show. Nothing changes until you apply."
        actions={<Button size="sm" variant="secondary" disabled={busy} onClick={() => void look()}>{rows ? "Check again" : "Check orders"}</Button>} />
      {rows && (
        <PanelBody className="space-y-3">
          {rows.length === 0 ? <p className="text-sm text-muted">Every order matches its SKU costs.</p> : (
            <>
              <div className="relative overflow-x-auto">
                <table className="w-full min-w-[520px] text-sm">
                  <caption className="sr-only">Orders whose costs would change</caption>
                  <thead><tr className="border-b border-line text-left text-xs uppercase text-muted">
                    <th scope="col" className="py-2">Order</th><th scope="col" className="py-2 text-right">Supplier now → new</th><th scope="col" className="py-2 text-right">Ours now → new</th>
                  </tr></thead>
                  <tbody>{rows.map((r) => (
                    <tr key={r.order_id} className="border-b border-line last:border-0">
                      <td className="py-2"><a href={`/channels/etsy/orders/${r.order_id}`} className="hover:underline">#{r.external_id}</a> <span className="text-xs text-muted">{formatDate(r.ordered_at)}</span></td>
                      <td className="num py-2 text-right">{money(r.purchase_cost)} → <strong>{money(r.new_purchase_cost)}</strong></td>
                      <td className="num py-2 text-right">{money(r.other_costs)} → <strong>{money(r.new_other_costs)}</strong></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <Button size="sm" disabled={busy} onClick={() => setConfirm(true)}>Use SKU costs on {rows.length} orders</Button>
            </>
          )}
        </PanelBody>
      )}
      <ConfirmDialog open={confirm} title="Update these orders' costs?" confirmLabel="Update costs" busy={busy}
        message={`${rows?.length ?? 0} orders will use their SKU costs. What the supplier is owed changes with them. Paid orders and hand-typed costs aren't touched.`}
        onConfirm={() => void apply()} onCancel={() => setConfirm(false)} />
    </Panel>
  );
}
