"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/utils";
import { CustomerPicker } from "@/modules/tickets/CustomerPicker";
import { useDirectory } from "@/modules/records/useDirectory";
import { useLookups } from "@/modules/settings/useLookups";
import { dealPatch, salesApi, STATUS_LABEL, STATUS_TONE, type Deal, type DealInput, type Pipeline } from "./api";

interface Form {
  title: string;
  pipeline_id: string;
  stage_id: string;
  value: string;
  currency: string;
  probability: string;
  expected_close_on: string;
  source: string;
  lost_reason: string;
  owner_id: string;
  description: string;
}

/** "Proposal · 50%", "Won · wins the deal" — stage options say what picking one will do. */
function stageLabel(name: string, probability: number, is_won: boolean, is_lost: boolean) {
  const ending = is_won ? " · wins the deal" : is_lost ? " · loses the deal" : ` · ${probability}%`;
  return `${name}${ending}`;
}

/**
 * Add or edit a deal. The stage is what decides the outcome: picking a stage flagged as the won or lost
 * column marks the deal won or lost, and the stage's probability becomes the deal's.
 */
export function DealDialog({
  open,
  deal,
  pipelines,
  customer,
  onClose,
  onSaved,
}: {
  open: boolean;
  deal: Deal | null;
  /** The boards, so the stage picker can list them. */
  pipelines: Pipeline[];
  /** Set when opening from a customer's page, so a new deal starts linked to them. */
  customer?: { id: number; name: string };
  onClose: () => void;
  onSaved: () => void;
}) {
  const { user, can } = useAuth();
  const { people } = useDirectory();
  const lookups = useLookups();
  const toast = useToast();
  const [form, setForm] = useState<Form | null>(null);
  const [picked, setPicked] = useState<{ id: number; name: string } | null>(null);
  const [touchedProbability, setTouchedProbability] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fallbackId = (pipelines.find((p) => p.is_default) ?? pipelines[0])?.id;
  const customerId = customer?.id ?? null;
  const customerName = customer?.name ?? null;

  useEffect(() => {
    if (!open) return;
    const pipeline = pipelines.find((p) => p.id === deal?.pipeline_id) ?? pipelines.find((p) => p.id === fallbackId);
    setForm({
      title: deal?.title ?? "",
      pipeline_id: String(pipeline?.id ?? ""),
      stage_id: String(deal?.stage_id ?? pipeline?.stages[0]?.id ?? ""),
      value: deal ? String(Number(deal.value)) : "",
      currency: deal?.currency ?? "USD",
      probability: String(deal?.probability ?? pipeline?.stages[0]?.probability ?? 0),
      expected_close_on: deal?.expected_close_on ?? "",
      source: deal?.source ?? "",
      lost_reason: deal?.lost_reason ?? "",
      owner_id: String(deal?.owner_id ?? user?.id ?? ""),
      description: deal?.description ?? "",
    });
    setPicked(
      deal?.customer_id
        ? { id: deal.customer_id, name: deal.customer_name ?? `Customer #${deal.customer_id}` }
        : customerId
          ? { id: customerId, name: customerName ?? `Customer #${customerId}` }
          : null,
    );
    setTouchedProbability(false);
    setError(null);
  }, [open, deal, pipelines, fallbackId, customerId, customerName, user?.id]);

  if (!form) return null;
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm({ ...form, [key]: value });
  const stages = pipelines.find((p) => p.id === Number(form.pipeline_id))?.stages ?? [];
  const stage = stages.find((s) => s.id === Number(form.stage_id));
  const canAssign = can("sales:edit_any");
  const owners = [...people.values()].filter((p) => p.is_active || String(p.id) === form.owner_id).sort((a, b) => a.full_name.localeCompare(b.full_name));

  function pickPipeline(id: string) {
    const next = pipelines.find((p) => p.id === Number(id));
    setForm((f) => (f ? { ...f, pipeline_id: id, stage_id: String(next?.stages[0]?.id ?? ""), probability: String(next?.stages[0]?.probability ?? 0) } : f));
    setTouchedProbability(false);
  }

  function pickStage(id: string) {
    const next = stages.find((s) => s.id === Number(id));
    setForm((f) => (f ? { ...f, stage_id: id, probability: touchedProbability ? f.probability : String(next?.probability ?? 0) } : f));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    if (!form.title.trim()) return setError("Give the deal a title.");
    if (!form.stage_id) return setError("Choose the stage this deal is on.");
    setBusy(true);
    setError(null);
    const moved = deal ? Number(form.stage_id) !== deal.stage_id : true;
    const data: DealInput = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      customer_id: picked?.id ?? null,
      stage_id: Number(form.stage_id),
      value: form.value.trim() === "" ? 0 : form.value.trim(),
      currency: form.currency.trim().toUpperCase() || "USD",
      expected_close_on: form.expected_close_on || null,
      source: form.source || null,
      lost_reason: form.lost_reason || null,
      owner_id: form.owner_id ? Number(form.owner_id) : null,
    };
    // Let the stage choose the probability unless the person set one themselves (or isn't moving it).
    if (!deal || touchedProbability || !moved) data.probability = Number(form.probability);
    try {
      if (deal) await salesApi.updateDeal(deal.id, dealPatch(deal, data));
      else await salesApi.createDeal(data);
      toast.push({
        title: deal ? "Deal saved" : "Deal added",
        description: stage?.is_won ? "It counts as won." : stage?.is_lost ? "It counts as lost." : form.title.trim(),
      });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!deal) return;
    setBusy(true);
    try {
      await salesApi.removeDeal(deal.id);
      toast.push({ title: "Deal deleted", description: deal.title });
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
        title={deal ? "Edit deal" : "Add a deal"}
        description={deal?.customer_name ? `About ${deal.customer_name}` : "An opportunity on a pipeline."}
        footer={
          <>
            {deal && (
              <Button variant="ghost" size="sm" className="mr-auto text-danger" onClick={() => setDeleting(true)}>
                Delete
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" form="deal-form" size="sm" disabled={busy}>
              {busy ? "Saving…" : deal ? "Save deal" : "Add deal"}
            </Button>
          </>
        }
      >
        {pipelines.length === 0 ? (
          <p className="text-sm text-muted">
            There is no pipeline yet.{" "}
            <Link href="/settings/pipelines" className="text-accent-strong underline">
              Set one up
            </Link>{" "}
            and the deal will have stages to move through.
          </p>
        ) : (
          <form id="deal-form" onSubmit={save} className="grid gap-4 sm:grid-cols-2">
            {error && (
              <p role="alert" className="text-sm text-danger sm:col-span-2">
                {error}
              </p>
            )}
            {deal && (
              <p className="flex flex-wrap items-center gap-2 text-sm text-muted sm:col-span-2">
                <Pill tone={STATUS_TONE[deal.status]}>{STATUS_LABEL[deal.status]}</Pill>
                {deal.closed_at ? <span>Closed {formatDate(deal.closed_at)}</span> : <span>On {deal.stage_name ?? "no stage"}</span>}
              </p>
            )}
            <Field label="Title" className="sm:col-span-2">
              {(p) => <Input {...p} required maxLength={200} autoFocus value={form.title} onChange={(e) => set("title", e.target.value)} />}
            </Field>
            <Field label="Pipeline">
              {(p) => (
                <Select {...p} value={form.pipeline_id} onChange={(e) => pickPipeline(e.target.value)}>
                  {pipelines.map((pl) => (
                    <option key={pl.id} value={pl.id}>
                      {pl.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Stage" hint={stage?.is_won ? "Saving here marks the deal won." : stage?.is_lost ? "Saving here marks the deal lost." : undefined}>
              {(p) => (
                <Select {...p} required value={form.stage_id} onChange={(e) => pickStage(e.target.value)}>
                  {stages.map((s) => (
                    <option key={s.id} value={s.id}>
                      {stageLabel(s.name, s.probability, s.is_won, s.is_lost)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <div className="sm:col-span-2">
              <p className="mb-1.5 text-sm font-medium text-ink">Customer</p>
              <CustomerPicker value={picked?.id ?? null} name={picked?.name ?? null} onChange={setPicked} />
            </div>
            <Field label="Value">
              {(p) => (
                <div className="flex gap-2">
                  <Input {...p} type="number" min="0" step="0.01" placeholder="0.00" value={form.value} onChange={(e) => set("value", e.target.value)} />
                  <Input
                    aria-label="Currency"
                    className="w-20"
                    maxLength={3}
                    value={form.currency}
                    onChange={(e) => set("currency", e.target.value.toUpperCase())}
                  />
                </div>
              )}
            </Field>
            <Field label="Probability %" hint="Comes from the stage; override it if you know better.">
              {(p) => (
                <Input
                  {...p}
                  type="number"
                  min="0"
                  max="100"
                  value={form.probability}
                  onChange={(e) => {
                    setTouchedProbability(true);
                    set("probability", e.target.value);
                  }}
                />
              )}
            </Field>
            <Field label="Expected close" hint="Optional.">
              {(p) => <Input {...p} type="date" value={form.expected_close_on} onChange={(e) => set("expected_close_on", e.target.value)} />}
            </Field>
            <Field label="Owner" hint={canAssign ? undefined : "Managers can give deals to someone else."}>
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
            <Field label="Source">
              {(p) => (
                <Select {...p} value={form.source} onChange={(e) => set("source", e.target.value)}>
                  <option value="">Not set</option>
                  {lookups.options("lead_source", deal?.source).map((v) => (
                    <option key={v.key} value={v.key}>
                      {v.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Lost reason" hint="Kept if the deal is lost.">
              {(p) => (
                <Select {...p} value={form.lost_reason} onChange={(e) => set("lost_reason", e.target.value)}>
                  <option value="">Not set</option>
                  {lookups.options("lost_reason", deal?.lost_reason).map((v) => (
                    <option key={v.key} value={v.key}>
                      {v.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Notes" className="sm:col-span-2" hint="Optional.">
              {(p) => <Textarea {...p} rows={3} maxLength={20000} value={form.description} onChange={(e) => set("description", e.target.value)} />}
            </Field>
          </form>
        )}
      </Modal>
      <ConfirmDialog
        open={deleting}
        title="Delete this deal?"
        message={`“${deal?.title}” will be removed from the board and the forecast.`}
        confirmLabel="Delete deal"
        tone="danger"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setDeleting(false)}
      />
    </>
  );
}
