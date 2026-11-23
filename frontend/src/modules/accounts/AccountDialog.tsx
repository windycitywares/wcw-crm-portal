"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { useLookups } from "@/modules/settings/useLookups";
import { AccountPicker } from "./AccountPicker";
import { accountsApi, type Account, type AccountInput, type AccountStatus } from "./api";

const blank = { name: "", account_type: "", status: "active" as AccountStatus, industry: "", website: "", email: "", phone: "",
  city: "", country: "", notes: "", parent_id: null as number | null, parent_name: null as string | null };

/** Add or edit an account. Suppliers are edited on their own page (their account follows), so this is for the rest. */
export function AccountDialog({ open, account, defaultType, onClose, onSaved }: {
  open: boolean;
  account: Account | null;
  defaultType?: string;
  onClose: () => void;
  onSaved: (account: Account) => void;
}) {
  const toast = useToast();
  const lookups = useLookups();
  const [draft, setDraft] = useState(blank);
  const [saving, setSaving] = useState(false);
  const types = lookups.options("account_type", account?.account_type);

  useEffect(() => {
    if (!open) return;
    setDraft(account ? {
      name: account.name, account_type: account.account_type, status: account.status, industry: account.industry ?? "",
      website: account.website ?? "", email: account.email ?? "", phone: account.phone ?? "",
      city: account.address?.city ?? "", country: account.address?.country ?? "", notes: account.notes ?? "",
      parent_id: account.parent_id, parent_name: account.parent_name,
    } : { ...blank, account_type: defaultType ?? "" });
  }, [open, account, defaultType]);

  const set = (patch: Partial<typeof blank>) => setDraft((d) => ({ ...d, ...patch }));
  const type = draft.account_type || types[0]?.key || "";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.name.trim() || !type) return;
    setSaving(true);
    const data: AccountInput = {
      name: draft.name.trim(), account_type: type, status: draft.status, industry: draft.industry.trim() || null,
      website: draft.website.trim() || null, email: draft.email.trim() || null, phone: draft.phone.trim() || null,
      address: draft.city.trim() || draft.country.trim()
        ? { ...(account?.address ?? {}), city: draft.city.trim() || null, country: draft.country.trim() || null } : null,
      notes: draft.notes.trim() || null, parent_id: draft.parent_id,
    };
    try {
      const saved = account ? await accountsApi.update(account.id, data) : await accountsApi.create(data);
      toast.push({ title: account ? "Account saved" : "Account added", description: saved.name });
      onSaved(saved);
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't save the account", description: err instanceof Error ? err.message : undefined });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={account ? "Edit account" : "Add account"} size="md">
      <form onSubmit={submit} className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2">
        <Field label="Name" className="sm:col-span-2">{(p) => <Input {...p} required value={draft.name} onChange={(e) => set({ name: e.target.value })} />}</Field>
        <Field label="Type">
          {(p) => (
            <Select {...p} value={type} onChange={(e) => set({ account_type: e.target.value })}>
              {types.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Status">
          {(p) => (
            <Select {...p} value={draft.status} onChange={(e) => set({ status: e.target.value as AccountStatus })}>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </Select>
          )}
        </Field>
        <Field label="Industry">{(p) => <Input {...p} value={draft.industry} onChange={(e) => set({ industry: e.target.value })} />}</Field>
        <Field label="Website" hint="https://…">{(p) => <Input {...p} type="url" value={draft.website} onChange={(e) => set({ website: e.target.value })} />}</Field>
        <Field label="Email">{(p) => <Input {...p} type="email" value={draft.email} onChange={(e) => set({ email: e.target.value })} />}</Field>
        <Field label="Phone">{(p) => <Input {...p} type="tel" value={draft.phone} onChange={(e) => set({ phone: e.target.value })} />}</Field>
        <Field label="City">{(p) => <Input {...p} value={draft.city} onChange={(e) => set({ city: e.target.value })} />}</Field>
        <Field label="Country">{(p) => <Input {...p} value={draft.country} onChange={(e) => set({ country: e.target.value })} />}</Field>
        <AccountPicker label="Parent account" className="sm:col-span-2" value={draft.parent_id} currentName={draft.parent_name}
          exclude={account?.id} onChange={(id, name) => set({ parent_id: id, parent_name: name })} />
        <Field label="Notes" className="sm:col-span-2">{(p) => <Textarea {...p} rows={3} value={draft.notes} onChange={(e) => set({ notes: e.target.value })} />}</Field>
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          <Button type="submit" size="sm" disabled={saving || !draft.name.trim() || !type}>{saving ? "Saving…" : account ? "Save account" : "Add account"}</Button>
        </div>
      </form>
    </Modal>
  );
}
