"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDateTime as dateTime } from "@/lib/utils";
import { ATTENTION_LABEL, EXCEPTIONS, MAIN_PATH, MISSING_LABEL, ordersApi, STATUS_LABEL, STATUS_TONE, type OrderDetail, type OrderPatch } from "@/modules/channels/orders";
import { useSuppliers } from "@/modules/channels/SupplierFilter";
import { money, StatusSteps, Thumb } from "@/modules/channels/ui";

function Alert({ tone, children }: { tone?: "danger"; children: React.ReactNode }) {
  return <p role={tone === "danger" ? "alert" : "status"} className={tone === "danger" ? "rounded-[var(--radius-control)] bg-danger/12 px-4 py-3 text-sm text-danger" : "rounded-[var(--radius-control)] bg-sand px-4 py-3 text-sm"}>{children}</p>;
}

const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");
const m = (v: string | number | null | undefined) => money(v);
const FORM_KEYS = ["purchase_cost", "shipping_cost", "supplier_account_id", "supplier_order_number", "carrier", "tracking_number", "buyer_phone", "notes"] as const;
type FormKey = (typeof FORM_KEYS)[number];
type Form = Record<FormKey, string>;
const ADDRESS_ORDER = ["name", "first_line", "second_line", "city", "state", "zip", "country_iso"];

function Row({ label, children, strong }: { label: string; children: React.ReactNode; strong?: boolean }) {
  return (
    <div className={`flex flex-wrap justify-between gap-x-4 gap-y-0.5 py-2 text-sm ${strong ? "font-semibold" : ""}`}>
      <dt className={strong ? "" : "text-muted"}>{label}</dt>
      <dd className="min-w-0 text-right">{children}</dd>
    </div>
  );
}

const toForm = (o: OrderDetail): Form => Object.fromEntries(FORM_KEYS.map((k) => [k, o[k] === null || o[k] === undefined ? "" : String(o[k])])) as Form;

