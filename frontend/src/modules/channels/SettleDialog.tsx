"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { money } from "./ui";

const isoDate = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** Record a supplier payment for one order (any amount) or several (each at what it owes). Admins only. */
export function SettleDialog({
  open,
  orders,
  onClose,
  onDone,
}: {
  open: boolean;
  orders: { id: number; external_id: number; owed: string | null }[];
  onClose: () => void;
  onDone: () => void;
}) {
  const { push } = useToast();

  const total = orders.reduce((n, o) => n + Number(o.owed ?? 0), 0);
  const single = orders.length === 1;
  const [paidOn, setPaidOn] = useState(isoDate(new Date()));
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const ids = orders.map((o) => o.id).join(",");
  const firstOwed = orders[0]?.owed ?? "";
  useEffect(() => {
    if (open) {
      setPaidOn(isoDate(new Date()));
      setReference("");
      setNote("");
      setAmount(single ? firstOwed : "");
    }
    // Reset when the dialog opens for a (new) set of orders, not on every parent render.
  }, [open, single, ids, firstOwed]);

  const submit = async () => {
    setBusy(true);
    try {
      const changed = single && amount.trim() !== "" && Number(amount) !== Number(orders[0].owed);
      const r = await apiFetch<{ settled: number; total: string }>("/channels/etsy/supplier-payments/settle", {
        method: "POST",
        body: JSON.stringify({
          order_ids: orders.map((o) => o.id),
          paid_on: paidOn,
          reference: reference.trim() || null,
          note: note.trim() || null,
          amount: changed ? amount.trim() : null,
        }),
      });
      push({ title: "Marked paid", description: `${r.settled} order${r.settled === 1 ? "" : "s"} · ${money(r.total)}` });
      onDone();
      onClose();
    } catch (e) {
      push({ title: "Not marked paid", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={single ? `Mark order #${orders[0]?.external_id} paid` : `Mark ${orders.length} orders paid`}
      description={`Owed to the supplier: ${money(total)} (purchase cost + shipping cost). The order's costs don't change.`}
      footer={
        <>
          <Button size="sm" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={submit} disabled={busy || !paidOn}>{busy ? "Saving…" : "Mark paid"}</Button>
        </>
      }
    >
      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-2">
        <Field label="Paid on">{(p) => <Input {...p} type="date" value={paidOn} max={isoDate(new Date())} onChange={(e) => setPaidOn(e.target.value)} />}</Field>
        <Field label="Reference" hint="Invoice, PayPal or bank reference.">{(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={100} />}</Field>
        {single ? (
          <Field label="Amount paid ($)" hint="Change it only if you paid a different amount.">
            {(p) => <Input {...p} pattern="\d{0,9}(\.\d{1,2})?" title="A number like 12.50 (up to 2 decimal places)." maxLength={13} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />}
          </Field>
        ) : null}
        <div className={single ? "" : "sm:col-span-2"}>
          <Field label="Note (optional)">{(p) => <Input {...p} value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} />}</Field>
        </div>
      </div>
    </Modal>
  );
}
