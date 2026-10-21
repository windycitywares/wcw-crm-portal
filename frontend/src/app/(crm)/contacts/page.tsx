"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";
import { contactsApi, type Contact, type ContactFilters, type ContactInput, type ContactStatus } from "@/modules/contacts/api";
import { useLookups } from "@/modules/settings/useLookups";

const PAGE_SIZE = 25;
const BLANK: ContactFilters = { q: "", type: "", status: "", owner: "any", sort: "-updated", page: 1 };

export default function ContactsPage() {
  const { can } = useAuth();
  const toast = useToast();
  const lookups = useLookups();
  const [filters, setFilters] = useState<ContactFilters>(BLANK);
  const [search, setSearch] = useState("");
  const [data, setData] = useState<Page<Contact> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [editing, setEditing] = useState<Contact | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null);

  const load = useCallback(async (f: ContactFilters) => {
    setLoading(true);
    setError(null);
    try {
      setData(await contactsApi.list({ ...f, page_size: PAGE_SIZE }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load contacts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) { setReady(true); return; }
    void load(filters);
  }, [filters, ready, load]);

  useEffect(() => {
    if (!ready || search === (filters.q ?? "")) return;
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search, page: 1 })), 300);
    return () => clearTimeout(t);
  }, [search, ready, filters.q]);

  const update = (patch: Partial<ContactFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  const handleDelete = useCallback((c: Contact) => {
    setDeleteTarget({ id: c.id, name: c.display_name });
  }, []);

  const handleDeleteConfirmed = useCallback(async () => {
    if (!deleteTarget) return;
    setDeletingId(deleteTarget.id);
    try {
      await contactsApi.delete(deleteTarget.id);
      toast.push({ title: "Contact deleted", description: `${deleteTarget.name} was removed.` });
      void load(filters);
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't delete", description: e instanceof Error ? e.message : undefined });
    } finally {
      setDeletingId(null);
      setDeleteTarget(null);
    }
  }, [deleteTarget, load, toast]);

  const typeOptions = lookups.options("contact_type");

  const columns: Column<Contact>[] = [
    {
      key: "name",
      header: "Contact",
      cell: (c) => (
        <div className="min-w-0">
          <button type="button" onClick={() => { setEditing(c); setShowForm(true); }}
            className="font-medium text-ink hover:text-accent-strong hover:underline">
            {c.display_name}
          </button>
          {c.company && c.display_name !== c.company && <div className="truncate text-xs text-muted">{c.company}</div>}
          {c.email && <div className="truncate text-xs text-muted">{c.email}</div>}
          {c.user_id && <div className="mt-0.5 text-xs text-muted">Staff user</div>}
          {c.customer_id && <div className="text-xs text-muted">Customer</div>}
        </div>
      ),
    },
    {
      key: "types",
      header: "Types",
      hide: "md",
      cell: (c) => (
        <div className="flex flex-wrap gap-1">
          {c.types.length ? c.types.map((t) => {
            const v = lookups.find("contact_type", t);
            return <Pill key={t} tone="neutral">{v ? v.label : t}</Pill>;
          }) : <span className="text-muted">—</span>}
        </div>
      ),
    },
    { key: "phone", header: "Phone", hide: "lg", cell: (c) => c.phone ?? <span className="text-muted">—</span> },
    { key: "status", header: "Status", hide: "md", cell: (c) => <Pill tone={c.status === "active" ? "success" : "neutral"}>{c.status}</Pill> },
  ];

  return (
    <div>
      <PageHeader title="Contacts" description="Every person the business deals with — staff, customers, vendors, leads. A person who is both staff and a customer is one row with both types." />
      <Panel className="mb-4">
        <div className="flex flex-wrap items-end gap-3 p-4">
          <Field label="Search" className="min-w-0 flex-1">
            {(p) => <Input {...p} type="search" placeholder="Name, company, email or phone" value={search} onChange={(e) => setSearch(e.target.value)} />}
          </Field>
          <Field label="Type">
            {(p) => (
              <Select {...p} value={filters.type ?? ""} onChange={(e) => update({ type: e.target.value })}>
                <option value="">All types</option>
                {typeOptions.map((v) => <option key={v.key} value={v.key}>{v.label}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Status">
            {(p) => (
              <Select {...p} value={filters.status ?? ""} onChange={(e) => update({ status: e.target.value })}>
                <option value="">All</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="blocked">Blocked</option>
              </Select>
            )}
          </Field>
          {can("customers:edit_own") && (
            <Button size="sm" onClick={() => { setEditing(null); setShowForm(true); }}>Add contact</Button>
          )}
        </div>
      </Panel>
      {error && <p className="mb-3 text-sm text-danger">{error}</p>}
      <DataTable
        columns={columns}
        rows={data?.items ?? null}
        rowKey={(c) => c.id}
        caption="Contacts"
        loading={loading}
        onEdit={(c) => { setEditing(c); setShowForm(true); }}
        onDelete={handleDelete}
        empty="No contacts match these filters."
      />
      {data && data.total > PAGE_SIZE && (
        <Pagination page={data.page} pageSize={data.page_size} total={data.total}
          onPage={(p) => setFilters((f) => ({ ...f, page: p }))} />
      )}
      <ContactDialog
        open={showForm}
        contact={editing}
        typeOptions={typeOptions}
        onClose={() => { setShowForm(false); setEditing(null); }}
        onSaved={() => { setShowForm(false); setEditing(null); void load(filters); }}
      />

      <ConfirmationDialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete contact"
        message={`Delete "${deleteTarget?.name}"? This can't be undone.`}
        onConfirm={handleDeleteConfirmed}
      />
    </div>
  );
}

function ContactDialog({ open, contact, typeOptions, onClose, onSaved }: {
  open: boolean; contact: Contact | null; typeOptions: { key: string; label: string }[];
  onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [company, setCompany] = useState("");
  const [title, setTitle] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [types, setTypes] = useState<string[]>(["other"]);
  const [status, setStatus] = useState<ContactStatus>("active");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!open) return;
    setFirst(contact?.first_name ?? "");
    setLast(contact?.last_name ?? "");
    setCompany(contact?.company ?? "");
    setTitle(contact?.title ?? "");
    setEmail(contact?.email ?? "");
    setPhone(contact?.phone ?? "");
    setTypes(contact?.types?.length ? contact.types : ["other"]);
    setStatus(contact?.status ?? "active");
    setNotes(contact?.notes ?? "");
  }, [open, contact]);

  const toggleType = (key: string) => setTypes((t) => t.includes(key) ? t.filter((x) => x !== key) : [...t, key]);

  const submit = async () => {
    if (types.length === 0) { toast.push({ title: "Pick at least one type", tone: "danger" }); return; }
    setSaving(true);
    const payload: ContactInput = { first_name: first || null, last_name: last || null, company: company || null,
      title: title || null, email: email || null, phone: phone || null, types, status, notes: notes || null };
    try {
      if (contact) await contactsApi.update(contact.id, payload);
      else await contactsApi.create(payload);
      toast.push({ title: contact ? "Contact updated" : "Contact added" });
      onSaved();
    } catch (e) {
      toast.push({ title: "Couldn't save", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={contact ? "Edit contact" : "Add contact"} size="md">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="First name">{(p) => <Input {...p} value={first} onChange={(e) => setFirst(e.target.value)} />}</Field>
        <Field label="Last name">{(p) => <Input {...p} value={last} onChange={(e) => setLast(e.target.value)} />}</Field>
        <Field label="Company">{(p) => <Input {...p} value={company} onChange={(e) => setCompany(e.target.value)} />}</Field>
        <Field label="Job title">{(p) => <Input {...p} value={title} onChange={(e) => setTitle(e.target.value)} />}</Field>
        <Field label="Email" className="sm:col-span-2">{(p) => <Input {...p} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
        <Field label="Phone">{(p) => <Input {...p} value={phone} onChange={(e) => setPhone(e.target.value)} />}</Field>
        <Field label="Status">
          {(p) => (
            <Select {...p} value={status} onChange={(e) => setStatus(e.target.value as ContactStatus)}>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="blocked">Blocked</option>
            </Select>
          )}
        </Field>
        <div className="sm:col-span-2">
          <p className="mb-1 text-sm font-medium">Types</p>
          <div className="flex flex-wrap gap-2">
            {typeOptions.map((v) => (
              <label key={v.key} className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" checked={types.includes(v.key)} onChange={() => toggleType(v.key)} />
                {v.label}
              </label>
            ))}
          </div>
        </div>
        <Field label="Notes" className="sm:col-span-2">
          {(p) => <textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)}
            className="min-h-[5rem] w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 py-2 text-sm" />}
        </Field>
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
        <Button size="sm" disabled={saving} onClick={submit}>{saving ? "Saving…" : (contact ? "Save" : "Add contact")}</Button>
      </div>
    </Modal>
  );
}
