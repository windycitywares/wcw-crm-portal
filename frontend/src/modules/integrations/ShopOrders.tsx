"use client";

import { useEffect, useState } from "react";
import { Pill, type Tone } from "@/components/ui/Pill";
import { formatDate } from "@/lib/utils";
import { shopApi, type ShopOrder } from "./api";

const TONE: Record<string, Tone> = { paid: "success", processing: "info", shipped: "info", delivered: "success", pending: "warning", cancelled: "neutral", refunded: "danger" };
const LABEL: Record<string, string> = { pending: "Awaiting payment", paid: "Paid", processing: "Preparing", shipped: "Shipped", delivered: "Delivered", cancelled: "Cancelled", refunded: "Refunded" };

function money(value: string, currency: string) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: currency || "USD" }).format(Number(value));
}

/** The customer's shop orders, newest first (kept up to date by the shop connection). */
export function ShopOrders({ customerId, refreshKey }: { customerId: number; refreshKey?: unknown }) {
  const [orders, setOrders] = useState<ShopOrder[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    shopApi
      .customerOrders(customerId)
      .then((list) => {
        setOrders(list);
        setError(false);
      })
      .catch(() => setError(true));
  }, [customerId, refreshKey]);

  if (error) return <p className="text-sm text-muted">Couldn&apos;t load the orders.</p>;
  if (!orders) return <p className="text-sm text-muted">Loading orders…</p>;
  if (orders.length === 0) return <p className="text-sm text-muted">No shop orders yet.</p>;
  return (
    <ul className="divide-y divide-line" aria-label="Shop orders">
      {orders.map((o) => (
        <li key={o.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2 text-sm">
          <span className="min-w-0">
            <span className="font-medium">{o.number}</span>
            <span className="block text-xs text-muted">{o.placed_at ? formatDate(o.placed_at) : "Not placed"}</span>
          </span>
          <span className="flex items-center gap-3">
            <Pill tone={TONE[o.status] ?? "neutral"}>{LABEL[o.status] ?? o.status}</Pill>
            <span className="tabular-nums">
              {money(o.grand_total, o.currency)}
              {Number(o.refunded_total) > 0 && <span className="block text-right text-xs text-danger">−{money(o.refunded_total, o.currency)}</span>}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}
