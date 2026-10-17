"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { CustomFieldsEditor, type CustomValues } from "@/modules/records/CustomFields";
import { useDirectory } from "@/modules/records/useDirectory";
import { customFieldsApi, type FieldDef } from "@/modules/settings/api";
import { useLookups } from "@/modules/settings/useLookups";
import { NEXT_STATUSES, STATUS_LABEL, ticketPatch, ticketsApi, type Ticket, type TicketInput, type TicketStatus } from "./api";
import { CustomerPicker } from "./CustomerPicker";

interface Form {
  subject: string;
  description: string;
  ticket_type: string;
  priority: string;
  customer_id: number | null;
  customer_name: string | null;
  assignee_id: number | null;
  shop_order_id: string;
  status: TicketStatus;
}

/**
 * Add or edit a ticket. `customer` presets the customer when opened from a customer page; `onSaved`
 * gets the saved ticket so the opener can refresh.
 */
export function TicketDialog({
  open,
  ticket,
  customer,
  onClose,
  onSaved,
}: {
  open: boolean;
  ticket: Ticket | null;
  customer?: { id: number; name: string };
  onClose: () => void;
  onSaved: (saved?: Ticket) => void;
}) {
  const { user, can } = useAuth();
  const directory = useDirectory();
  const lookups = useLookups();
  const toast = useToast();
  const [form, setForm] = useState<Form | null>(null);
  const [values, setValues] = useState<CustomValues>({});
  const [defs, setDefs] = useState<FieldDef[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm({
      subject: ticket?.subject ?? "",
      description: ticket?.description ?? "",
      ticket_type: ticket?.ticket_type ?? "",
      priority: ticket?.priority ?? "normal",
      customer_id: ticket?.customer_id ?? customer?.id ?? null,
      customer_name: ticket?.customer_name ?? customer?.name ?? null,
      assignee_id: ticket?.assignee_id ?? user?.id ?? null,
      shop_order_id: ticket?.shop_order_id ? String(ticket.shop_order_id) : "",
      status: ticket?.status ?? "new",
    });
    setValues(ticket?.custom_fields ?? {});
    setError(null);
  }, [open, ticket, customer?.id, customer?.name, user?.id]);

  useEffect(() => {
    if (!open) return;
    customFieldsApi
      .list("ticket")
      .then(setDefs)
      .catch(() => setDefs([]));
  }, [open]);

  if (!form) return null;
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm({ ...form, [key]: value });
  const canAssign = can("tickets:assign");
  const owners = [...directory.people.values()]
    .filter((p) => p.is_active || p.id === form.assignee_id)
    .filter((p) => canAssign || p.id === user?.id || p.id === ticket?.assignee_id)
    .sort((a, b) => a.full_name.localeCompare(b.full_name));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    if (!form.subject.trim()) return setError("Give the ticket a subject.");
    setBusy(true);
    setError(null);
    const desired: TicketInput = {
      subject: form.subject.trim(),
      description: form.description.trim() || null,
      ticket_type: form.ticket_type || null,
      priority: form.priority,
      customer_id: form.customer_id,
      assignee_id: form.assignee_id,
      shop_order_id: form.shop_order_id ? Number(form.shop_order_id) : null,
      custom_fields: values,
    };
    try {
      if (ticket) {
        // Send only what changed: re-sending the priority would restart the SLA clock.
        const payload = ticketPatch(ticket, desired);
        if (form.status !== ticket.status) payload.status = form.status;
        if (Object.keys(payload).length === 0) {
          onClose();
          return;
        }
        const saved = await ticketsApi.update(ticket.id, payload);
        toast.push({ title: "Ticket saved", description: saved.number ?? saved.subject });
        onSaved(saved);
      } else {
        const saved = await ticketsApi.create(desired);
        toast.push({ title: "Ticket opened", description: saved.number ?? saved.subject });
        onSaved(saved);
      }
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!ticket) return;
    setBusy(true);
    try {
      await ticketsApi.remove(ticket.id);
      toast.push({ title: "Ticket deleted", description: ticket.number ?? ticket.subject });
      setDeleting(false);
      onSaved();
      onClose();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't delete", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  const statuses = ticket ? [ticket.status, ...NEXT_STATUSES[ticket.status]] : [];
  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        size="lg"
        title={ticket ? `Edit ${ticket.number ?? "ticket"}` : "New ticket"}
        description={ticket ? undefined : "Log a customer question, complaint or request."}
        footer={
          <>
            {ticket && (
              <Button variant="ghost" size="sm" className="mr-auto text-danger" onClick={() => setDeleting(true)}>
                Delete
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" form="ticket-form" size="sm" disabled={busy}>
              {busy ? "Saving…" : ticket ? "Save ticket" : "Open ticket"}
            </Button>
          </>
        }
      >
        <form id="ticket-form" onSubmit={save} className="grid gap-4 sm:grid-cols-2">
          {error && (
            <p role="alert" className="text-sm text-danger sm:col-span-2">
              {error}
            </p>
          )}
          <Field label="Subject" className="sm:col-span-2">
            {(p) => <Input {...p} required maxLength={200} autoFocus value={form.subject} onChange={(e) => set("subject", e.target.value)} />}
          </Field>
          <Field label="Customer" className="sm:col-span-2" hint="Optional — link the ticket to a customer to email replies and see it on their record.">
            {() => (
              <CustomerPicker
                value={form.customer_id}
                name={form.customer_name}
                onChange={(c) => setForm({ ...form, customer_id: c?.id ?? null, customer_name: c?.name ?? null })}
              />
            )}
          </Field>
          <Field label="Type">
            {(p) => (
              <Select {...p} value={form.ticket_type} onChange={(e) => set("ticket_type", e.target.value)}>
                <option value="">Not set</option>
                {lookups.options("ticket_type", ticket?.ticket_type).map((v) => (
                  <option key={v.key} value={v.key}>
                    {v.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Priority" hint="Sets the response-time target.">
            {(p) => (
              <Select {...p} value={form.priority} onChange={(e) => set("priority", e.target.value)}>
                {lookups.options("ticket_priority", ticket?.priority ?? "normal").map((v) => (
                  <option key={v.key} value={v.key}>
                    {v.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {ticket && (
            <Field label="Status">
              {(p) => (
                <Select {...p} value={form.status} onChange={(e) => set("status", e.target.value as TicketStatus)}>
                  {statuses.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABEL[s]}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          <Field label="Assigned to" hint={canAssign ? undefined : "Ask a manager to give a ticket to someone else."}>
            {(p) => (
              <Select
                {...p}
                value={form.assignee_id ?? ""}
                onChange={(e) => set("assignee_id", e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Unassigned</option>
                {owners.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.full_name}
                    {o.id === user?.id ? " (you)" : ""}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Shop order" hint="Optional order number from the shop.">
            {(p) => <Input {...p} inputMode="numeric" value={form.shop_order_id} onChange={(e) => set("shop_order_id", e.target.value.replace(/\D/g, ""))} />}
          </Field>
          <Field label="Details" className="sm:col-span-2" hint="What the customer asked for, in their words.">
            {(p) => <Textarea {...p} rows={4} maxLength={20000} value={form.description} onChange={(e) => set("description", e.target.value)} />}
          </Field>
          {defs.some((d) => d.is_active) && (
            <div className="grid gap-4 sm:col-span-2 sm:grid-cols-2">
              <CustomFieldsEditor defs={defs} values={values} onChange={setValues} />
            </div>
          )}
        </form>
      </Modal>
      <ConfirmDialog
        open={deleting}
        title="Delete this ticket?"
        message={`${ticket?.number ?? ""} and its messages will be removed from the queue.`}
        confirmLabel="Delete ticket"
        tone="danger"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setDeleting(false)}
      />
    </>
  );
}
