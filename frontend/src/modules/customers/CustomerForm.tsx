"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { useAuth } from "@/lib/auth";
import { CustomFieldsEditor, type CustomValues } from "@/modules/records/CustomFields";
import { useDirectory } from "@/modules/records/useDirectory";
import { customFieldsApi, type FieldDef } from "@/modules/settings/api";
import { useLookups } from "@/modules/settings/useLookups";
import { customersApi, STATUS_LABEL, type Address, type Customer, type CustomerInput, type CustomerStatus } from "./api";

interface FormState {
  first_name: string;
  last_name: string;
  company: string;
  email: string;
  alt_emails: string;
  phone: string;
  address: Required<{ [K in keyof Address]: string }>;
  customer_type: string;
  source: string;
  status: CustomerStatus;
  owner_id: string;
  marketing_consent: boolean;
  custom_fields: CustomValues;
}

const ADDRESS_FIELDS: { key: keyof Address; label: string; className?: string; autoComplete: string }[] = [
  { key: "line1", label: "Address line 1", className: "sm:col-span-2", autoComplete: "off" },
  { key: "line2", label: "Address line 2", className: "sm:col-span-2", autoComplete: "off" },
  { key: "city", label: "City", autoComplete: "off" },
  { key: "state", label: "State / region", autoComplete: "off" },
  { key: "postal_code", label: "Postal code", autoComplete: "off" },
  { key: "country", label: "Country", autoComplete: "off" },
];

function toState(c: Customer | null): FormState {
  const a = c?.address ?? {};
  return {
    first_name: c?.first_name ?? "",
    last_name: c?.last_name ?? "",
    company: c?.company ?? "",
    email: c?.email ?? "",
    alt_emails: (c?.alt_emails ?? []).join(", "),
    phone: c?.phone ?? "",
    address: {
      line1: a.line1 ?? "",
      line2: a.line2 ?? "",
      city: a.city ?? "",
      state: a.state ?? "",
      postal_code: a.postal_code ?? "",
      country: a.country ?? "",
    },
    customer_type: c?.customer_type ?? "",
    source: c?.source ?? "",
    status: c?.status ?? "active",
    owner_id: c?.owner_id != null ? String(c.owner_id) : "",
    marketing_consent: c?.marketing_consent ?? false,
    custom_fields: c?.custom_fields ?? {},
  };
}

function toInput(f: FormState): CustomerInput {
  const address = Object.fromEntries(Object.entries(f.address).map(([k, v]) => [k, v.trim() || null])) as Address;
  const hasAddress = Object.values(address).some(Boolean);
  return {
    first_name: f.first_name.trim() || null,
    last_name: f.last_name.trim() || null,
    company: f.company.trim() || null,
    email: f.email.trim() || null,
    alt_emails: f.alt_emails
      .split(/[\s,;]+/)
      .map((e) => e.trim())
      .filter(Boolean),
    phone: f.phone.trim() || null,
    address: hasAddress ? address : null,
    customer_type: f.customer_type || null,
    source: f.source || null,
    status: f.status,
    owner_id: f.owner_id ? Number(f.owner_id) : null,
    marketing_consent: f.marketing_consent,
    custom_fields: f.custom_fields,
  };
}

