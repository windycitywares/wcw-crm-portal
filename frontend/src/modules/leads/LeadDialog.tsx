"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { useDirectory } from "@/modules/records/useDirectory";
import { useLookups } from "@/modules/settings/useLookups";
import { leadPatch, leadsApi, WORKFLOW, STATUS_LABEL, type Lead, type LeadInput, type LeadOpenStatus } from "./api";

interface Form {
  first_name: string;
  last_name: string;
  company: string;
  email: string;
  phone: string;
  source: string;
  status: LeadOpenStatus;
  owner_id: string;
  notes: string;
}

/**
 * Add or edit a lead: who they are, where they came from, who is chasing them and how far along it is.
 * Converting (which makes the customer and the deal) has its own dialog — the button here opens it.
 */
export function LeadDialog({
  open,
  lead,
  onClose,
  onSaved,
  onConvert,
}: {
  open: boolean;
  lead: Lead | null;
  onClose: () => void;
  onSaved: () => void;
  /** Opens the convert dialog for this lead (the page owns it). */
  onConvert?: (lead: Lead) => void;
}) {
  const { user, can } = useAuth();
  const { people } = useDirectory();
  const lookups = useLookups();
  const toast = useToast();
  const [form, setForm] = useState<Form | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const converted = lead?.status === "converted";

  useEffect(() => {
    if (!open) return;
    setForm({
      first_name: lead?.first_name ?? "",
      last_name: lead?.last_name ?? "",
      company: lead?.company ?? "",
      email: lead?.email ?? "",
      phone: lead?.phone ?? "",
      source: lead?.source ?? "",
      // a converted lead has no open status left; showing "New" would be a lie and the API refuses it
      status: lead && lead.status !== "converted" ? lead.status : "new",
      owner_id: String(lead?.owner_id ?? user?.id ?? ""),
      notes: lead?.notes ?? "",
    });
    setError(null);
  }, [open, lead, converted, user?.id]);

  if (!form) return null;
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm({ ...form, [key]: value });
  const canAssign = can("sales:edit_any");
  const owners = [...people.values()]
    .filter((p) => p.is_active || String(p.id) === form.owner_id)
    .sort((a, b) => a.full_name.localeCompare(b.full_name));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    const data: LeadInput = {
      first_name: form.first_name.trim() || null,
      last_name: form.last_name.trim() || null,
      company: form.company.trim() || null,
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      source: form.source || null,
      notes: form.notes.trim() || null,
      owner_id: form.owner_id ? Number(form.owner_id) : null,
    };
    if (!converted) data.status = form.status;
    if (!data.first_name && !data.last_name && !data.company && !data.email && !data.phone) {
      return setError("Give the lead at least a name, company, email or phone.");
    }
    setBusy(true);
    setError(null);
    try {
      if (lead) await leadsApi.update(lead.id, leadPatch(lead, data));
      else await leadsApi.create(data);
      toast.push({ title: lead ? "Lead saved" : "Lead added", description: lead?.display_name ?? (data.company || data.email || undefined) });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!lead) return;
    setBusy(true);
    try {
      await leadsApi.remove(lead.id);
      toast.push({ title: "Lead deleted", description: lead.display_name });
      setDeleting(false);
      onSaved();
      onClose();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't delete", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={lead ? "Edit lead" : "Add a lead"}
        description={lead ? lead.display_name : "Someone who might become a customer."}
        footer={
          <>
            {lead && (
              <Button variant="ghost" size="sm" className="mr-auto text-danger" onClick={() => setDeleting(true)}>
                Delete
              </Button>
            )}
            {lead && !converted && onConvert && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  onClose();
                  onConvert(lead);
                }}
              >
                Convert…
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" form="lead-form" size="sm" disabled={busy}>
              {busy ? "Saving…" : lead ? "Save lead" : "Add lead"}
            </Button>
          </>
        }
      >
        <form id="lead-form" onSubmit={save} className="grid gap-4 sm:grid-cols-2">
          {error && (
            <p role="alert" className="text-sm text-danger sm:col-span-2">
              {error}
            </p>
          )}
          {converted && (
            <p className="text-sm text-muted sm:col-span-2">
              Converted {lead?.converted_customer_name ? `to ${lead.converted_customer_name}` : "to a customer"} — the
              customer and the deal are the live records now; notes here are kept for the history.
            </p>
          )}
          <Field label="First name">
            {(p) => <Input {...p} maxLength={80} autoFocus value={form.first_name} onChange={(e) => set("first_name", e.target.value)} />}
          </Field>
          <Field label="Last name">
            {(p) => <Input {...p} maxLength={80} value={form.last_name} onChange={(e) => set("last_name", e.target.value)} />}
          </Field>
          <Field label="Company">
            {(p) => <Input {...p} maxLength={160} value={form.company} onChange={(e) => set("company", e.target.value)} />}
          </Field>
          <Field label="Email">
            {(p) => <Input {...p} type="email" maxLength={320} value={form.email} onChange={(e) => set("email", e.target.value)} />}
          </Field>
          <Field label="Phone">
            {(p) => <Input {...p} maxLength={40} value={form.phone} onChange={(e) => set("phone", e.target.value)} />}
          </Field>
          <Field label="Source" hint="Where the lead came from.">
            {(p) => (
              <Select {...p} value={form.source} onChange={(e) => set("source", e.target.value)}>
                <option value="">Not set</option>
                {lookups.options("lead_source", lead?.source).map((v) => (
                  <option key={v.key} value={v.key}>
                    {v.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Status" hint={converted ? "Converted leads keep their status." : undefined}>
            {(p) => (
              <Select {...p} disabled={converted} value={form.status} onChange={(e) => set("status", e.target.value as LeadOpenStatus)}>
                {WORKFLOW.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Owner" hint={canAssign ? undefined : "Managers can give leads to someone else."}>
            {(p) => (
              <Select {...p} disabled={!canAssign} value={form.owner_id} onChange={(e) => set("owner_id", e.target.value)}>
                {owners.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.full_name}
                    {o.id === user?.id ? " (you)" : ""}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Notes" className="sm:col-span-2" hint="Optional.">
            {(p) => <Textarea {...p} rows={3} maxLength={20000} value={form.notes} onChange={(e) => set("notes", e.target.value)} />}
          </Field>
        </form>
      </Modal>
      <ConfirmDialog
        open={deleting}
        title="Delete this lead?"
        message={`“${lead?.display_name}” will be removed from the funnel${converted ? " (the customer and deal stay)" : ""}.`}
        confirmLabel="Delete lead"
        tone="danger"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setDeleting(false)}
      />
    </>
  );
}
