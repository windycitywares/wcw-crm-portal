"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/client-api";
import { fmtInt } from "@/components/charts/format";
import { formatDateTime as dateTime } from "@/lib/utils";
import { PAYMENT_LABEL, PAYMENT_TONE, type SupplierOrder } from "@/modules/channels/supplier";
import { money, Stat, Thumb } from "@/modules/channels/ui";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { Segmented } from "@/components/ui/Segmented";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";

function Alert({ tone, children }: { tone?: "danger"; children: React.ReactNode }) {
  return <p role={tone === "danger" ? "alert" : "status"} className={tone === "danger" ? "rounded-[var(--radius-control)] bg-danger/12 px-4 py-3 text-sm text-danger" : "rounded-[var(--radius-control)] bg-sand px-4 py-3 text-sm"}>{children}</p>;
}

type View = "to_ship" | "shipped" | "all";
interface Page {
  items: SupplierOrder[];
  total: number;
  counts: Record<View, number>;
}
const PAGE_SIZE = 20;
const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

/** A supplier's home: their Etsy orders to ship, what they shipped, and what they're owed. */
export default function SupplierOrders() {
  const [me, setMe] = useState<{ supplier_name: string | null } | null>(null);
  const [owed, setOwed] = useState<{ pending_amount: string; pending_count: number } | null>(null);
  const [view, setView] = useState<View>("to_ship");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<{ supplier_name: string | null }>("/supplier-portal/me").then(setMe, () => undefined);
    apiFetch<{ pending_amount: string; pending_count: number }>("/supplier-portal/etsy/payments?state=pending&page_size=1").then(setOwed, () => undefined);
  }, []);
  const load = useCallback(async () => {
    try {
      const p = new URLSearchParams({ view, page: String(page), page_size: String(PAGE_SIZE) });
      if (query) p.set("q", query);
      setData(await apiFetch<Page>(`/supplier-portal/etsy/orders?${p}`));
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }, [view, page, query]);
  useEffect(() => {
    void load();
  }, [load]);

  const late = data?.items.filter((o) => o.late).length ?? 0;
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader title="Your Etsy orders" description={me?.supplier_name ? `Orders Windy City Wares placed with ${me.supplier_name}. Ship them, add the tracking number, and see what you're owed.` : "Your orders to ship."} />
      {error ? <Alert tone="danger">{error}</Alert> : null}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <Stat label="To ship" value={data ? fmtInt(data.counts.to_ship) : "—"} sub={late ? `${late} past the ship-by date` : "Oldest ship-by date first"}
          tone={late ? "danger" : data?.counts.to_ship ? "warning" : undefined} active={view === "to_ship"} onClick={() => { setView("to_ship"); setPage(1); }} />
        <Stat label="Shipped" value={data ? fmtInt(data.counts.shipped) : "—"} sub="With tracking" active={view === "shipped"} onClick={() => { setView("shipped"); setPage(1); }} />
        <Link href="/supplier/payments" className="block">
          <Stat label="Owed to you" value={owed ? money(owed.pending_amount) : "—"} sub={owed ? `${fmtInt(owed.pending_count)} orders not paid yet` : undefined} />
        </Link>
      </div>

      <Panel>
        <div className="border-b border-line p-4">
          <Segmented<View> label="Which orders" value={view} onChange={(v) => { setView(v); setPage(1); }} options={[
            { value: "to_ship", label: `To ship${data ? ` (${data.counts.to_ship})` : ""}` },
            { value: "shipped", label: `Shipped${data ? ` (${data.counts.shipped})` : ""}` },
            { value: "all", label: `All${data ? ` (${data.counts.all})` : ""}` },
          ]} />
        </div>
        <form className="flex flex-wrap items-end gap-3 border-b border-line p-4" onSubmit={(e) => { e.preventDefault(); setPage(1); setQuery(q.trim()); }}>
          <Field label="Search" className="min-w-52 flex-1">{(p) => <Input {...p} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Order #, buyer, item, your order #" />}</Field>
          <Button type="submit" size="sm">Search orders</Button>
        </form>
        <ul className="divide-y divide-line">
          {!data ? <li className="p-4 text-sm text-muted">Loading…</li> : null}
          {data && data.items.length === 0 ? <li className="p-8 text-center text-sm text-muted">{view === "to_ship" ? "Nothing to ship right now." : "No orders here yet."}</li> : null}
          {data?.items.map((o) => (
            <li key={o.id}>
              <Link href={`/supplier/orders/${o.id}`} className="flex flex-wrap items-start gap-4 p-4 hover:bg-sand focus-visible:outline-2 focus-visible:outline-accent">
                <Thumb src={o.items[0]?.image} size="lg" />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    <span className="text-accent-strong">#{o.external_id}</span>
                    <Pill tone={o.status === "shipped" || o.status === "delivered" ? "success" : "info"}>{o.status_label}</Pill>
                    {o.late ? <Pill tone="danger">Late</Pill> : null}
                  </p>
                  <ul className="mt-1 text-sm">
                    {o.items.map((i, n) => (
                      <li key={n}>
                        {i.quantity}× {i.title.split(" - ")[0]}
                        {i.variations.length ? <span className="text-muted"> · {i.variations.map((v) => `${v.name}: ${v.value}`).join(" · ")}</span> : null}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1 text-xs text-muted">
                    For {o.buyer_name ?? "the buyer"} · ordered {dateTime(o.ordered_at)}
                    {o.ship_by ? ` · ship by ${dateTime(o.ship_by)}` : ""}
                    {o.tracking_number ? ` · tracking ${o.tracking_number}` : ""}
                  </p>
                </div>
                <div className="text-right text-sm">
                  <span className="num block font-semibold">{o.owed ? money(o.owed) : "—"}</span>
                  <Pill tone={PAYMENT_TONE[o.payment]}>{PAYMENT_LABEL[o.payment]}</Pill>
                </div>
              </Link>
            </li>
          ))}
        </ul>
        {data && data.total > PAGE_SIZE ? <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} /> : null}
      </Panel>
    </div>
  );
}