/** Create or edit a customer. Calls `onSaved` with the stored record. */
export function CustomerForm({ customer, onSaved }: { customer: Customer | null; onSaved: (c: Customer) => void }) {
  const { user, can } = useAuth();
  const canReassign = can("customers:edit_any");
  const { people } = useDirectory();
  const lookups = useLookups();
  const [form, setForm] = useState<FormState>(() => toState(customer));
  const [defs, setDefs] = useState<FieldDef[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<{ id: number; name: string | null } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    customFieldsApi
      .list("customer")
      .then((list) => setDefs(list.filter((d) => d.is_active)))
      .catch(() => setDefs([]));
  }, []);

  useEffect(() => {
    if (!customer && user && !form.owner_id) setForm((f) => ({ ...f, owner_id: String(user.id) }));
  }, [customer, user, form.owner_id]);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => setForm((f) => ({ ...f, [key]: value }));

  async function checkEmail() {
    const email = form.email.trim();
    if (!email || email === customer?.email) return setDuplicate(null);
    try {
      const res = await customersApi.checkEmail(email, customer?.id);
      setDuplicate(res.exists && res.customer_id ? { id: res.customer_id, name: res.display_name } : null);
    } catch {
      setDuplicate(null);
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const data = toInput(form);
    if (!data.first_name && !data.last_name && !data.company && !data.email) {
      setError("Give the customer a name, a company or an email.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = customer ? await customersApi.update(customer.id, data) : await customersApi.create(data);
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setBusy(false);
    }
  }

  const owners = [...people.values()].filter((p) => p.is_active || String(p.id) === form.owner_id).sort((a, b) => a.full_name.localeCompare(b.full_name));

  return (
    <form onSubmit={save} className="grid gap-6" noValidate={false}>
      {error && (
        <p role="alert" className="rounded-lg border border-danger/30 bg-danger/8 px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}

      <Card>
        <CardHeader title="Contact" />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <Field label="First name">{(p) => <Input {...p} autoComplete="off" maxLength={80} value={form.first_name} onChange={(e) => set("first_name", e.target.value)} />}</Field>
          <Field label="Last name">{(p) => <Input {...p} autoComplete="off" maxLength={80} value={form.last_name} onChange={(e) => set("last_name", e.target.value)} />}</Field>
          <Field label="Company" hint="For business customers." className="sm:col-span-2">
            {(p) => <Input {...p} autoComplete="off" maxLength={160} value={form.company} onChange={(e) => set("company", e.target.value)} />}
          </Field>
          <Field label="Email" error={duplicate ? "Another customer already uses this email." : undefined}>
            {(p) => (
              <Input
                {...p}
                type="email"
                autoComplete="off"
                value={form.email}
                onChange={(e) => {
                  set("email", e.target.value);
                  setDuplicate(null);
                }}
                onBlur={checkEmail}
              />
            )}
          </Field>
          <Field label="Phone">{(p) => <Input {...p} type="tel" autoComplete="off" maxLength={40} value={form.phone} onChange={(e) => set("phone", e.target.value)} />}</Field>
          {duplicate && (
            <p className="text-sm sm:col-span-2">
              <Link className="text-accent-strong underline" href={`/customers/${duplicate.id}`}>
                Open {duplicate.name ?? `customer #${duplicate.id}`}
              </Link>{" "}
              instead of creating a second record.
            </p>
          )}
          <Field label="Other emails" hint="Separate with commas. Used to match shop orders and replies." className="sm:col-span-2">
            {(p) => <Input {...p} autoComplete="off" value={form.alt_emails} onChange={(e) => set("alt_emails", e.target.value)} />}
          </Field>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Classification" />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          <Field label="Customer type">
            {(p) => (
              <Select {...p} value={form.customer_type} onChange={(e) => set("customer_type", e.target.value)}>
                <option value="">Not set</option>
                {lookups.options("customer_type", customer?.customer_type).map((v) => (
                  <option key={v.key} value={v.key}>
                    {v.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Source">
            {(p) => (
              <Select {...p} value={form.source} onChange={(e) => set("source", e.target.value)}>
                <option value="">Not set</option>
                {lookups.options("lead_source", customer?.source).map((v) => (
                  <option key={v.key} value={v.key}>
                    {v.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Status">
            {(p) => (
              <Select {...p} value={form.status} onChange={(e) => set("status", e.target.value as CustomerStatus)}>
                {(Object.keys(STATUS_LABEL) as CustomerStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Owner" hint={canReassign ? "The colleague responsible for this customer." : "Managers can hand customers to someone else."}>
            {(p) => (
              <Select {...p} disabled={!canReassign} value={form.owner_id} onChange={(e) => set("owner_id", e.target.value)}>
                <option value="">Nobody</option>
                {owners.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.full_name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <label className="flex items-start gap-3 text-sm sm:col-span-2">
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-[var(--color-accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              checked={form.marketing_consent}
              onChange={(e) => set("marketing_consent", e.target.checked)}
            />
            <span>
              Agreed to receive marketing email
              <span className="block text-muted">Tick only if the customer said yes. Campaigns skip everyone else.</span>
            </span>
          </label>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Address" />
        <CardBody className="grid gap-4 sm:grid-cols-2">
          {ADDRESS_FIELDS.map((a) => (
            <Field key={a.key} label={a.label} className={a.className}>
              {(p) => (
                <Input {...p} autoComplete={a.autoComplete} value={form.address[a.key]} onChange={(e) => set("address", { ...form.address, [a.key]: e.target.value })} />
              )}
            </Field>
          ))}
        </CardBody>
      </Card>

      {defs.length > 0 && (
        <Card>
          <CardHeader title="More details" description="Fields your team added in Administration → Custom fields." />
          <CardBody>
            <CustomFieldsEditor defs={defs} values={form.custom_fields} onChange={(v) => set("custom_fields", v)} />
          </CardBody>
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={busy}>
          {busy ? "Saving…" : customer ? "Save customer" : "Add customer"}
        </Button>
        <Link href={customer ? `/customers/${customer.id}` : "/customers"} className="inline-flex h-11 items-center px-4 text-sm text-muted hover:text-ink">
          Cancel
        </Link>
      </div>
    </form>
  );
}