export default function EtsyOrderPage() {
  const { id } = useParams<{ id: string }>();
  const { push } = useToast();
  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [saving, setSaving] = useState(false);
  const [nextStatus, setNextStatus] = useState("");
  const [statusNote, setStatusNote] = useState("");
  const { can } = useAuth();
  const suppliers = useSuppliers();
  const canEdit = can("channels:edit");

  const show = useCallback((o: OrderDetail) => {
    setOrder(o);
    setForm(toForm(o));
  }, []);
  const reload = useCallback(() => {
    ordersApi.get(Number(id)).then(show, (e) => setError(errorText(e)));
  }, [id, show]);
  useEffect(() => {
    reload();
  }, [reload]);

  if (error) return <Alert tone="danger">{error}</Alert>;
  if (!order || !form) return <p className="text-sm text-muted">Loading…</p>;

  const set = (k: FormKey) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm({ ...form, [k]: e.target.value });
  const dirty = FORM_KEYS.filter((k) => (form[k] ?? "") !== (order[k] === null || order[k] === undefined ? "" : String(order[k])));
  const save = async () => {
    setSaving(true);
    try {
      const body = Object.fromEntries(dirty.map((k) => {
        const v = form[k].trim();
        return [k, v === "" ? null : k === "supplier_account_id" ? Number(v) : v];
      })) as OrderPatch;
      show(await ordersApi.update(order.id, body));
      push({ title: "Order saved" });
    } catch (e) {
      push({ title: "Not saved", description: errorText(e), tone: "danger" });
    } finally {
      setSaving(false);
    }
  };
  const changeStatus = async () => {
    if (!nextStatus) return;
    setSaving(true);
    try {
      show(await ordersApi.setStatus(order.id, nextStatus, statusNote));
      push({ title: `Status changed to ${STATUS_LABEL[nextStatus]}` });
      setNextStatus("");
      setStatusNote("");
    } catch (e) {
      push({ title: "Status not changed", description: errorText(e), tone: "danger" });
    } finally {
      setSaving(false);
    }
  };

  const PAY_LABEL = { pending: "Pending", settled: "Settled", cost_missing: "Cost missing", not_due: "Not due (cancelled)" } as const;
  const PAY_TONE = { pending: "warning", settled: "success", cost_missing: "danger", not_due: "neutral" } as const;
  const p = order.profit;
  // Without a purchase cost the "profit" would just be the revenue: say it is incomplete instead of showing 100 %.
  const noCost = p.missing.includes("purchase_cost");
  const address = ADDRESS_ORDER.map((k) => order.ship_address[k]).filter(Boolean);
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader
        title={`Etsy order #${order.external_id}`}
        description={`${order.buyer_name ?? "Buyer"} · ordered ${dateTime(order.ordered_at)}${order.ship_by ? ` · ship by ${dateTime(order.ship_by)}` : ""}`}
        back={{ href: "/channels/etsy/orders", label: "Etsy orders" }}
        actions={
          <a href={order.external_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-accent underline">
            Open on Etsy <Icon name="external" className="size-4" />
          </a>
        }
      />
      <Panel>
        <PanelBody>
          <StatusSteps status={order.status} />
        </PanelBody>
      </Panel>
      {order.past_order ? (
        <Alert>This order was already shipped when Etsy was connected. It is kept for history and reports and is never flagged; you can still add its costs.</Alert>
      ) : null}
      {order.attention.length > 0 ? (
        <Alert tone="danger">Needs attention: {order.attention.map((a) => ATTENTION_LABEL[a] ?? a).join(" · ")}</Alert>
      ) : null}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="grid grid-cols-[minmax(0,1fr)] content-start gap-6">
          <Panel>
            <PanelHeader title="Items" description="From Etsy; read-only." />
            <ul className="divide-y divide-line">
              {order.line_items.map((i) => (
                <li key={i.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                  <Thumb src={i.image} size="lg" />
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{i.quantity}× {i.title}</span>
                    <span className="block text-xs text-muted">
                      {[i.sku, ...i.variations.map((v) => `${v.name}: ${v.value}`)].filter(Boolean).join(" · ") || "No SKU"}
                    </span>
                  </span>
                  <span className="num">{m(Number(i.unit_price) * i.quantity)}</span>
                </li>
              ))}
            </ul>
            <PanelBody>
              <dl className="divide-y divide-line">
                <Row label="Items">{m(order.items_total)}</Row>
                <Row label="Shipping charged">{m(order.shipping_charged)}</Row>
                <Row label="Discounts">{Number(order.discounts) ? `−${m(order.discounts)}` : "—"}</Row>
                <Row label="Sales tax (collected for the state, not revenue)">{m(order.tax)}</Row>
                <Row label="Buyer paid" strong>{m(order.grand_total)}</Row>
              </dl>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Costs and tracking" description={order.costs_prefilled ? "Purchase cost was filled in from the listing's default cost. Check it." : "What you paid and how it was shipped."} />
            <PanelBody className="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-2">
              <Field label="Purchase cost ($)">{(f) => <Input {...f} inputMode="decimal" value={form.purchase_cost} onChange={set("purchase_cost")} />}</Field>
              <Field label="Actual shipping cost ($)">{(f) => <Input {...f} inputMode="decimal" value={form.shipping_cost} onChange={set("shipping_cost")} />}</Field>
              <Field label="Supplier">
                {(f) => (
                  <Select {...f} value={form.supplier_account_id} onChange={(e) => setForm({ ...form, supplier_account_id: e.target.value })} disabled={!canEdit}>
                    <option value="">No supplier</option>
                    {suppliers.map((s) => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
                    {order.supplier_account_id && !suppliers.some((s) => s.id === order.supplier_account_id) && (
                      <option value={String(order.supplier_account_id)}>{order.supplier_name ?? `Account #${order.supplier_account_id}`}</option>
                    )}
                  </Select>
                )}
              </Field>
              <Field label="Supplier order number">{(f) => <Input {...f} value={form.supplier_order_number} onChange={set("supplier_order_number")} maxLength={100} />}</Field>
              <Field label="Carrier">{(f) => <Input {...f} value={form.carrier} onChange={set("carrier")} placeholder="USPS, UPS, FedEx…" maxLength={60} />}</Field>
              <Field label="Tracking number" hint="Sending it to Etsy automatically comes in a later phase.">{(f) => <Input {...f} value={form.tracking_number} onChange={set("tracking_number")} maxLength={100} />}</Field>
              <Field label="Buyer phone (optional)" hint="Etsy doesn't share it.">{(f) => <Input {...f} type="tel" value={form.buyer_phone} onChange={set("buyer_phone")} maxLength={50} />}</Field>
              <div className="sm:col-span-2">
                <Field label="Notes (team only)">{(f) => <Textarea {...f} rows={3} value={form.notes} onChange={set("notes")} maxLength={5000} />}</Field>
              </div>
              <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
                {canEdit && <Button size="sm" onClick={save} disabled={saving || dirty.length === 0}>{saving ? "Saving…" : "Save order"}</Button>}
                {dirty.length ? <span className="text-sm text-muted">{dirty.length} unsaved change{dirty.length > 1 ? "s" : ""}</span> : null}
              </div>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="History" description="Every status change and edit, by Etsy or by your team." />
            <ol className="divide-y divide-line">
              {order.history.map((h) => (
                <li key={h.id} className="flex flex-wrap justify-between gap-x-4 gap-y-1 px-5 py-3 text-sm">
                  <span className="min-w-0">
                    <span className="block">{h.message}</span>
                    <span className="block text-xs text-muted">{h.source === "etsy" ? "Etsy" : h.source === "supplier" ? `${h.actor_name ?? "Supplier"} (supplier)` : h.actor_name ?? "Team"}</span>
                  </span>
                  <time className="text-xs text-muted" dateTime={h.created_at}>{dateTime(h.created_at)}</time>
                </li>
              ))}
              {order.history.length === 0 ? <li className="px-5 py-3 text-sm text-muted">No changes yet.</li> : null}
            </ol>
          </Panel>
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)] content-start gap-6">
          <Panel>
            <PanelHeader title="Status" />
            <PanelBody className="grid grid-cols-[minmax(0,1fr)] gap-3">
              <div><Pill tone={STATUS_TONE[order.status] ?? "neutral"}>{STATUS_LABEL[order.status] ?? order.status}</Pill></div>
              {canEdit && <>
              <Field label="Change status to">
                {(f) => (
                  <Select {...f} value={nextStatus} onChange={(e) => setNextStatus(e.target.value)}>
                    <option value="">Choose…</option>
                    <optgroup label="Main path">{MAIN_PATH.filter((s) => s !== order.status).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</optgroup>
                    <optgroup label="Exceptions">{EXCEPTIONS.filter((s) => s !== order.status).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}</optgroup>
                  </Select>
                )}
              </Field>
              <Field label="Note (optional)">{(f) => <Input {...f} value={statusNote} onChange={(e) => setStatusNote(e.target.value)} maxLength={300} />}</Field>
              <div><Button size="sm" variant="secondary" onClick={changeStatus} disabled={saving || !nextStatus}>Change status</Button></div>
              </>}
              <p className="text-xs text-muted">Etsy updates New, Cancelled, Shipped and Delivered by itself and never moves an order backwards.</p>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Supplier payment" description="Purchase cost + shipping cost, paid to the supplier." />
            <PanelBody className="grid grid-cols-[minmax(0,1fr)] gap-3">
              <div><Pill tone={PAY_TONE[order.supplier_payment]}>{PAY_LABEL[order.supplier_payment]}</Pill></div>
              <dl className="divide-y divide-line">
                <Row label="Owed">{m(order.supplier_owed)}</Row>
                {order.supplier_paid_at ? <Row label="Paid">{m(order.supplier_paid_amount)} on {order.supplier_paid_at.slice(0, 10)}</Row> : null}
                {order.supplier_payment_ref ? <Row label="Reference">{order.supplier_payment_ref}</Row> : null}
              </dl>
              {order.supplier_payment === "cost_missing" ? <p className="text-xs text-muted">Enter the purchase cost first.</p> : null}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Profit" />
            <PanelBody>
              <dl className="divide-y divide-line">
                <Row label="Revenue (items + shipping − discounts)">{m(p.revenue)}</Row>
                <Row label="Purchase cost">{m(order.purchase_cost)}</Row>
                <Row label="Shipping cost">{m(order.shipping_cost)}</Row>
                <Row label="Etsy fees">{order.marketplace_fees == null ? <span className="text-muted">Later phase</span> : m(order.marketplace_fees)}</Row>
                <Row label="Total cost">{m(p.total_cost)}</Row>
                <Row label="Net profit" strong>
                  {noCost ? <span className="font-normal text-muted">Enter the purchase cost</span> : <span className={Number(p.net_profit) < 0 ? "text-danger" : undefined}>{m(p.net_profit)}</span>}
                </Row>
                <Row label="Margin">{noCost || p.margin_pct == null ? "—" : `${Number(p.margin_pct).toFixed(1)}%`}</Row>
                <Row label="Days from payment to shipping">{p.days_to_ship ?? "—"}</Row>
              </dl>
              {p.missing.length ? <p className="mt-3 text-xs text-muted">Not included yet: {p.missing.map((k) => MISSING_LABEL[k] ?? k).join(", ")}.</p> : null}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Buyer and shipping" description="Only for fulfilling this order." />
            <PanelBody>
              <dl className="divide-y divide-line">
                <Row label="Buyer">{order.buyer_name ?? "—"}</Row>
                <Row label="Etsy buyer ID">{order.external_buyer_id ?? "—"}</Row>
                <Row label="Email">{order.buyer_email ?? <span className="text-muted">Not shared by Etsy</span>}</Row>
                <Row label="Ship to"><span className="whitespace-pre-line">{address.join("\n") || "—"}</span></Row>
              </dl>
              {order.buyer_note ? <p className="mt-3 rounded-md bg-sand p-3 text-sm"><span className="font-medium">Buyer note:</span> {order.buyer_note}</p> : null}
              {order.gift_message ? <p className="mt-3 rounded-md bg-sand p-3 text-sm"><span className="font-medium">Gift message:</span> {order.gift_message}</p> : null}
            </PanelBody>
          </Panel>
        </div>
      </div>
    </div>
  );
}
