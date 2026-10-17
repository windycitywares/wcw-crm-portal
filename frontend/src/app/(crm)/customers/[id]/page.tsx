"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button, ButtonLink } from "@/components/ui/Button";
import { ColorTag } from "@/components/ui/ColorTag";
import { ConfirmDialog } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDate, formatDateTime } from "@/lib/utils";
import { customersApi, formatMoney, STATUS_LABEL, type Customer } from "@/modules/customers/api";
import { MergeDialog } from "@/modules/customers/MergeDialog";
import { RecordTasks } from "@/modules/tasks/RecordTasks";
import { CustomerDeals } from "@/modules/sales/CustomerDeals";
import { CustomerTickets } from "@/modules/tickets/CustomerTickets";
import { ShopOrders } from "@/modules/integrations/ShopOrders";
import { CustomFieldsView } from "@/modules/records/CustomFields";
import { NotesPanel } from "@/modules/records/NotesPanel";
import { TagEditor } from "@/modules/records/TagEditor";
import { Timeline } from "@/modules/records/Timeline";
import { useDirectory } from "@/modules/records/useDirectory";
import { customFieldsApi, type FieldDef } from "@/modules/settings/api";
import { useLookups } from "@/modules/settings/useLookups";

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 break-words text-sm">{children ?? <span className="text-muted">—</span>}</dd>
    </div>
  );
}

