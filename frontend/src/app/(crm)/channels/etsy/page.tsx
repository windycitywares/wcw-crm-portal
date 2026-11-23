"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BarList } from "@/components/charts/BarList";
import { ChartFrame } from "@/components/charts/ChartFrame";
import { ColumnChart } from "@/components/charts/ColumnChart";
import { LineChart, lineTable } from "@/components/charts/LineChart";
import { dayLabel, fmtInt, money, pct } from "@/components/charts/format";
import { Button, ButtonLink } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { formatDateTime } from "@/lib/utils";
import { channelsApi, type EtsyConnection } from "@/modules/channels/api";
import { STATUS_LABEL } from "@/modules/channels/orders";
import { SupplierFilter } from "@/modules/channels/SupplierFilter";
import { shortTitles, Stat, Thumb } from "@/modules/channels/ui";
import { UrnSetupNotice } from "@/modules/urns/UrnSetupNotice";

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
function presetRange(days: number) {
  const to = new Date();
  const from = new Date(to);
  from.setDate(to.getDate() - (days - 1));
  return { from: iso(from), to: iso(to) };
}

function bucketFormat(granularity: RangeInfo["granularity"] | undefined) {
  return (x: string, long?: boolean) =>
    granularity === "month"
      ? new Date(`${x}T12:00:00`).toLocaleDateString("en-US", { month: long ? "long" : "short", year: "numeric" })
      : granularity === "week"
        ? `${long ? "Week of " : ""}${dayLabel(x, "short")}`
        : dayLabel(x, long ? "long" : "short");
}

function formatKpi(k: Kpi): string {
  if (k.value === null || k.value === undefined) return "—";
  if (k.format === "money") return money(k.value);
  if (k.format === "percent") return pct(k.value);
  if (k.format === "decimal") return k.value.toFixed(1);
  return fmtInt(k.value);
}

/** The period's headline numbers, each against the period before. */
function KpiStrip({ kpis }: { kpis?: Kpi[] }) {
  const items: Partial<Kpi>[] = kpis ?? ["Orders", "Items sold", "Revenue", "Net profit", "Margin", "Days to ship"].map((label) => ({ key: label, label }));
  return (
    <dl className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
      {items.map((k) => {
        const kpi = k as Kpi;
        const good = kpi.change == null || kpi.better === "none" ? null : (kpi.better === "down" ? kpi.change < 0 : kpi.change > 0);
        return (
          <div key={k.key} className="rounded-[var(--radius-card)] bg-surface p-4 shadow-[var(--shadow-card)]" title={kpi.help || undefined}>
            <dt className="text-sm text-muted">{k.label}</dt>
            <dd className="num font-admin mt-1 text-2xl font-bold">{kpis ? formatKpi(kpi) : "—"}</dd>
            {kpis && kpi.change != null && (
              <dd className={good ? "text-xs text-success" : good === false ? "text-xs text-danger" : "text-xs text-muted"}>
                {kpi.change > 0 ? "▲" : kpi.change < 0 ? "▼" : "■"} {pct(Math.abs(kpi.change))} <span className="text-muted">vs previous period</span>
              </dd>
            )}
          </div>
        );
      })}
    </dl>
  );
}

function Alert({ children }: { children: React.ReactNode }) {
  return <p role="alert" className="rounded-[var(--radius-control)] bg-danger/12 px-4 py-3 text-sm text-danger">{children}</p>;
}

interface Summary {
  orders: number;
  cancelled: number;
  units: number;
  revenue: number;
  aov: number | null;
  cost: number;
  profit: number | null;
  margin: number | null;
  cost_coverage: number | null;
  costed_orders: number;
  avg_days_to_ship: number | null;
  on_time_rate: number | null;
  cancel_rate: number | null;
}
interface SupplierRow extends Summary {
  supplier_account_id: number | null;
  supplier: string | null;
}
interface RangeInfo { start: string; end: string; days: number; granularity: "day" | "week" | "month"; previous_start: string; previous_end: string }
interface Kpi { key: string; label: string; value: number | null; previous: number | null; change: number | null; format: string; help: string; better: "up" | "down" | "none" }
interface Dashboard {
  range: RangeInfo;
  kpis: Kpi[];
  totals: Summary;
  previous: Summary;
  series: { bucket: string; label: string; orders: number; units: number; revenue: number; cost: number; profit: number | null }[];
  statuses: Record<string, number>;
  top_products: { listing_id: number | null; title: string; image?: string | null; units: number; orders: number; revenue: number; profit: number | null; margin: number | null }[];
  suppliers: SupplierRow[];
  places: { label: string; orders: number; revenue: number }[];
  options: { products: { listing_id: number; title: string }[] };
}

