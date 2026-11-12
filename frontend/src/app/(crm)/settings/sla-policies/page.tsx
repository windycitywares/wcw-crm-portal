"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { IconButton, RowActions } from "@/components/ui/IconButton";
import { ColorTag } from "@/components/ui/ColorTag";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { errorText } from "@/modules/settings/api";
import { useLookups } from "@/modules/settings/useLookups";
import { formatBusinessMinutes, ticketsApi, type SlaPolicy, type SlaPolicyInput } from "@/modules/tickets/api";

interface Form {
  name: string;
  priority: string;
  ticket_type: string;
  response: string;
  resolve: string;
  is_active: boolean;
}

const hours = (minutes: number) => String(Math.round((minutes / 60) * 100) / 100);

/** Add or edit one response-time policy. Targets are entered in business hours (8 h = one day). */
function PolicyDialog({ open, policy, onClose, onSaved }: { open: boolean; policy: SlaPolicy | null; onClose: () => void; onSaved: () => void }) {
  const lookups = useLookups();
  const toast = useToast();
  const [form, setForm] = useState<Form | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setForm({
      name: policy?.name ?? "",
      priority: policy?.priority ?? "",
      ticket_type: policy?.ticket_type ?? "",
      response: policy ? hours(policy.first_response_minutes) : "4",
      resolve: policy ? hours(policy.resolve_minutes) : "16",
      is_active: policy?.is_active ?? true,
    });
    setError(null);
  }, [open, policy]);

  if (!form) return null;
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm({ ...form, [key]: value });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    if (!form.name.trim()) return setError("Give the policy a name.");
    setBusy(true);
    setError(null);
    const data: SlaPolicyInput = {
      name: form.name.trim(),
      priority: form.priority || null,
      ticket_type: form.ticket_type || null,
      first_response_minutes: Math.max(1, Math.round(Number(form.response || 0) * 60)),
      resolve_minutes: Math.max(1, Math.round(Number(form.resolve || 0) * 60)),
      is_active: form.is_active,
    };
    try {
      if (policy) await ticketsApi.updateSla(policy.id, data);
      else await ticketsApi.createSla(data);
      toast.push({ title: policy ? "Policy saved" : "Policy added", description: data.name });
      onSaved();
      onClose();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={policy ? "Edit SLA policy" : "New SLA policy"}
      description="The narrowest match wins: a policy with a priority beats a type-only one."
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="sla-form" size="sm" disabled={busy}>
            {busy ? "Saving…" : policy ? "Save policy" : "Add policy"}
          </Button>
        </>
      }
    >
      <form id="sla-form" onSubmit={save} className="grid gap-4 sm:grid-cols-2">
        {error && (
          <p role="alert" className="text-sm text-danger sm:col-span-2">
            {error}
          </p>
        )}
        <Field label="Name" className="sm:col-span-2">
          {(p) => <Input {...p} required maxLength={80} autoFocus value={form.name} onChange={(e) => set("name", e.target.value)} />}
        </Field>
        <Field label="Priority" hint="Optional.">
          {(p) => (
            <Select {...p} value={form.priority} onChange={(e) => set("priority", e.target.value)}>
              <option value="">Any priority</option>
              {lookups.options("ticket_priority", policy?.priority).map((v) => (
                <option key={v.key} value={v.key}>
                  {v.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Type" hint="Optional.">
          {(p) => (
            <Select {...p} value={form.ticket_type} onChange={(e) => set("ticket_type", e.target.value)}>
              <option value="">Any type</option>
              {lookups.options("ticket_type", policy?.ticket_type).map((v) => (
                <option key={v.key} value={v.key}>
                  {v.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="First reply (hours)" hint="8 hours = one business day.">
          {(p) => <Input {...p} type="number" min="0.25" step="0.25" value={form.response} onChange={(e) => set("response", e.target.value)} />}
        </Field>
        <Field label="Resolve within (hours)" hint="8 hours = one business day.">
          {(p) => <Input {...p} type="number" min="0.25" step="0.25" value={form.resolve} onChange={(e) => set("resolve", e.target.value)} />}
        </Field>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} />
          Active — new and re-prioritised tickets use this policy
        </label>
      </form>
    </Modal>
  );
}

export default function SlaPoliciesPage() {
  const { can } = useAuth();
  const toast = useToast();
  const lookups = useLookups();
  const [policies, setPolicies] = useState<SlaPolicy[] | null>(null);
  const [editing, setEditing] = useState<SlaPolicy | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    ticketsApi
      .slaPolicies()
      .then(setPolicies)
      .catch((err) => {
        setPolicies([]);
        toast.push({ tone: "danger", title: "Couldn't load SLA policies", description: errorText(err) });
      });
  }, [toast]);

  useEffect(() => {
    if (can("lookups:manage")) load();
  }, [load, can]);

  if (!can("lookups:manage")) return <PageHeader title="SLA policies" description="Only admins can change response-time targets." />;

  async function toggle(policy: SlaPolicy) {
    try {
      await ticketsApi.updateSla(policy.id, { is_active: !policy.is_active });
      toast.push({ title: policy.is_active ? "Policy paused" : "Policy active" });
      load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't update", description: errorText(err) });
    }
  }

  const columns: Column<SlaPolicy>[] = [
    {
      key: "policy",
      header: "Policy",
      cell: (p) => (
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{p.name}</span>
          {!p.is_active && <Pill>Paused</Pill>}
        </div>
      ),
    },
    {
      key: "applies",
      header: "Applies to",
      cell: (p) => {
        const priority = lookups.find("ticket_priority", p.priority);
        const type = lookups.find("ticket_type", p.ticket_type);
        return (
          <div className="flex flex-wrap items-center gap-2">
            {priority ? <ColorTag color={priority.color}>{priority.label}</ColorTag> : <span className="text-muted">Any priority</span>}
            {type ? <ColorTag color={type.color}>{type.label}</ColorTag> : <span className="text-muted">· any type</span>}
          </div>
        );
      },
    },
    { key: "response", header: "First reply", hide: "sm", cell: (p) => formatBusinessMinutes(p.first_response_minutes) },
    { key: "resolve", header: "Resolve", hide: "sm", cell: (p) => formatBusinessMinutes(p.resolve_minutes) },
    {
      key: "actions",
      header: "",
      align: "right",
      cell: (p) => (
        <RowActions>
          <IconButton icon={p.is_active ? "pause" : "play"} label={p.is_active ? `Pause ${p.name}` : `Resume ${p.name}`} onClick={() => void toggle(p)} />
          <IconButton icon="edit" label={`Edit ${p.name}`} onClick={() => setEditing(p)} />
        </RowActions>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="SLA policies"
        description="Response-time targets for tickets, counted in business hours (Admin → Business hours). The clock starts when a ticket is opened or re-prioritised."
        actions={
          <Button size="sm" onClick={() => setAdding(true)}>
            New policy
          </Button>
        }
      />
      <Panel>
        <DataTable
          columns={columns}
          rows={policies}
          rowKey={(p) => p.id}
          caption="SLA policies"
          empty="No policies yet. Add one to start tracking response times."
        />
      </Panel>
      <PolicyDialog open={adding || editing !== null} policy={editing} onClose={() => {
        setAdding(false);
        setEditing(null);
      }} onSaved={load} />
    </>
  );
}
