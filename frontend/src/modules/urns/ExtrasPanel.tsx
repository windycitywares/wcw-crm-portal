"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Modal";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { formatDate } from "@/lib/utils";
import { urnsApi, type CostExtra, type UrnSize } from "./api";

/** In words: "−10% of the supplier price, per piece · supplier's" or "+$4.00 once per order · ours". */
export function describeExtra(e: CostExtra, sizes: UrnSize[]): string {
  const v = Number(e.value);
  const sign = v < 0 ? "−" : "+";
  const amount = e.mode === "percent" ? `${sign}${Math.abs(v)}% of the supplier price` : `${sign}$${Math.abs(v).toFixed(2)}`;
  const size = e.size_code ? sizes.find((s) => s.code === e.size_code)?.label ?? e.size_code : null;
  const per = e.applies === "order" ? "once per order" : size ? `per ${size} piece` : "per piece";
  return `${amount} ${per}`;
}

const blank = { name: "", value: "", sign: "+", mode: "amount", applies: "piece", size_code: "", party: "supplier", effective_from: "" };

/** Extra costs: what adds to or comes off the supplier price. `urnId` null = the ones for every urn. */
export function ExtrasPanel({ urnId, extras, sizes, canManage, onChange, title, description }: {
  urnId: number | null; extras: CostExtra[]; sizes: UrnSize[]; canManage: boolean; onChange: () => void;
  title?: string; description?: string;
}) {
  const toast = useToast();
  const [draft, setDraft] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [ending, setEnding] = useState<CostExtra | null>(null);
  const [showEnded, setShowEnded] = useState(false);
  const set = (patch: Partial<typeof blank>) => setDraft((d) => ({ ...d, ...patch }));
  const shown = extras.filter((e) => showEnded || e.active);

  const add = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const n = Number(draft.value);
    if (!draft.name.trim() || !n) return;
    setBusy(true);
    try {
      await urnsApi.addExtra({
        urn_id: urnId, name: draft.name.trim(), mode: draft.mode as CostExtra["mode"],
        value: String(draft.sign === "-" ? -Math.abs(n) : Math.abs(n)), applies: draft.applies as CostExtra["applies"],
        size_code: draft.applies === "piece" && draft.size_code ? draft.size_code : null, party: draft.party as CostExtra["party"],
        effective_from: draft.effective_from || null,
      });
      toast.push({ title: "Extra cost added", description: draft.name.trim() });
      setDraft(blank);
      onChange();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't add the extra cost", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  };

  const end = async () => {
    if (!ending) return;
    setBusy(true);
    try {
      await urnsApi.endExtra(ending.id);
      toast.push({ title: "Extra cost stopped", description: `${ending.name} no longer applies from today. Earlier orders keep it.` });
      setEnding(null);
      onChange();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't stop the extra cost", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title={title ?? "Extra costs"}
        description={description ?? "Added to or taken off the supplier price. The supplier's count in what they're owed; ours only in profit."}
        actions={extras.some((e) => !e.active) ? <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={showEnded} onChange={(e) => setShowEnded(e.target.checked)} />Show stopped</label> : undefined} />
      <PanelBody className="space-y-4">
        <ul className="divide-y divide-line">
          {shown.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 font-medium">
                  {e.name}
                  <Badge variant={e.party === "supplier" ? "info" : "neutral"}>{e.party === "supplier" ? "Supplier's" : "Ours"}</Badge>
                  {e.urn_id === null && urnId !== null && <Badge>Every urn</Badge>}
                  {!e.active && <Badge variant="warning">Stopped</Badge>}
                </div>
                <div className="text-xs text-muted">
                  {describeExtra(e, sizes)} · from {formatDate(e.effective_from)}{e.effective_to ? ` to ${formatDate(e.effective_to)}` : ""}
                </div>
              </div>
              {canManage && e.active && (e.urn_id === urnId) && (
                <Button size="sm" variant="ghost" disabled={busy} onClick={() => setEnding(e)}>Stop</Button>
              )}
            </li>
          ))}
          {shown.length === 0 && <li className="py-2 text-sm text-muted">No extra costs.</li>}
        </ul>
        {canManage && (
          <form onSubmit={add} className="grid grid-cols-[minmax(0,1fr)] gap-3 border-t border-line pt-4 sm:grid-cols-6">
            <Field label="Name" className="sm:col-span-2">{(p) => <Input {...p} placeholder="Packaging, supplier discount…" value={draft.name} maxLength={80} onChange={(e) => set({ name: e.target.value })} />}</Field>
            <Field label="Adds or subtracts">
              {(p) => <Select {...p} value={draft.sign} onChange={(e) => set({ sign: e.target.value })}><option value="+">Adds (+)</option><option value="-">Subtracts (−)</option></Select>}
            </Field>
            <Field label="Amount">{(p) => <Input {...p} type="number" min="0" step="0.01" inputMode="decimal" value={draft.value} onChange={(e) => set({ value: e.target.value })} />}</Field>
            <Field label="As">
              {(p) => <Select {...p} value={draft.mode} onChange={(e) => set({ mode: e.target.value, applies: e.target.value === "percent" ? "piece" : draft.applies })}><option value="amount">Dollars</option><option value="percent">% of supplier price</option></Select>}
            </Field>
            <Field label="Counted">
              {(p) => (
                <Select {...p} value={draft.applies} onChange={(e) => set({ applies: e.target.value })} disabled={draft.mode === "percent"}>
                  <option value="piece">Per piece</option><option value="order">Once per order</option>
                </Select>
              )}
            </Field>
            {draft.applies === "piece" && (
              <Field label="Pieces of">
                {(p) => (
                  <Select {...p} value={draft.size_code} onChange={(e) => set({ size_code: e.target.value })}>
                    <option value="">Any size</option>
                    {sizes.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
                  </Select>
                )}
              </Field>
            )}
            <Field label="Whose">
              {(p) => <Select {...p} value={draft.party} onChange={(e) => set({ party: e.target.value })}><option value="supplier">Supplier's (owed to them)</option><option value="ours">Ours (profit only)</option></Select>}
            </Field>
            <Field label="From" hint="Empty = today">{(p) => <Input {...p} type="date" value={draft.effective_from} onChange={(e) => set({ effective_from: e.target.value })} />}</Field>
            <div className="flex items-end sm:col-span-2">
              <Button type="submit" size="sm" disabled={busy || !draft.name.trim() || !Number(draft.value)}>Add extra cost</Button>
            </div>
          </form>
        )}
      </PanelBody>
      <ConfirmDialog open={ending !== null} title="Stop this extra cost?" confirmLabel="Stop extra cost" busy={busy}
        message={ending ? `${ending.name} won't apply to orders from today. Orders before today keep it.` : ""}
        onConfirm={() => void end()} onCancel={() => setEnding(null)} />
    </Panel>
  );
}
