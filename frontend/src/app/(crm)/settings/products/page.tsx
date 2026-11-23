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
import { formatDate } from "@/lib/utils";
import { money } from "@/modules/channels/ui";
import { orderCostsApi, urnsApi, type CostExtra, type RecalcRow, type SkuFormat, type UrnSize } from "@/modules/urns/api";
import { ExtrasPanel } from "@/modules/urns/ExtrasPanel";

const err = (e: unknown) => (e instanceof Error ? e.message : undefined);

/** Settings → Products: the sizes urns come in, the SKU format, extra costs for every urn, and bringing older
 *  orders' costs in line with the SKUs. */
export default function ProductSettingsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const canManage = can("channels:manage");
  const [sizes, setSizes] = useState<UrnSize[]>([]);
  const [extras, setExtras] = useState<CostExtra[]>([]);

  const load = useCallback(async () => {
    try {
      const [s, e] = await Promise.all([urnsApi.sizes(), urnsApi.sharedExtras()]);
      setSizes(s);
      setExtras(e);
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't load product settings", description: err(e) });
    }
  }, [toast]);
  useEffect(() => { void load(); }, [load]);

  return (
    <div className="space-y-5">
      <PageHeader title="Products" description="Sizes, the SKU format, and costs that apply to every urn." />
      <SkuFormatPanel canManage={canManage} />
      <SizesPanel sizes={sizes} canManage={canManage} onChange={() => void load()} />
      <ExtrasPanel urnId={null} extras={extras} sizes={sizes} canManage={canManage} onChange={() => void load()}
        title="Extra costs for every urn" description="E.g. packaging per piece or a box per order. A urn can add its own on its page. Minus amounts subtract." />
      {canManage && <RecalculatePanel />}
    </div>
  );
}

function SkuFormatPanel({ canManage }: { canManage: boolean }) {
  const toast = useToast();
  const [saved, setSaved] = useState<SkuFormat | null>(null);
  const [draft, setDraft] = useState({ template: "", size_format: "", separator: "" });
  const [check, setCheck] = useState<SkuFormat | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    urnsApi.format().then((f) => { setSaved(f); setCheck(f); setDraft({ template: f.template, size_format: f.size_format, separator: f.separator }); })
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!saved) return;
    const t = setTimeout(() => { urnsApi.checkFormat(draft).then(setCheck).catch(() => undefined); }, 300);
    return () => clearTimeout(t);
  }, [draft, saved]);

  const changed = saved && (draft.template !== saved.template || draft.size_format !== saved.size_format || draft.separator !== saved.separator);
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await urnsApi.saveFormat(draft);
      toast.push({ title: "SKU format saved", description: `${r.changed} SKUs in the CRM changed. Nothing was sent to Etsy.` });
      setSaved({ ...(saved as SkuFormat), ...draft });
    } catch (e2) {
      toast.push({ tone: "danger", title: "Couldn't save the format", description: err(e2) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title="SKU format" description="How every SKU is written. Changing it changes the SKUs in the CRM only — Etsy isn't touched." />
      <PanelBody>
        <form onSubmit={save} className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-[minmax(0,3fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <Field label="Template" hint="{supplier:3} supplier number · {urn:4} urn number · {sizes} the pieces · {-option} reserved for options">
            {(p) => <Input {...p} className="font-mono" value={draft.template} maxLength={80} disabled={!canManage} onChange={(e) => setDraft((d) => ({ ...d, template: e.target.value }))} />}
          </Field>
          <Field label="One size" hint="{code} and {qty}">
            {(p) => <Input {...p} className="font-mono" value={draft.size_format} maxLength={20} disabled={!canManage} onChange={(e) => setDraft((d) => ({ ...d, size_format: e.target.value }))} />}
          </Field>
          <Field label="Between sizes">
            {(p) => <Input {...p} className="font-mono" value={draft.separator} maxLength={3} disabled={!canManage} onChange={(e) => setDraft((d) => ({ ...d, separator: e.target.value }))} />}
          </Field>
          <div className="sm:col-span-3">
            {check && check.problems.length > 0 ? (
              <ul role="alert" className="space-y-1 text-sm text-danger">{check.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            ) : check && (
              <p className="text-sm text-muted">Examples: {check.examples.map((x) => <code key={x} className="mr-2 rounded bg-sand px-1.5 py-0.5 text-ink">{x}</code>)}</p>
            )}
          </div>
          {canManage && (
            <div className="flex gap-2 sm:col-span-3">
              <Button type="submit" size="sm" disabled={busy || !changed || Boolean(check?.problems.length)}>Save SKU format</Button>
              {changed && saved && <Button type="button" size="sm" variant="ghost"
                onClick={() => setDraft({ template: saved.template, size_format: saved.size_format, separator: saved.separator })}>Undo changes</Button>}
            </div>
          )}
        </form>
      </PanelBody>
    </Panel>
  );
}

function SizesPanel({ sizes, canManage, onChange }: { sizes: UrnSize[]; canManage: boolean; onChange: () => void }) {
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
      <PanelHeader title="Sizes" description="The sizes urns come in, in the order they appear in a SKU. Words that mean a size in Etsy variation names help the CRM read them." />
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
            onSubmit={(e) => { e.preventDefault(); void act(() => urnsApi.addSize({ code: code.trim(), label: newLabel.trim() || `${code.trim()} inch` }), "Size added", code)
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
