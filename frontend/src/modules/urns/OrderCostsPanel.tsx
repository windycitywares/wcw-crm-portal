"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { formatDate } from "@/lib/utils";
import { money } from "@/modules/channels/ui";
import { orderCostsApi, type CostLine, type OrderCosts } from "./api";

const SOURCE: Record<string, string> = { sku: "From SKUs", listing: "From the listing's cost", manual: "Typed in by hand" };

function Lines({ lines }: { lines: CostLine[] }) {
  return (
    <ul className="divide-y divide-line text-sm">
      {lines.map((l, i) => (
        <li key={i} className="flex items-start justify-between gap-3 py-1.5">
          <span className="min-w-0">
            {l.label}
            <span className="ml-2 text-xs text-muted">{l.party === "supplier" ? "supplier" : "ours"}{l.kind === "adjustment" ? " · adjustment" : ""}</span>
          </span>
          <span className={`num shrink-0 ${Number(l.amount) < 0 ? "text-success" : ""}`}>{money(l.amount)}</span>
        </li>
      ))}
    </ul>
  );
}

/** How the order's cost was worked out from its SKUs: the supplier's prices on the order's date, extras, and the
 *  team's one-off adjustments — with "Use the SKU costs" to (re)apply them. */
export function OrderCostsPanel({ orderId, canEdit, onChanged }: { orderId: number; canEdit: boolean; onChanged: () => void }) {
  const toast = useToast();
  const [data, setData] = useState<OrderCosts | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [adj, setAdj] = useState({ label: "", amount: "", sign: "-", party: "supplier", note: "" });

  const load = useCallback(async () => {
    try {
      setData(await orderCostsApi.get(orderId));
    } catch {
      setData(null);
    }
  }, [orderId]);
  useEffect(() => { void load(); }, [load]);

  const act = async (fn: () => Promise<OrderCosts>, title: string, description?: string) => {
    setBusy(true);
    try {
      setData(await fn());
      toast.push({ title, description });
      onChanged();
      return true;
    } catch (e) {
      toast.push({ tone: "danger", title: "That didn't work", description: e instanceof Error ? e.message : undefined });
      return false;
    } finally {
      setBusy(false);
    }
  };

  if (!data) return null;
  const sku = data.source === "sku";
  const shown = sku && data.saved ? data.saved : data.live;
  const amount = Number(adj.amount);

  return (
    <Panel>
      <PanelHeader title="Cost breakdown"
        description={data.live.on ? `Supplier prices and extras in force on ${formatDate(data.live.on)}.` : "Worked out from the items' SKUs."}
        actions={data.source ? <Badge variant={sku ? "success" : data.source === "manual" ? "neutral" : "warning"}>{SOURCE[data.source]}</Badge> : undefined} />
      <PanelBody className="space-y-3">
        {shown.lines.length > 0 ? <Lines lines={shown.lines} /> : null}
        {data.live.missing.length > 0 && (
          <ul className="space-y-1 text-sm text-warning">{data.live.missing.map((m) => <li key={m}>{m}</li>)}</ul>
        )}
        {(shown.lines.length > 0) && (
          <dl className="grid grid-cols-2 gap-2 rounded-[var(--radius-control)] bg-sand/50 p-3 text-sm">
            <dt className="text-muted">Supplier's part (owed)</dt><dd className="num text-right font-semibold">{money(shown.supplier)}</dd>
            <dt className="text-muted">Our extra costs</dt><dd className="num text-right font-semibold">{money(shown.ours)}</dd>
          </dl>
        )}
        {data.locked && <p className="text-xs text-muted">The supplier has been paid for this order, so its costs are fixed.</p>}
        {canEdit && !data.locked && (
          <div className="flex flex-wrap gap-2">
            {data.live.complete && (!sku || data.differs) && (
              <Button size="sm" disabled={busy}
                onClick={() => void act(() => orderCostsApi.recalculate(orderId), "Costs from SKUs applied",
                  `Supplier ${money(data.live.supplier)}, ours ${money(data.live.ours)}.`)}>
                {sku ? "Update to today's SKU costs" : "Use the SKU costs"}
              </Button>
            )}
            {sku && !adding && <Button size="sm" variant="secondary" onClick={() => setAdding(true)}>Add adjustment</Button>}
          </div>
        )}
        {data.adjustments.length > 0 && (
          <div>
            <p className="mb-1 text-sm font-medium">Adjustments</p>
            <ul className="divide-y divide-line text-sm">
              {data.adjustments.map((a) => (
                <li key={a.id} className="flex items-start justify-between gap-3 py-1.5">
                  <span className="min-w-0">{a.label} <span className="text-xs text-muted">· {a.party === "supplier" ? "supplier" : "ours"} · {a.note}</span></span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="num">{money(a.amount)}</span>
                    {canEdit && !data.locked && <Button size="sm" variant="ghost" disabled={busy}
                      onClick={() => void act(() => orderCostsApi.removeAdjustment(orderId, a.id), "Adjustment removed", a.label)}>Remove</Button>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {adding && (
          <form className="grid grid-cols-[minmax(0,1fr)] gap-2 border-t border-line pt-3 sm:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              const value = (adj.sign === "-" ? -Math.abs(amount) : Math.abs(amount)).toFixed(2);
              void act(() => orderCostsApi.addAdjustment(orderId, { label: adj.label.trim(), amount: value, party: adj.party as "supplier" | "ours", note: adj.note.trim() }),
                "Adjustment added", `${adj.label.trim()}: ${money(value)}`).then((ok) => {
                if (ok) { setAdding(false); setAdj({ label: "", amount: "", sign: "-", party: "supplier", note: "" }); }
              });
            }}>
            <Field label="What">{(p) => <Input {...p} placeholder="Supplier refund, reshipping…" required value={adj.label} maxLength={120} onChange={(e) => setAdj({ ...adj, label: e.target.value })} />}</Field>
            <Field label="Adds or subtracts">
              {(p) => <Select {...p} value={adj.sign} onChange={(e) => setAdj({ ...adj, sign: e.target.value })}><option value="-">Subtracts (−)</option><option value="+">Adds (+)</option></Select>}
            </Field>
            <Field label="Amount ($)">{(p) => <Input {...p} type="number" min="0.01" max="100000" step="0.01" inputMode="decimal" required value={adj.amount} onChange={(e) => setAdj({ ...adj, amount: e.target.value })} />}</Field>
            <Field label="Whose">
              {(p) => <Select {...p} value={adj.party} onChange={(e) => setAdj({ ...adj, party: e.target.value })}><option value="supplier">Supplier's (changes what they're owed)</option><option value="ours">Ours (profit only)</option></Select>}
            </Field>
            <Field label="Why" className="sm:col-span-2">{(p) => <Input {...p} required value={adj.note} maxLength={500} onChange={(e) => setAdj({ ...adj, note: e.target.value })} />}</Field>
            <div className="flex gap-2 sm:col-span-2">
              <Button type="submit" size="sm" loading={busy}>Add adjustment</Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
            </div>
          </form>
        )}
      </PanelBody>
    </Panel>
  );
}
