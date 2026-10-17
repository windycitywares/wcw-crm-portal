"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import type { Pipeline } from "@/modules/sales/api";
import { CustomerPicker } from "@/modules/tickets/CustomerPicker";
import { leadsApi, type Lead, type LeadConvertInput } from "./api";

interface Form {
  pipeline_id: string;
  stage_id: string;
  deal_title: string;
  value: string;
  currency: string;
  expected_close_on: string;
  create_deal: boolean;
}

/**
 * Convert a lead: the customer is one you pick, the one already on the lead's email, or a new one made
 * from the lead's details — and, unless you say otherwise, the lead's first deal is opened too. The API
 * does it all in one transaction, so there is never half a conversion.
 */
export function LeadConvertDialog({
  open,
  lead,
  pipelines,
  onClose,
  onConverted,
}: {
  open: boolean;
  lead: Lead | null;
  pipelines: Pipeline[];
  onClose: () => void;
  onConverted: (converted: Lead) => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState<Form | null>(null);
  const [customer, setCustomer] = useState<{ id: number; name: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pipeline = pipelines.find((p) => p.is_default) ?? pipelines[0];
  const hasPipeline = Boolean(pipeline);
  const firstStage = String(pipeline?.stages[0]?.id ?? "");

  useEffect(() => {
    if (!open || !lead) return;
    setForm({
      pipeline_id: String(pipeline?.id ?? ""),
      stage_id: firstStage,
      deal_title: lead.company ?? lead.display_name,
      value: "",
      currency: "USD",
      expected_close_on: "",
      create_deal: hasPipeline,
    });
    setCustomer(null);
    setError(null);
  }, [open, lead, pipeline?.id, firstStage, hasPipeline]);

  if (!form || !lead) return null;
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm({ ...form, [key]: value });
  const stages = pipelines.find((p) => p.id === Number(form.pipeline_id))?.stages ?? [];

  function pickPipeline(id: string) {
    const next = pipelines.find((p) => p.id === Number(id));
    setForm((f) => (f ? { ...f, pipeline_id: id, stage_id: String(next?.stages[0]?.id ?? "") } : f));
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form || !lead) return;
    setBusy(true);
    setError(null);
    const data: LeadConvertInput = {
      customer_id: customer?.id ?? null,
      create_deal: form.create_deal,
      deal_title: form.deal_title.trim() || null,
      stage_id: form.create_deal && form.stage_id ? Number(form.stage_id) : null,
      value: form.value.trim() === "" ? 0 : form.value.trim(),
      currency: form.currency.trim().toUpperCase() || "USD",
      expected_close_on: form.expected_close_on || null,
    };
    try {
      const converted = await leadsApi.convert(lead.id, data);
      toast.push({
        title: `${lead.display_name} converted`,
        description: converted.converted_deal_id ? "The customer and their first deal are ready." : "The customer is ready.",
      });
      onConverted(converted);
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
      title="Convert lead"
      description={`${lead.display_name} becomes a customer.`}
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="convert-form" size="sm" disabled={busy}>
            {busy ? "Converting…" : "Convert lead"}
          </Button>
        </>
      }
    >
      <form id="convert-form" onSubmit={save} className="grid gap-4 sm:grid-cols-2">
        {error && (
          <p role="alert" className="text-sm text-danger sm:col-span-2">
            {error}
          </p>
        )}
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 rounded-[var(--radius-control)] bg-sand px-3.5 py-2.5 text-sm sm:col-span-2">
          <dt className="text-muted">Name</dt>
          <dd>{lead.full_name || "—"}</dd>
          <dt className="text-muted">Company</dt>
          <dd>{lead.company || "—"}</dd>
          <dt className="text-muted">Email</dt>
          <dd>{lead.email || "—"}</dd>
          <dt className="text-muted">Phone</dt>
          <dd>{lead.phone || "—"}</dd>
        </dl>
        <div className="sm:col-span-2">
          <p className="mb-1.5 text-sm font-medium text-ink">Customer</p>
          <CustomerPicker value={customer?.id ?? null} name={customer?.name ?? null} onChange={setCustomer} />
          <p className="mt-1.5 text-xs text-muted">
            Leave this empty to use the customer that already has this email — or to make one from the lead&apos;s details.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input
            type="checkbox"
            className="size-4 accent-[var(--color-accent)]"
            checked={form.create_deal}
            disabled={!hasPipeline}
            onChange={(e) => set("create_deal", e.target.checked)}
          />
          Open a deal for them
        </label>
        {!hasPipeline && (
          <p className="text-xs text-muted sm:col-span-2">
            There is no pipeline yet.{" "}
            <Link href="/settings/pipelines" className="text-accent-strong underline">
              Set one up
            </Link>{" "}
            and converting can open a deal too — for now only the customer is made.
          </p>
        )}
        {form.create_deal && (
          <>
            <Field label="Deal title">
              {(p) => <Input {...p} maxLength={200} value={form.deal_title} onChange={(e) => set("deal_title", e.target.value)} />}
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
            <Field label="Stage" hint="Where the deal starts; the stage decides won or lost later.">
              {(p) => (
                <Select {...p} value={form.stage_id} onChange={(e) => set("stage_id", e.target.value)}>
                  {stages.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Expected close" hint="Optional.">
              {(p) => <Input {...p} type="date" value={form.expected_close_on} onChange={(e) => set("expected_close_on", e.target.value)} />}
            </Field>
            <Field label="Value">
              {(p) => (
                <div className="flex gap-2">
                  <Input
                    {...p}
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={form.value}
                    onChange={(e) => set("value", e.target.value)}
                  />
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
          </>
        )}
      </form>
    </Modal>
  );
}