const STATUS_ORDER = ["new", "purchased", "shipped", "delivered", "closed", "issue", "replacement", "return_requested", "returned", "refunded", "cancelled"];
const m = (n: number | null | undefined) => (n == null ? "—" : money(n));
const rate = (n: number | null | undefined) => (n == null ? "—" : pct(n));
const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

/** Etsy → Dashboard: how the Etsy shop is doing — sales, costs, profit, products, suppliers, shipping — for a period. */
export default function EtsyDashboard() {
  const { can } = useAuth();
  const [range, setRange] = useState(() => presetRange(30));
  const [preset, setPreset] = useState("30");
  const [listing, setListing] = useState("");
  const [supplier, setSupplier] = useState("");
  const [conn, setConn] = useState<EtsyConnection | null>(null);
  useEffect(() => { void channelsApi.etsy.connection().then(setConn).catch(() => setConn(null)); }, []);
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    const p = new URLSearchParams({ start: range.from, end: range.to });
    if (listing) p.set("listing_id", listing);
    if (supplier) p.set("supplier", supplier);
    apiFetch<Dashboard>(`/channels/etsy/dashboard?${p}`)
      .then((d) => {
        if (!live) return;
        setData(d);
        setError(null);
      })
      .catch((e) => {
        if (live) setError(errorText(e));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [range.from, range.to, listing, supplier]);

  const t = data?.totals;
  const series = data?.series ?? [];
  const x = series.map((s) => s.bucket);
  const xFormat = bucketFormat(data?.range.granularity);
  const per = data?.range.granularity ?? "day";
  const costed = (t?.costed_orders ?? 0) > 0;
  const money3 = [
    { key: "revenue", label: "Revenue", values: series.map((s) => s.revenue), color: "var(--color-accent)" },
    { key: "profit", label: "Net profit", values: series.map((s) => s.profit), color: "var(--viz-3)" },
    { key: "cost", label: "Costs", values: series.map((s) => (s.cost ? s.cost : null)), color: "var(--viz-2)" },
  ];
  const filtered = !!(listing || supplier);
  const products = data?.top_products ?? [];
  const names = shortTitles(products.map((p) => p.title));
  const topRevenue = Math.max(1, ...products.map((p) => p.revenue));
  const statusTotal = Object.values(data?.statuses ?? {}).reduce((a, b) => a + b, 0);
  const statusRows = STATUS_ORDER.filter((s) => data?.statuses[s]);
  const supplierColumns: Column<SupplierRow>[] = [
    { key: "s", header: "Supplier", cell: (r) => r.supplier ?? <span className="text-muted">Not set</span> },
    { key: "o", header: "Orders", align: "right", cell: (r) => fmtInt(r.orders) },
    { key: "r", header: "Revenue", align: "right", cell: (r) => m(r.revenue) },
    { key: "c", header: "Costs", align: "right", hide: "sm", cell: (r) => m(r.cost) },
    { key: "p", header: "Profit", align: "right", cell: (r) => <span className={(r.profit ?? 0) < 0 ? "text-danger" : undefined}>{m(r.profit)}</span> },
    { key: "mg", header: "Margin", align: "right", hide: "sm", cell: (r) => rate(r.margin) },
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader title="Etsy" description="Sales, costs and profit of your Etsy shop, with what sells, where it goes and how fast it ships."
        actions={<div className="flex flex-wrap gap-2">
          <ButtonLink href="/channels/etsy/orders?view=attention" size="sm">Orders needing attention</ButtonLink>
          <ButtonLink href="/channels/etsy/listings" size="sm" variant="secondary">Listings</ButtonLink>
          <ButtonLink href="/channels/etsy/payments" size="sm" variant="secondary">Supplier payments</ButtonLink>
          <ButtonLink href="/channels/etsy/products" size="sm" variant="secondary">Products</ButtonLink>
        </div>} />
      <UrnSetupNotice />
      {conn && (
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted">
          {conn.connected ? <Pill tone="success">Connected</Pill> : <Pill tone="warning">Not connected</Pill>}
          {conn.shop_name}
          {conn.connected && <span>· orders synced {conn.orders_synced_at ? formatDateTime(conn.orders_synced_at) : "not yet"}</span>}
          {conn.last_error && <span className="text-danger">· {conn.last_error}</span>}
          {!conn.connected && can("channels:manage") && <Link href="/settings/channels" className="font-medium text-accent-strong hover:underline">Connect Etsy</Link>}
        </p>
      )}

      <div className="flex flex-wrap items-end gap-3 rounded-[var(--radius-card)] bg-surface p-4 shadow-[var(--shadow-card,0_0_0_1px_var(--color-line))]" role="group" aria-label="Filters">
        <Field label="Dates">
          {(p) => (
            <Select {...p} value={preset} onChange={(e) => { setPreset(e.target.value); if (e.target.value !== "custom") setRange(presetRange(Number(e.target.value))); }}>
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
              <option value="365">Last 12 months</option>
              <option value="custom">Custom dates</option>
            </Select>
          )}
        </Field>
        {preset === "custom" && <>
          <Field label="From">{(p) => <Input {...p} type="date" value={range.from} max={range.to} onChange={(e) => e.target.value && setRange({ ...range, from: e.target.value })} />}</Field>
          <Field label="To">{(p) => <Input {...p} type="date" value={range.to} min={range.from} onChange={(e) => e.target.value && setRange({ ...range, to: e.target.value })} />}</Field>
        </>}
        <Field label="Product" className="w-full sm:w-72">
          {(p) => (
            <Select {...p} value={listing} onChange={(e) => setListing(e.target.value)}>
              <option value="">All products</option>
              {data?.options.products.map((o) => <option key={o.listing_id} value={o.listing_id}>{o.title.split(" - ")[0]}</option>)}
            </Select>
          )}
        </Field>
        <SupplierFilter value={supplier} onChange={setSupplier} />
        {filtered ? <Button variant="ghost" size="sm" onClick={() => { setListing(""); setSupplier(""); }}>Clear filters</Button> : null}
        <span className="ml-auto self-center text-xs text-muted">Compared with the {data ? `${data.range.days} days before` : "period before"}</span>
      </div>

      {error ? <Alert>{error}</Alert> : null}

      <KpiStrip kpis={data?.kpis} />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel>
          <PanelBody>
            <ChartFrame title="Revenue" description={`Per ${per}, after discounts and before tax.`}
              table={{ columns: ["Date", "Revenue", "Orders"], rows: series.map((s) => [xFormat(s.bucket, true), money(s.revenue), s.orders]) }}>
              <ColumnChart x={x} values={series.map((s) => s.revenue)} seriesLabel="Revenue" yFormat={(n) => money(n, { compact: true })}
                xFormat={xFormat} label={`Revenue per ${per}`} height={240} loading={loading && !data} />
            </ChartFrame>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Where orders are now" description={`${fmtInt(statusTotal)} orders in this period`} />
          <PanelBody className="grid gap-4">
            {statusTotal ? (
              <div className="flex h-3 overflow-hidden rounded-full bg-sand" aria-hidden="true">
                {statusRows.map((s, i) => (
                  <span key={s} style={{ width: `${(data!.statuses[s] / statusTotal) * 100}%`, background: s === "cancelled" ? "var(--color-muted)" : `var(--viz-${(i % 8) + 1})` }} />
                ))}
              </div>
            ) : null}
            <ul className="grid gap-2 text-sm">
              {statusRows.map((s, i) => (
                <li key={s} className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2">
                    <span aria-hidden="true" className="size-2.5 rounded-full" style={{ background: s === "cancelled" ? "var(--color-muted)" : `var(--viz-${(i % 8) + 1})` }} />
                    {STATUS_LABEL[s] ?? s}
                  </span>
                  <span className="num font-semibold">{fmtInt(data!.statuses[s])}</span>
                </li>
              ))}
              {!statusTotal ? <li className="text-muted">No orders in this period.</li> : null}
            </ul>
            <Link href="/channels/etsy/orders" className="text-sm font-medium text-accent-strong hover:underline">Open orders</Link>
          </PanelBody>
        </Panel>
      </div>

      <Panel>
        <PanelBody>
          {costed ? (
            <ChartFrame
              title="Revenue, costs and profit"
              description={`Per ${per}. Counts orders that have a purchase cost; before Etsy fees.`}
              legend={money3.map((s) => ({ label: s.label, color: s.color }))}
              table={lineTable(x, money3, (n) => money(n), xFormat)}
            >
              <LineChart x={x} series={money3} yFormat={(n) => money(n, { compact: true })} xFormat={xFormat} area={false}
                label="Revenue, costs and net profit over the period" loading={loading && !data} />
            </ChartFrame>
          ) : (
            <div className="grid place-items-center gap-2 py-8 text-center">
              <h3 className="text-base">Profit appears here once costs are in</h3>
              <p className="max-w-md text-sm text-muted">
                {t?.orders ? `None of the ${fmtInt(t.orders)} orders in this period has a purchase cost yet.` : "No orders in this period."} Add what you paid on each order,
                or set a default cost on each listing so new orders fill it in.
              </p>
              <div className="flex flex-wrap justify-center gap-3 text-sm font-medium">
                <Link href="/channels/etsy/orders?view=attention" className="text-accent-strong hover:underline">Enter costs on orders</Link>
                <Link href="/channels/etsy/listings" className="text-accent-strong hover:underline">Set listing costs</Link>
              </div>
            </div>
          )}
          {costed && (t?.cost_coverage ?? 1) < 1 ? (
            <p className="mt-3 text-xs text-muted">
              Profit counts {fmtInt(t!.costed_orders)} of {fmtInt(t!.orders)} orders ({rate(t!.cost_coverage)}).{" "}
              <Link href="/channels/etsy/orders?view=attention" className="underline">Enter the missing costs</Link>.
            </p>
          ) : null}
        </PanelBody>
      </Panel>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Panel>
          <PanelHeader title="Best sellers" description="By revenue in this period." />
          <PanelBody>
            {products.length ? (
              <ol className="grid gap-3">
                {products.map((p, i) => (
                  <li key={`${p.listing_id ?? p.title}`} className="flex items-center gap-3">
                    <span className="num w-5 text-right text-xs text-muted">{i + 1}</span>
                    <Thumb src={p.image} size="sm" />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline justify-between gap-3">
                        <span className="truncate font-medium" title={p.title}>{names[i]}</span>
                        <span className="num shrink-0 font-semibold">{m(p.revenue)}</span>
                      </span>
                      <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-sand" aria-hidden="true">
                        <span className="block h-full rounded-full bg-accent" style={{ width: `${(p.revenue / topRevenue) * 100}%` }} />
                      </span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {fmtInt(p.units)} sold{p.profit == null ? "" : ` · ${m(p.profit)} profit (${rate(p.margin)})`}
                      </span>
                    </span>
                  </li>
                ))}
              </ol>
            ) : <p className="py-6 text-center text-sm text-muted">Nothing sold in this period.</p>}
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Where buyers are" description="US states, or the country outside the US." />
          <PanelBody>
            <BarList
              items={(data?.places ?? []).map((p) => ({ label: p.label, value: p.revenue, display: m(p.revenue), sub: `${fmtInt(p.orders)} order${p.orders === 1 ? "" : "s"}` }))}
              color="var(--viz-7)"
              empty="No orders in this period."
            />
          </PanelBody>
        </Panel>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Panel>
          <PanelHeader title="Suppliers" description="Revenue, costs and profit of each supplier's orders." />
          <div className="relative"><DataTable columns={supplierColumns} rows={data ? data.suppliers : null} rowKey={(r) => r.supplier_account_id ?? "none"} caption="Suppliers" loading={loading} empty="No orders in this period." /></div>
        </Panel>
        <div className="grid grid-cols-2 content-start gap-4">
          <Stat label="Days to ship" value={t?.avg_days_to_ship == null ? "—" : t.avg_days_to_ship.toFixed(1)} sub="Average, payment to shipping" />
          <Stat label="On time" value={rate(t?.on_time_rate)} sub="Shipped by Etsy's date" tone={t?.on_time_rate != null && t.on_time_rate < 0.9 ? "warning" : undefined} />
          <Stat label="Average order" value={m(t?.aov)} sub="Revenue ÷ orders" />
          <Stat label="Cancelled" value={t ? fmtInt(t.cancelled) : "—"} sub={t ? `${rate(t.cancel_rate)} of orders` : undefined} />
        </div>
      </div>
    </div>
  );
}
