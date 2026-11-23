"use client";

import { useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { trashApi } from "@/modules/trash/api";
import { suppliersApi, type Supplier } from "./api";

/** Delete a supplier: it goes to the Trash (restorable). If products or supplied products still point at it, say so
 *  first — they have to move to another supplier or be removed before it can go. */
export function DeleteSupplierDialog({ supplier, onClose, onDeleted }: {
  supplier: Pick<Supplier, "id" | "name"> | null; onClose: () => void; onDeleted: () => void;
}) {
  const toast = useToast();
  const [blockers, setBlockers] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setBlockers(null);
    if (!supplier) return;
    trashApi.blockers("supplier", supplier.id).then(setBlockers).catch(() => setBlockers([]));
  }, [supplier]);

  const blocked = Boolean(blockers && blockers.length);
  const remove = async () => {
    if (!supplier || blocked) return;
    setBusy(true);
    try {
      await suppliersApi.remove(supplier.id);
      toast.push({ title: "Supplier deleted", description: `${supplier.name} is in the Trash (Settings → Trash) and can be restored.` });
      onDeleted();
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't delete the supplier", description: e instanceof Error ? e.message : undefined });
    } finally {
      setBusy(false);
    }
  };

  const message = !supplier ? "" : blockers === null ? "Checking what still uses this supplier…"
    : blocked ? `${supplier.name} still has ${blockers.join(", ")}. Move them to another supplier or remove them first.`
      : `${supplier.name} goes to the Trash with its account; you can restore it from Settings → Trash.`;

  return (
    <ConfirmDialog open={supplier !== null} title={blocked ? "Can't delete this supplier yet" : "Delete this supplier?"}
      confirmLabel={blocked ? "OK" : "Delete supplier"} tone={blocked ? "primary" : "danger"} busy={busy || blockers === null} message={message}
      onConfirm={() => (blocked ? onClose() : void remove())} onCancel={onClose} />
  );
}
