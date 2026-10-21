"use client";

import { useState } from "react";
import { Button } from "./Button";
import { Modal } from "./Modal";

/** "Are you sure?" dialog for destructive actions. The button names the action ("Delete contact"). */
export function ConfirmationDialog({ open, onClose, onConfirm, title, message, confirmLabel = "Delete", cancelLabel = "Cancel", variant = "danger" }: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title?: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "secondary";
}) {
  const [busy, setBusy] = useState(false);
  const handleConfirm = async () => {
    setBusy(true);
    try { await onConfirm(); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title={title ?? `Delete ${confirmLabel.toLowerCase()}?`} size="sm">
      <div className="space-y-2 text-sm">
        <p className="text-ink">{message}</p>
      </div>
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onClose} disabled={busy}>{cancelLabel}</Button>
        <Button variant={variant} size="sm" onClick={handleConfirm} disabled={busy} loading={busy}>
          {busy ? "Deleting…" : confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
