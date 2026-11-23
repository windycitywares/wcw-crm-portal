"use client";

import { useEffect, useState } from "react";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { apiFetch } from "@/lib/client-api";
import { formatDate } from "@/lib/utils";

/** The supplier's Etsy figures, from the CRM's own Etsy orders: open orders, money, shipping speed. */
export interface ShopSupplierStats {
  listings: number;
  orders: number;
  open_orders: number;
  to_ship: number;
  late: number;
  owed: string;
  owed_orders: number;
  paid: string;
  avg_days_to_ship_90d: number | null;
  on_time_rate_90d: number | null;
  last_order_at: string | null;
}

export const shopSuppliersApi = {
  stats: (accountId: number) => apiFetch<ShopSupplierStats>(`/channels/etsy/supplier-stats/${accountId}`),
};

const usd = (v: string | number) => Number(v).toLocaleString("en-US", { style: "currency", currency: "USD" });

export function ShopPerformancePanel({ accountId }: { accountId: number }) {
  const [stats, setStats] = useState<ShopSupplierStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    shopSuppliersApi.stats(accountId).then(
      (s) => live && setStats(s),
      (e: unknown) => live && setError(e instanceof Error ? e.message : "Couldn't load the Etsy figures"),
    );
    return () => {
      live = false;
    };
  }, [accountId]);

  const cells: [string, string, string?][] = stats
    ? [
        ["Open orders", stats.open_orders.toLocaleString(), stats.to_ship ? `${stats.to_ship} to ship${stats.late ? `, ${stats.late} late` : ""}` : "Nothing to ship"],
        ["Owed", usd(stats.owed), `${stats.owed_orders} order${stats.owed_orders === 1 ? "" : "s"} not paid yet`],
        ["Paid so far", usd(stats.paid)],
        ["Days to ship", stats.avg_days_to_ship_90d == null ? "—" : stats.avg_days_to_ship_90d.toFixed(1), "Average, last 90 days"],
        ["On time", stats.on_time_rate_90d == null ? "—" : `${Math.round(stats.on_time_rate_90d * 100)}%`, "Shipped by Etsy's date, 90 days"],
        ["Orders", stats.orders.toLocaleString(), stats.last_order_at ? `Last ${formatDate(stats.last_order_at)}` : "None yet"],
      ]
    : [];
  return (
    <Panel>
      <PanelHeader title="On Etsy" description="Etsy orders this supplier fulfils, what you owe them, and how fast they ship." />
      <PanelBody>
        {error ? (
          <p className="text-sm text-muted">{error}</p>
        ) : !stats ? (
          <div className="h-24 animate-pulse rounded-md bg-sand" />
        ) : (
          <>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {cells.map(([label, value, sub]) => (
                <div key={label}>
                  <dt className="text-xs text-muted">{label}</dt>
                  <dd className="mt-0.5 text-lg font-semibold tabular-nums">{value}</dd>
                  {sub ? <dd className="text-xs text-muted">{sub}</dd> : null}
                </div>
              ))}
            </dl>
            <p className="mt-4 text-xs text-muted">
              {stats.listings} Etsy listing{stats.listings === 1 ? "" : "s"} use this supplier.{" "}
              <a href={`/channels/etsy/payments`} className="text-accent-strong underline">Supplier payments</a>{" · "}
              <a href={`/channels/etsy/orders?supplier=${accountId}`} className="text-accent-strong underline">Their orders</a>
            </p>
          </>
        )}
      </PanelBody>
    </Panel>
  );
}
