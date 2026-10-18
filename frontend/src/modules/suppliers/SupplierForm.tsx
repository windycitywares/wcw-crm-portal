"use client";

import { useEffect, useState } from "react";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { CustomFieldsEditor, type CustomValues } from "@/modules/records/CustomFields";
import { customFieldsApi, type FieldDef } from "@/modules/settings/api";
import { useLookups } from "@/modules/settings/useLookups";
import { suppliersApi, type Supplier, type SupplierAddress, type SupplierInput, type SupplierStatus } from "./api";

interface FormState {
  name: string;
  supplier_type: string;
  status: SupplierStatus;
  website: string;
  payment_terms: string;
  lead_time_days: string;
  currency: string;
  rating: string;
  address: Required<{ [K in keyof SupplierAddress]: string }>;
  custom_fields: CustomValues;
  contact_name: string;
  contact_title: string;
  contact_email: string;
  contact_phone: string;
}

function toState(supplier: Supplier | null): FormState {
  const address = supplier?.address ?? {};
  const primary = supplier?.contacts.find((contact) => contact.is_primary) ?? null;
  return {
    name: supplier?.name ?? "",
    supplier_type: supplier?.supplier_type ?? "",
    status: supplier?.status ?? "active",
    website: supplier?.website ?? "",
    payment_terms: supplier?.payment_terms ?? "",
    lead_time_days: supplier?.lead_time_days == null ? "" : String(supplier.lead_time_days),
    currency: supplier?.currency ?? "USD",
    rating: supplier?.rating == null ? "" : String(supplier.rating),
    address: {
      line1: address.line1 ?? "",
      line2: address.line2 ?? "",
      city: address.city ?? "",
      state: address.state ?? "",
      postal_code: address.postal_code ?? "",
      country: address.country ?? "",
    },
    custom_fields: supplier?.custom_fields ?? {},
    contact_name: primary?.name ?? "",
    contact_title: primary?.title ?? "",
    contact_email: primary?.email ?? "",
    contact_phone: primary?.phone ?? "",
  };
}

const ADDRESS_FIELDS: { key: keyof SupplierAddress; label: string }[] = [
  { key: "line1", label: "Address line 1" },
  { key: "line2", label: "Address line 2" },
  { key: "city", label: "City" },
  { key: "state", label: "State / region" },
  { key: "postal_code", label: "Postal code" },
  { key: "country", label: "Country" },
];

