"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { channelsApi, type EtsyConnection } from "@/modules/channels/api";

/** Etsy at a glance. The dashboard (sales, profit, what needs attention) arrives with orders. */
export default function EtsyHome() {
  const { can } = useAuth();
  const [conn, setConn] = useState<EtsyConnection | null>(null);
  useEffect(() => { void channelsApi.etsy.connection().then(setConn).catch(() => setConn(null)); }, []);
  return (
    <>
      <PageHeader title="Etsy" description="Your Etsy shop, worked from the CRM: listings now, orders and the dashboard next." />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-2">
        <Panel>
          <PanelHeader title="Connection" />
          <PanelBody className="space-y-2 text-sm">
            {conn ? (
              <>
                <p>{conn.connected ? <Pill tone="success">Connected</Pill> : <Pill tone="warning">Not connected</Pill>} {conn.shop_name}</p>
                <p className="text-muted">Listings synced {conn.listings_synced_at ? formatDateTime(conn.listings_synced_at) : "not yet"} · orders synced {conn.orders_synced_at ? formatDateTime(conn.orders_synced_at) : "not yet"}</p>
                {conn.last_error && <p className="text-danger">{conn.last_error}</p>}
              </>
            ) : <p className="text-muted">Loading…</p>}
            {can("channels:manage") && <Link href="/settings/channels" className="text-accent-strong hover:underline">Settings → Sales channels</Link>}
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Orders" description="Paid Etsy orders: purchase from the supplier, ship, track, see the profit." />
          <PanelBody className="flex flex-wrap gap-4 text-sm font-medium">
            <Link href="/channels/etsy/orders?view=attention" className="text-accent-strong hover:underline">Needs attention</Link>
            <Link href="/channels/etsy/orders" className="text-accent-strong hover:underline">Open orders</Link>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Listings" description="Etsy's products, with the supplier and what each costs you." />
          <PanelBody><Link href="/channels/etsy/listings" className="text-sm font-medium text-accent-strong hover:underline">Open Etsy listings</Link></PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Supplier payments" description="What each supplier is owed and what you've paid, with exports for the books." />
          <PanelBody><Link href="/channels/etsy/payments" className="text-sm font-medium text-accent-strong hover:underline">Open supplier payments</Link></PanelBody>
        </Panel>
      </div>
    </>
  );
}