export default function CustomerPage() {
  const { id } = useParams<{ id: string }>();
  const customerId = Number(id);
  const router = useRouter();
  const toast = useToast();
  const { user, can } = useAuth();
  const { name } = useDirectory();
  const lookups = useLookups();
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [defs, setDefs] = useState<FieldDef[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [merging, setMerging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);

  const load = useCallback(async () => {
    try {
      // Managers can open deleted customers (to restore them); others get "not found".
      setCustomer(await customersApi.get(customerId, can("customers:edit_any")));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the customer");
    }
  }, [customerId, can]);

  useEffect(() => {
    void load();
    customFieldsApi
      .list("customer")
      .then(setDefs)
      .catch(() => setDefs([]));
  }, [load]);

  if (error) {
    return (
      <>
        <PageHeader title="Customer" back={{ href: "/customers", label: "Customers" }} />
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      </>
    );
  }
  if (!customer) return <p className="text-sm text-muted">Loading…</p>;

  const record = { type: "customer", id: customer.id };
  const deleted = customer.deleted_at != null;
  const canManage = can("customers:edit_any");
  const canEdit = !deleted && (canManage || (can("customers:edit_own") && customer.owner_id === user?.id));
  const type = lookups.find("customer_type", customer.customer_type);
  const source = lookups.find("lead_source", customer.source);
  const a = customer.address;
  const address = a ? [a.line1, a.line2, [a.city, a.state, a.postal_code].filter(Boolean).join(", "), a.country].filter(Boolean) : [];
  const changed = () => setRefresh((n) => n + 1);

  async function remove() {
    setBusy(true);
    try {
      await customersApi.remove(customerId);
      toast.push({ title: "Customer deleted", description: `${customer?.display_name} can be restored from the Deleted filter.` });
      router.push("/customers");
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't delete", description: err instanceof Error ? err.message : undefined });
      setBusy(false);
      setConfirming(false);
    }
  }

  async function restore() {
    setBusy(true);
    try {
      setCustomer(await customersApi.restore(customerId));
      toast.push({ title: "Customer restored" });
      changed();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't restore", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title={customer.display_name}
        back={{ href: "/customers", label: "Customers" }}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {deleted ? (
              <Pill tone="danger">Deleted {formatDate(customer.deleted_at)}</Pill>
            ) : (
              <Pill tone={customer.status === "active" ? "success" : customer.status === "blocked" ? "danger" : "neutral"}>{STATUS_LABEL[customer.status]}</Pill>
            )}
            {type && <ColorTag color={type.color}>{type.label}</ColorTag>}
            {customer.shop_user_id && <Pill tone="info">Shop account</Pill>}
          </span>
        }
        actions={
          <>
            {canEdit && (
              <ButtonLink href={`/customers/${customer.id}/edit`} size="sm">
                Edit customer
              </ButtonLink>
            )}
            {can("customers:merge") && !deleted && (
              <Button variant="secondary" size="sm" onClick={() => setMerging(true)}>
                Merge duplicate
              </Button>
            )}
            {canManage && !deleted && (
              <Button variant="secondary" size="sm" onClick={() => setConfirming(true)}>
                Delete
              </Button>
            )}
            {canManage && deleted && (
              <Button size="sm" onClick={restore} disabled={busy}>
                {busy ? "Restoring…" : "Restore customer"}
              </Button>
            )}
          </>
        }
      />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <div className="grid content-start gap-6">
          <Panel>
            <PanelHeader title="Details" />
            <PanelBody>
              <dl className="grid gap-4 sm:grid-cols-2">
                <Detail label="Email">{customer.email && <a className="text-accent-strong underline" href={`mailto:${customer.email}`}>{customer.email}</a>}</Detail>
                <Detail label="Phone">{customer.phone && <a className="text-accent-strong underline" href={`tel:${customer.phone}`}>{customer.phone}</a>}</Detail>
                {customer.company && customer.full_name && <Detail label="Company">{customer.company}</Detail>}
                <Detail label="Owner">{customer.owner_id ? name(customer.owner_id) : null}</Detail>
                <Detail label="Source">{source?.label ?? customer.source}</Detail>
                <Detail label="Marketing email">
                  {customer.unsubscribed_at
                    ? `Unsubscribed ${formatDate(customer.unsubscribed_at)}`
                    : customer.marketing_consent
                      ? `Agreed${customer.consent_at ? ` ${formatDate(customer.consent_at)}` : ""}${customer.consent_source ? ` (${customer.consent_source})` : ""}`
                      : "No consent"}
                </Detail>
                {customer.alt_emails.length > 0 && <Detail label="Other emails">{customer.alt_emails.join(", ")}</Detail>}
                {address.length > 0 && (
                  <Detail label="Address">
                    <address className="not-italic">
                      {address.map((line) => (
                        <span key={line} className="block">
                          {line}
                        </span>
                      ))}
                    </address>
                  </Detail>
                )}
                <Detail label="Added">{`${formatDateTime(customer.created_at)} by ${name(customer.created_by)}`}</Detail>
              </dl>
              <div className="mt-4">
                <CustomFieldsView defs={defs} values={customer.custom_fields} />
              </div>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Shop orders" description="Kept up to date by the shop connection." />
            <PanelBody className="grid gap-4">
              <dl className="grid grid-cols-2 gap-4">
                <Detail label="Orders">{customer.orders_count}</Detail>
                <Detail label="Total spent">{formatMoney(customer.total_spent)}</Detail>
                <Detail label="First order">{customer.first_order_at ? formatDate(customer.first_order_at) : null}</Detail>
                <Detail label="Last order">{customer.last_order_at ? formatDate(customer.last_order_at) : null}</Detail>
              </dl>
              <ShopOrders customerId={customer.id} refreshKey={customer.updated_at} />
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Tags" />
            <PanelBody>
              <TagEditor record={record} canEdit={canEdit} onChange={changed} />
            </PanelBody>
          </Panel>
        </div>

        <div className="grid content-start gap-6">
          {can("tickets:view") && !deleted && <CustomerTickets customerId={customer.id} customerName={customer.display_name} onChange={changed} />}
          {can("sales:view") && !deleted && <CustomerDeals customerId={customer.id} customerName={customer.display_name} onChange={changed} />}
          {can("tasks:view") && !deleted && <RecordTasks type="customer" id={customer.id} label={customer.display_name} onChange={changed} />}
          <NotesPanel record={record} onChange={changed} />
          <Timeline record={record} refreshKey={`${refresh}-${customer.updated_at}`} />
        </div>
      </div>

      <MergeDialog
        customer={customer}
        open={merging}
        onClose={() => setMerging(false)}
        onMerged={(merged) => {
          setCustomer(merged);
          changed();
        }}
      />

      <ConfirmDialog
        open={confirming}
        title="Delete this customer?"
        message={`${customer.display_name} disappears from lists and searches. Managers can restore them later from the Deleted filter.`}
        confirmLabel="Delete customer"
        tone="danger"
        busy={busy}
        onConfirm={remove}
        onCancel={() => setConfirming(false)}
      />
    </>
  );
}