export function SupplierForm({ supplier, onSaved }: { supplier: Supplier | null; onSaved: (supplier: Supplier) => void }) {
  const lookups = useLookups();
  const [form, setForm] = useState<FormState>(() => toState(supplier));
  const [defs, setDefs] = useState<FieldDef[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    customFieldsApi.list("supplier").then(setDefs).catch(() => setDefs([]));
  }, []);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((current) => ({ ...current, [key]: value }));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim() || !form.supplier_type) return;
    setBusy(true);
    setError(null);
    const address = Object.fromEntries(
      Object.entries(form.address).map(([key, value]) => [key, value.trim() || null]),
    ) as SupplierAddress;
    const hasAddress = Object.values(address).some(Boolean);
    const data: SupplierInput = {
      name: form.name.trim(),
      supplier_type: form.supplier_type,
      status: form.status,
      website: form.website.trim() || null,
      payment_terms: form.payment_terms.trim() || null,
      lead_time_days: form.lead_time_days ? Number(form.lead_time_days) : null,
      currency: form.currency.trim().toUpperCase(),
      rating: form.rating ? Number(form.rating) : null,
      address: hasAddress ? address : null,
      custom_fields: form.custom_fields,
    };
    if (!supplier && form.contact_name.trim()) {
      data.contacts = [{
        name: form.contact_name.trim(),
        title: form.contact_title.trim() || null,
        email: form.contact_email.trim() || null,
        phone: form.contact_phone.trim() || null,
        is_primary: true,
      }];
    }
    try {
      const saved = supplier ? await suppliersApi.update(supplier.id, data) : await suppliersApi.create(data);
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save supplier");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="grid gap-6">
      {error && <p role="alert" className="rounded border border-danger/40 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</p>}

      <Panel>
        <PanelHeader title="Supplier" description="Directory and purchasing details." />
        <PanelBody className="grid gap-4 sm:grid-cols-2">
          <Field label="Supplier name" className="sm:col-span-2">
            {(p) => <Input {...p} required maxLength={160} value={form.name} onChange={(e) => set("name", e.target.value)} />}
          </Field>
          <Field label="Supplier type">
            {(p) => <Select {...p} required value={form.supplier_type} onChange={(e) => set("supplier_type", e.target.value)}>
              <option value="">Choose a type</option>
              {lookups.options("supplier_type", supplier?.supplier_type).map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
            </Select>}
          </Field>
          <Field label="Status">
            {(p) => <Select {...p} value={form.status} onChange={(e) => set("status", e.target.value as SupplierStatus)}>
              <option value="active">Active</option><option value="inactive">Inactive</option>
            </Select>}
          </Field>
          <Field label="Website">
            {(p) => <Input {...p} type="url" placeholder="https://" value={form.website} onChange={(e) => set("website", e.target.value)} />}
          </Field>
          <Field label="Payment terms">
            {(p) => <Input {...p} maxLength={300} placeholder="Net 30" value={form.payment_terms} onChange={(e) => set("payment_terms", e.target.value)} />}
          </Field>
          <Field label="Lead time (days)">
            {(p) => <Input {...p} type="number" min={0} max={3650} step={1} value={form.lead_time_days} onChange={(e) => set("lead_time_days", e.target.value)} />}
          </Field>
          <Field label="Currency" hint="Three-letter ISO code.">
            {(p) => <Input {...p} minLength={3} maxLength={3} pattern="[A-Za-z]{3}" value={form.currency} onChange={(e) => set("currency", e.target.value.toUpperCase())} />}
          </Field>
          <Field label="Rating">
            {(p) => <Select {...p} value={form.rating} onChange={(e) => set("rating", e.target.value)}>
              <option value="">Not rated</option>{[1, 2, 3, 4, 5].map((rating) => <option key={rating} value={rating}>{rating} / 5</option>)}
            </Select>}
          </Field>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="Address" />
        <PanelBody className="grid gap-4 sm:grid-cols-2">
          {ADDRESS_FIELDS.map(({ key, label }) => <Field key={key} label={label} className={key === "line1" || key === "line2" ? "sm:col-span-2" : undefined}>
            {(p) => <Input {...p} value={form.address[key]} onChange={(e) => setForm((current) => ({ ...current, address: { ...current.address, [key]: e.target.value } }))} />}
          </Field>)}
        </PanelBody>
      </Panel>

      {!supplier && <Panel>
        <PanelHeader title="Primary contact" description="Optional; additional contacts can be added after saving." />
        <PanelBody className="grid gap-4 sm:grid-cols-2">
          <Field label="Contact name">{(p) => <Input {...p} value={form.contact_name} onChange={(e) => set("contact_name", e.target.value)} />}</Field>
          <Field label="Title">{(p) => <Input {...p} value={form.contact_title} onChange={(e) => set("contact_title", e.target.value)} />}</Field>
          <Field label="Email">{(p) => <Input {...p} type="email" value={form.contact_email} onChange={(e) => set("contact_email", e.target.value)} />}</Field>
          <Field label="Phone">{(p) => <Input {...p} type="tel" value={form.contact_phone} onChange={(e) => set("contact_phone", e.target.value)} />}</Field>
        </PanelBody>
      </Panel>}

      {defs.length > 0 && <Panel>
        <PanelHeader title="Custom fields" />
        <PanelBody className="grid gap-4 sm:grid-cols-2">
          <CustomFieldsEditor defs={defs} values={form.custom_fields} onChange={(values) => set("custom_fields", values)} />
        </PanelBody>
      </Panel>}

      <div className="flex gap-2">
        <Button type="submit" disabled={busy || !form.name.trim() || !form.supplier_type}>{busy ? "Saving…" : supplier ? "Save supplier" : "Create supplier"}</Button>
        <ButtonLink href={supplier ? `/suppliers/${supplier.id}` : "/suppliers"} variant="secondary">Cancel</ButtonLink>
      </div>
    </form>
  );
}