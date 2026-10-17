"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { customersApi, formatMoney, type Customer } from "./api";

/** Pick a duplicate and merge it into `customer` (managers and admins). */
export function MergeDialog({ customer, open, onClose, onMerged }: { customer: Customer; open: boolean; onClose: () => void; onMerged: (c: Customer) => void }) {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Customer[]>([]);
  const [picked, setPicked] = useState<Customer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setQ("");
      setResults([]);
      setPicked(null);
      setError(null);
    }
  }, [open]);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) return setResults([]);
    const t = setTimeout(() => {
      customersApi
        .list({ q: term, page_size: 8 })
        .then((page) => setResults(page.items.filter((c) => c.id !== customer.id)))
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, customer.id]);

  async function merge() {
    if (!picked) return;
    setBusy(true);
    setError(null);
    try {
      const merged = await customersApi.merge(customer.id, picked.id);
      toast.push({ title: "Customers merged", description: `${picked.display_name} was merged into ${merged.display_name}.` });
      onMerged(merged);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Merge a duplicate into ${customer.display_name}`}
      description="This customer is kept and its values win. Blank details are filled from the duplicate; its emails, tags, notes, activity and shop orders move here. The duplicate is deleted (managers can still find it under the Deleted filter)."
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button size="sm" variant="danger" disabled={!picked || busy} onClick={() => void merge()}>
            {busy ? "Merging…" : picked ? `Merge ${picked.display_name}` : "Merge"}
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <Field label="Find the duplicate" hint="Name, company, email or phone.">
          {(p) => <Input {...p} type="search" autoComplete="off" value={q} onChange={(e) => setQ(e.target.value)} />}
        </Field>
        {results.length > 0 && (
          <fieldset className="grid gap-2">
            <legend className="sr-only">Matching customers</legend>
            {results.map((c) => (
              <label key={c.id} className={`flex cursor-pointer items-start gap-3 rounded-[var(--radius-control)] border px-3 py-2 text-sm ${picked?.id === c.id ? "border-accent bg-accent-soft" : "border-line"}`}>
                <input
                  type="radio"
                  name="duplicate"
                  className="mt-0.5 size-4 accent-[var(--color-accent)] focus-visible:outline-2 focus-visible:outline-accent"
                  checked={picked?.id === c.id}
                  onChange={() => setPicked(c)}
                />
                <span className="min-w-0">
                  <span className="font-medium">
                    {c.display_name} <span className="text-muted">#{c.id}</span>
                  </span>
                  <span className="block truncate text-xs text-muted">
                    {[c.email, c.phone, c.company].filter(Boolean).join(" · ") || "No contact details"} · {c.orders_count} orders, {formatMoney(c.total_spent)}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
        )}
        {q.trim().length >= 2 && results.length === 0 && <p className="text-sm text-muted">No other customers match.</p>}
      </div>
    </Modal>
  );
}
