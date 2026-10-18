"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { CustomFieldsView } from "@/modules/records/CustomFields";
import { NotesPanel } from "@/modules/records/NotesPanel";
import { TagEditor } from "@/modules/records/TagEditor";
import { Timeline } from "@/modules/records/Timeline";
import { customFieldsApi, type FieldDef } from "@/modules/settings/api";
import { useLookups } from "@/modules/settings/useLookups";
import { suppliersApi, type Supplier, type SupplierContact, type SupplierProduct } from "@/modules/suppliers/api";

type ContactDraft = { name: string; title: string; email: string; phone: string; is_primary: boolean };
type ProductDraft = { shop_sku: string; supplier_sku: string; description: string; unit_cost: string; currency: string; minimum_order_quantity: string; lead_time_days: string; notes: string };
const EMPTY_CONTACT: ContactDraft = { name: "", title: "", email: "", phone: "", is_primary: false };
const EMPTY_PRODUCT: ProductDraft = { shop_sku: "", supplier_sku: "", description: "", unit_cost: "", currency: "USD", minimum_order_quantity: "", lead_time_days: "", notes: "" };
const PRODUCT_PAGE_SIZE = 10;

function ContactsPanel({ supplier, canEdit, onChange }: { supplier: Supplier; canEdit: boolean; onChange: () => void }) {
  const [draft, setDraft] = useState<ContactDraft>(EMPTY_CONTACT);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEdit = (contact: SupplierContact) => {
    setEditingId(contact.id);
    setDraft({ name: contact.name, title: contact.title ?? "", email: contact.email ?? "", phone: contact.phone ?? "", is_primary: contact.is_primary });
    setError(null);
  };

  const reset = () => {
    setEditingId(null);
    setDraft(EMPTY_CONTACT);
    setError(null);
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.name.trim()) return;
    setBusy(true);
    setError(null);
    const data = {
      name: draft.name.trim(),
      title: draft.title.trim() || null,
      email: draft.email.trim() || null,
      phone: draft.phone.trim() || null,
      is_primary: draft.is_primary,
    };
    try {
      if (editingId) await suppliersApi.contacts.update(supplier.id, editingId, data);
      else await suppliersApi.contacts.add(supplier.id, data);
      reset();
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save contact");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (contact: SupplierContact) => {
    if (!window.confirm(`Remove ${contact.name} from this supplier?`)) return;
    setBusy(true);
    try {
      await suppliersApi.contacts.remove(supplier.id, contact.id);
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't remove contact");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title="Contacts" description={`${supplier.contacts.length} ${supplier.contacts.length === 1 ? "contact" : "contacts"}`} />
      <PanelBody className="space-y-4">
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <ul className="divide-y divide-line">
          {supplier.contacts.map((contact) => (
            <li key={contact.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 font-medium">{contact.name}{contact.is_primary && <Pill tone="info">Primary</Pill>}</div>
                <div className="text-xs text-muted">{[contact.title, contact.email, contact.phone].filter(Boolean).join(" · ") || "No contact details"}</div>
              </div>
              {canEdit && <div className="flex gap-1">
                <Button type="button" size="sm" variant="secondary" onClick={() => startEdit(contact)}>Edit</Button>
                <Button type="button" size="sm" variant="ghost" className="text-danger" disabled={busy} onClick={() => void remove(contact)}>Remove</Button>
              </div>}
            </li>
          ))}
          {supplier.contacts.length === 0 && <li className="py-2 text-sm text-muted">No contacts recorded.</li>}
        </ul>
        {canEdit && <form onSubmit={save} className="grid gap-3 border-t border-line pt-4 sm:grid-cols-2">
          <h3 className="text-sm font-semibold sm:col-span-2">{editingId ? "Edit contact" : "Add contact"}</h3>
          <Field label="Name">{(p) => <Input {...p} required value={draft.name} onChange={(e) => setDraft((current) => ({ ...current, name: e.target.value }))} />}</Field>
          <Field label="Title">{(p) => <Input {...p} value={draft.title} onChange={(e) => setDraft((current) => ({ ...current, title: e.target.value }))} />}</Field>
          <Field label="Email">{(p) => <Input {...p} type="email" value={draft.email} onChange={(e) => setDraft((current) => ({ ...current, email: e.target.value }))} />}</Field>
          <Field label="Phone">{(p) => <Input {...p} type="tel" value={draft.phone} onChange={(e) => setDraft((current) => ({ ...current, phone: e.target.value }))} />}</Field>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={draft.is_primary} onChange={(e) => setDraft((current) => ({ ...current, is_primary: e.target.checked }))} />
            Primary contact
          </label>
          <div className="flex gap-2 sm:col-span-2">
            <Button type="submit" size="sm" disabled={busy || !draft.name.trim()}>{busy ? "Saving…" : editingId ? "Save contact" : "Add contact"}</Button>
            {editingId && <Button type="button" size="sm" variant="secondary" onClick={reset}>Cancel</Button>}
          </div>
        </form>}
      </PanelBody>
    </Panel>
  );
}

function ProductsPanel({ supplierId, canEdit }: { supplierId: number; canEdit: boolean }) {
  const [products, setProducts] = useState<SupplierProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState<ProductDraft>(EMPTY_PRODUCT);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    void suppliersApi.products.list(supplierId, page, PRODUCT_PAGE_SIZE).then((result) => {
      if (active) {
        setProducts(result.items);
        setTotal(result.total);
      }
    }).catch((err: unknown) => {
      if (active) setError(err instanceof Error ? err.message : "Couldn't load supplied products");
    });
    return () => { active = false; };
  }, [supplierId, page, revision]);

  const reset = () => {
    setEditingId(null);
    setDraft(EMPTY_PRODUCT);
    setError(null);
  };

  const edit = (product: SupplierProduct) => {
    setEditingId(product.id);
    setDraft({
      shop_sku: product.shop_sku,
      supplier_sku: product.supplier_sku ?? "",
      description: product.description ?? "",
      unit_cost: product.unit_cost,
      currency: product.currency,
      minimum_order_quantity: product.minimum_order_quantity ?? "",
      lead_time_days: product.lead_time_days == null ? "" : String(product.lead_time_days),
      notes: product.notes ?? "",
    });
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.shop_sku.trim() || draft.unit_cost === "") return;
    setBusy(true);
    setError(null);
    const data = {
      shop_sku: draft.shop_sku.trim(),
      supplier_sku: draft.supplier_sku.trim() || null,
      description: draft.description.trim() || null,
      unit_cost: draft.unit_cost,
      currency: draft.currency.trim().toUpperCase(),
      minimum_order_quantity: draft.minimum_order_quantity || null,
      lead_time_days: draft.lead_time_days === "" ? null : Number(draft.lead_time_days),
      notes: draft.notes.trim() || null,
    };
    try {
      if (editingId) await suppliersApi.products.update(supplierId, editingId, data);
      else await suppliersApi.products.add(supplierId, data);
      reset();
      setRevision((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save supplied product");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (product: SupplierProduct) => {
    if (!window.confirm(`Remove ${product.shop_sku} from this supplier?`)) return;
    setBusy(true);
    try {
      await suppliersApi.products.remove(supplierId, product.id);
      setRevision((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't remove supplied product");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title="Supplied products" description={`${total} ${total === 1 ? "product" : "products"}`} />
      <PanelBody className="space-y-4">
        {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        <ul className="divide-y divide-line">
          {products.map((product) => (
            <li key={product.id} className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0">
              <div className="min-w-0">
                <div className="font-medium">{product.shop_sku}{product.supplier_sku ? <span className="font-normal text-muted"> · {product.supplier_sku}</span> : null}</div>
                <div className="text-xs text-muted">{product.description ?? "No description"} · {product.currency} {Number(product.unit_cost).toFixed(2)}{product.minimum_order_quantity ? ` · MOQ ${product.minimum_order_quantity}` : ""}</div>
              </div>
              {canEdit && <div className="flex gap-1">
                <Button type="button" size="sm" variant="secondary" onClick={() => edit(product)}>Edit</Button>
                <Button type="button" size="sm" variant="ghost" className="text-danger" disabled={busy} onClick={() => void remove(product)}>Remove</Button>
              </div>}
            </li>
          ))}
          {products.length === 0 && <li className="py-2 text-sm text-muted">No supplied products recorded.</li>}
        </ul>
        {total > PRODUCT_PAGE_SIZE && <Pagination page={page} pageSize={PRODUCT_PAGE_SIZE} total={total} onPage={setPage} />}
        {canEdit && <form onSubmit={save} className="grid gap-3 border-t border-line pt-4 sm:grid-cols-2">
          <h3 className="text-sm font-semibold sm:col-span-2">{editingId ? "Edit supplied product" : "Add supplied product"}</h3>
          <Field label="Shop SKU">{(p) => <Input {...p} required value={draft.shop_sku} onChange={(e) => setDraft((current) => ({ ...current, shop_sku: e.target.value }))} />}</Field>
          <Field label="Supplier SKU">{(p) => <Input {...p} value={draft.supplier_sku} onChange={(e) => setDraft((current) => ({ ...current, supplier_sku: e.target.value }))} />}</Field>
          <Field label="Description">{(p) => <Input {...p} value={draft.description} onChange={(e) => setDraft((current) => ({ ...current, description: e.target.value }))} />}</Field>
          <Field label="Unit cost">{(p) => <Input {...p} type="number" min={0} step="0.01" required value={draft.unit_cost} onChange={(e) => setDraft((current) => ({ ...current, unit_cost: e.target.value }))} />}</Field>
          <Field label="Currency">{(p) => <Input {...p} minLength={3} maxLength={3} pattern="[A-Za-z]{3}" required value={draft.currency} onChange={(e) => setDraft((current) => ({ ...current, currency: e.target.value.toUpperCase() }))} />}</Field>
          <Field label="Minimum order quantity">{(p) => <Input {...p} type="number" min={0.001} step="0.001" value={draft.minimum_order_quantity} onChange={(e) => setDraft((current) => ({ ...current, minimum_order_quantity: e.target.value }))} />}</Field>
          <Field label="Lead time (days)">{(p) => <Input {...p} type="number" min={0} step={1} value={draft.lead_time_days} onChange={(e) => setDraft((current) => ({ ...current, lead_time_days: e.target.value }))} />}</Field>
          <Field label="Notes" className="sm:col-span-2">{(p) => <Textarea {...p} value={draft.notes} onChange={(e) => setDraft((current) => ({ ...current, notes: e.target.value }))} />}</Field>
          <div className="flex gap-2 sm:col-span-2">
            <Button type="submit" size="sm" disabled={busy || !draft.shop_sku.trim() || draft.unit_cost === ""}>{busy ? "Saving…" : editingId ? "Save product" : "Add product"}</Button>
            {editingId && <Button type="button" size="sm" variant="secondary" onClick={reset}>Cancel</Button>}
          </div>
        </form>}
      </PanelBody>
    </Panel>
  );
}

export default function SupplierPage() {
  const { id } = useParams<{ id: string }>();
  const supplierId = Number(id);
  const router = useRouter();
  const { can } = useAuth();
  const lookups = useLookups();
  const canEdit = can("suppliers:edit");
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [defs, setDefs] = useState<FieldDef[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    if (!Number.isSafeInteger(supplierId) || supplierId < 1) {
      setError("Supplier not found.");
      return;
    }
    let active = true;
    void suppliersApi.get(supplierId).then((row) => {
      if (active) {
        setSupplier(row);
        setError(null);
      }
    }).catch((err: unknown) => {
      if (active) setError(err instanceof Error ? err.message : "Couldn't load supplier");
    });
    customFieldsApi.list("supplier").then((fields) => { if (active) setDefs(fields); }).catch(() => { if (active) setDefs([]); });
    return () => { active = false; };
  }, [supplierId, refresh]);

  const changed = () => setRefresh((value) => value + 1);

  const removeSupplier = async () => {
    if (!supplier || !window.confirm(`Archive ${supplier.name}?`)) return;
    try {
      await suppliersApi.remove(supplier.id);
      router.push("/suppliers");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't archive supplier");
    }
  };

  if (error) return <><PageHeader title="Supplier" back={{ href: "/suppliers", label: "Suppliers" }} /><p role="alert" className="text-sm text-danger">{error}</p></>;
  if (!supplier) return <p className="text-sm text-muted">Loading supplier…</p>;

  const record = { type: "supplier", id: supplier.id };
  const typeLabel = lookups.find("supplier_type", supplier.supplier_type)?.label ?? supplier.supplier_type;
  const address = supplier.address ? [supplier.address.line1, supplier.address.line2, [supplier.address.city, supplier.address.state, supplier.address.postal_code].filter(Boolean).join(", "), supplier.address.country].filter(Boolean) : [];

  return (
    <>
      <PageHeader
        title={supplier.name}
        back={{ href: "/suppliers", label: "Suppliers" }}
        description={<span className="flex flex-wrap items-center gap-2"><Pill tone={supplier.status === "active" ? "success" : "neutral"}>{supplier.status}</Pill><Pill tone="info">{typeLabel}</Pill></span>}
        actions={<>
          {canEdit && <ButtonLink href={`/suppliers/${supplier.id}/edit`} size="sm">Edit supplier</ButtonLink>}
          {canEdit && <Button type="button" size="sm" variant="secondary" className="text-danger" onClick={() => void removeSupplier()}>Archive</Button>}
        </>}
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <div className="grid content-start gap-6">
          <Panel>
            <PanelHeader title="Purchasing details" />
            <PanelBody>
              <dl className="grid gap-4 sm:grid-cols-2">
                <div><dt className="text-xs text-muted">Website</dt><dd className="mt-0.5 break-words text-sm">{supplier.website ? <a href={supplier.website} target="_blank" rel="noreferrer" className="text-accent-strong underline">{supplier.website}</a> : "—"}</dd></div>
                <div><dt className="text-xs text-muted">Payment terms</dt><dd className="mt-0.5 text-sm">{supplier.payment_terms ?? "—"}</dd></div>
                <div><dt className="text-xs text-muted">Lead time</dt><dd className="mt-0.5 text-sm">{supplier.lead_time_days == null ? "—" : `${supplier.lead_time_days} days`}</dd></div>
                <div><dt className="text-xs text-muted">Currency</dt><dd className="mt-0.5 text-sm">{supplier.currency}</dd></div>
                <div><dt className="text-xs text-muted">Rating</dt><dd className="mt-0.5 text-sm">{supplier.rating == null ? "—" : `${supplier.rating} / 5`}</dd></div>
                {address.length > 0 && <div className="sm:col-span-2"><dt className="text-xs text-muted">Address</dt><dd className="mt-0.5 text-sm">{address.map((line) => <span key={line} className="block">{line}</span>)}</dd></div>}
                <div className="sm:col-span-2"><dt className="text-xs text-muted">Added</dt><dd className="mt-0.5 text-sm">{formatDateTime(supplier.created_at)}</dd></div>
              </dl>
              <div className="mt-4"><CustomFieldsView defs={defs} values={supplier.custom_fields} /></div>
            </PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title="Tags" />
            <PanelBody><TagEditor record={record} canEdit={canEdit} onChange={changed} /></PanelBody>
          </Panel>
          <NotesPanel record={record} onChange={changed} />
        </div>

        <div className="grid content-start gap-6">
          <ContactsPanel supplier={supplier} canEdit={canEdit} onChange={changed} />
          <ProductsPanel supplierId={supplier.id} canEdit={canEdit} />
          <Timeline record={record} refreshKey={`${refresh}-${supplier.updated_at}`} />
        </div>
      </div>
    </>
  );
}