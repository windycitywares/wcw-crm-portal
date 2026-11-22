"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/client-api";
import { formatDateTime as dateTime } from "@/lib/utils";
import { PAYMENT_LABEL, PAYMENT_TONE, type SupplierOrderDetail } from "@/modules/channels/supplier";
import { money, StatusSteps, Thumb } from "@/modules/channels/ui";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";

function Alert({ tone, children }: { tone?: "danger"; children: React.ReactNode }) {
  return <p role={tone === "danger" ? "alert" : "status"} className={tone === "danger" ? "rounded-[var(--radius-control)] bg-danger/12 px-4 py-3 text-sm text-danger" : "rounded-[var(--radius-control)] bg-sand px-4 py-3 text-sm"}>{children}</p>;
}

const ADDRESS_ORDER = ["name", "first_line", "second_line", "city", "state", "zip", "country_iso"];
const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

/** One order for the supplier: what to make and where to send it; tracking in, mark shipped. */
export default function SupplierOrderPage() {
  const { id } = useParams<{ id: string }>();
  const { push } = useToast();
  const [o, setO] = useState<SupplierOrderDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ref, setRef] = useState("");
  const [carrier, setCarrier] = useState("");
  const [tracking, setTracking] = useState("");
  const [busy, setBusy] = useState(false);

  const show = useCallback((d: SupplierOrderDetail) => {
    setO(d);
    setRef(d.supplier_order_number ?? "");
    setCarrier(d.carrier ?? "");
    setTracking(d.tracking_number ?? "");
  }, []);
  useEffect(() => {
    apiFetch<SupplierOrderDetail>(`/supplier-portal/etsy/orders/${id}`).then(show, (e) => setError(errorText(e)));
  }, [id, show]);

  if (error) return <Alert tone="danger">{error}</Alert>;
  if (!o) return <p className="text-sm text-muted">Loading…</p>;

  const toShip = o.status === "new" || o.status === "purchased";
  const save = async () => {
    setBusy(true);
    try {
      show(await apiFetch<SupplierOrderDetail>(`/supplier-portal/etsy/orders/${o.id}`, {
        method: "PATCH",
        body: JSON.stringify({ supplier_order_number: ref.trim() || null, carrier: carrier.trim() || null, tracking_number: tracking.trim() || null }),
      }));
      push({ title: "Saved" });
    } catch (e) {
      push({ title: "Not saved", description: errorText(e), tone: "danger" });
    } finally {
      setBusy(false);
    }
  };
  const shipped = async () => {
    setBusy(true);
    try {
      if (ref.trim() !== (o.supplier_order_number ?? "")) {
        await apiFetch(`/supplier-portal/etsy/orders/${o.id}`, { method: "PATCH", body: JSON.stringify({ supplier_order_number: ref.trim() || null }) });
      }
      show(await apiFetch<SupplierOrderDetail>(`/supplier-portal/etsy/orders/${o.id}/shipped`, {
        method: "POST", body: JSON.stringify({ carrier: carrier.trim() || null, tracking_number: tracking.trim() }),
      }));
      push({ title: "Marked shipped", description: "Windy City Wares can see the tracking number now." });
    } catch (e) {
      push({ title: "Not marked shipped", description: errorText(e), tone: "danger" });
    } finally {
      setBusy(false);
    }
  };
  const address = ADDRESS_ORDER.map((k) => o.ship_address[k]).filter(Boolean);

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader
        title={`Order #${o.external_id}`}
        description={`For ${o.buyer_name ?? "the buyer"} · ordered ${dateTime(o.ordered_at)}${o.ship_by ? ` · ship by ${dateTime(o.ship_by)}` : ""}`}
        back={{ href: "/supplier", label: "Your orders" }}
      />
      {o.late ? <Alert tone="danger">This order is past Etsy's ship-by date. Please ship it as soon as you can.</Alert> : null}
      <Panel><PanelBody><StatusSteps status={o.status} /></PanelBody></Panel>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="grid grid-cols-[minmax(0,1fr)] content-start gap-6">
          <Panel>
            <PanelHeader title="What to make" description="Exactly as the buyer ordered it, including any personalisation." />
            <ul className="divide-y divide-line">
              {o.items.map((i, n) => (
                <li key={n} className="flex items-start gap-4 px-5 py-4">
                  <Thumb src={i.image} size="lg" />
                  <div className="min-w-0 text-sm">
                    <p className="font-medium">{i.quantity}× {i.title}</p>
                    {i.sku ? <p className="text-xs text-muted">SKU {i.sku}</p> : null}
                    {i.variations.length ? (
                      <dl className="mt-2 grid gap-1">
                        {i.variations.map((v) => (
                          <div key={v.name} className="flex flex-wrap gap-x-2">
                            <dt className="text-muted">{v.name}:</dt>
                            <dd className="font-medium">{v.value}</dd>
                          </div>
                        ))}
                      </dl>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
            {o.buyer_note || o.gift_message ? (
              <PanelBody className="grid gap-2 border-t border-line">
                {o.buyer_note ? <p className="rounded-md bg-sand p-3 text-sm"><span className="font-medium">Buyer's note:</span> {o.buyer_note}</p> : null}
                {o.gift_message ? <p className="rounded-md bg-sand p-3 text-sm"><span className="font-medium">Gift message (include it):</span> {o.gift_message}</p> : null}
              </PanelBody>
            ) : null}
          </Panel>

          <Panel>
            <PanelHeader title="Shipping" description={toShip ? "Add the tracking number, then mark it shipped." : "Shipped. You can still correct the details."} />
            <PanelBody className="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-3">
              <Field label="Your order number">{(p) => <Input {...p} value={ref} onChange={(e) => setRef(e.target.value)} maxLength={100} />}</Field>
              <Field label="Carrier">{(p) => <Input {...p} value={carrier} onChange={(e) => setCarrier(e.target.value)} placeholder="USPS, UPS…" maxLength={60} />}</Field>
              <Field label="Tracking number">{(p) => <Input {...p} value={tracking} onChange={(e) => setTracking(e.target.value)} maxLength={100} />}</Field>
              <div className="flex flex-wrap gap-3 sm:col-span-3">
                {toShip ? <Button size="sm" onClick={shipped} disabled={busy || !tracking.trim()}>{busy ? "Saving…" : "Mark shipped"}</Button> : null}
                <Button size="sm" variant="secondary" onClick={save} disabled={busy}>Save details</Button>
              </div>
            </PanelBody>
          </Panel>
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)] content-start gap-6">
          <Panel>
            <PanelHeader title="Ship to" />
            <PanelBody><p className="whitespace-pre-line text-sm">{address.join("\n") || "—"}</p></PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title="Your payment" />
            <PanelBody className="grid gap-2 text-sm">
              <Pill tone={PAYMENT_TONE[o.payment]}>{PAYMENT_LABEL[o.payment]}</Pill>
              <p>Amount: <span className="num font-semibold">{o.owed ? money(o.owed) : "—"}</span></p>
              {o.paid_at ? <p>Paid {money(o.paid_amount ?? 0)} on {o.paid_at.slice(0, 10)}{o.payment_ref ? ` (ref ${o.payment_ref})` : ""}</p> : null}
            </PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title="History" />
            <ol className="divide-y divide-line">
              {o.history.map((h) => (
                <li key={h.id} className="px-5 py-3 text-sm">
                  <span className="block">{h.message}</span>
                  <span className="text-xs text-muted">{h.source === "etsy" ? "Etsy" : h.actor_name ?? "Windy City Wares"} · {dateTime(h.created_at)}</span>
                </li>
              ))}
            </ol>
          </Panel>
        </div>
      </div>
    </div>
  );
}
