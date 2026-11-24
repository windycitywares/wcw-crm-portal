"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { formatDate } from "@/lib/utils";
import { money } from "@/modules/channels/ui";
import { orderCostsApi, type RecalcRow } from "@/modules/urns/api";

const err = (e: unknown) => (e instanceof Error ? e.message : undefined);

/** Etsy → Orders → "Recalculate costs": orders not yet paid to the supplier and not typed in by hand whose SKU costs
 *  differ from what they show, side by side, and one confirmed step to bring them in line. Nothing changes before that. */
export function RecalculateCostsDialog({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone?: () => void }) {
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
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (open) { setRows(null); void look(); } }, [open]);

  const apply = async () => {
    if (!rows?.length) return;
    setBusy(true);
    try {
      const r = await orderCostsApi.apply(rows.map((x) => x.order_id));
      toast.push({ title: "Order costs updated", description: `${r.updated} orders now use their SKU costs.` });
      setConfirm(false);
      onDone?.();
      await look();
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't update the costs", description: err(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Modal open={open && !confirm} onClose={onClose} size="lg" title="Recalculate order costs"
        description="Orders not yet paid to the supplier and not typed in by hand, whose costs differ from what their SKUs work out to now — after you change prices, sizes or extra costs."
        footer={<>
          <Button variant="secondary" onClick={onClose}>Close</Button>
          {!!rows?.length && <Button loading={busy} onClick={() => setConfirm(true)}>Use SKU costs on {rows.length} {rows.length === 1 ? "order" : "orders"}</Button>}
        </>}>
        {rows === null ? <p className="text-sm text-muted">Checking orders…</p>
          : rows.length === 0 ? <p className="text-sm text-muted">Every order matches its SKU costs. Nothing to do.</p> : (
            <div className="relative overflow-x-auto">
              <table className="w-full min-w-[480px] text-sm">
                <caption className="sr-only">Orders whose costs would change</caption>
                <thead><tr className="border-b border-line text-left text-xs uppercase text-muted">
                  <th scope="col" className="py-2">Order</th>
                  <th scope="col" className="py-2 text-right">Supplier now → new</th>
                  <th scope="col" className="py-2 text-right">Ours now → new</th>
                </tr></thead>
                <tbody>{rows.map((r) => (
                  <tr key={r.order_id} className="border-b border-line last:border-0">
                    <td className="py-2"><Link href={`/channels/etsy/orders/${r.order_id}`} className="hover:underline">#{r.external_id}</Link> <span className="text-xs text-muted">{formatDate(r.ordered_at)}</span></td>
                    <td className="num py-2 text-right">{money(r.purchase_cost)} → <strong>{money(r.new_purchase_cost)}</strong></td>
                    <td className="num py-2 text-right">{money(r.other_costs)} → <strong>{money(r.new_other_costs)}</strong></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
      </Modal>
      <ConfirmDialog open={confirm} title="Update these orders' costs?" confirmLabel="Update costs" busy={busy}
        message={`${rows?.length ?? 0} orders will use their SKU costs. What the supplier is owed changes with them. Paid orders and hand-typed costs aren't touched.`}
        onConfirm={() => void apply()} onCancel={() => setConfirm(false)} />
    </>
  );
}
