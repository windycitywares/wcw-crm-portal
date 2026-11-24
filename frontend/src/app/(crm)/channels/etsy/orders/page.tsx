"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { Segmented } from "@/components/ui/Segmented";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { ATTENTION_LABEL, EXCEPTIONS, MAIN_PATH, ordersApi, STATUS_LABEL, STATUS_TONE, type OrderFilters, type OrderPage, type OrderSummary } from "@/modules/channels/orders";
import { SupplierFilter } from "@/modules/channels/SupplierFilter";
import { money, Stat, Thumb } from "@/modules/channels/ui";
import { RecalculateCostsDialog } from "@/modules/urns/RecalculateCostsDialog";

type View = "attention" | "open" | "all";
const PAGE_SIZE = 25;
const OPEN = ["new", "purchased", "shipped", "issue", "replacement", "return_requested"];

export default function EtsyOrdersPage() {
  const { can } = useAuth();
  const [recalc, setRecalc] = useState(false);
  const [view, setView] = useState<View>("open");
  const [status, setStatus] = useState("");
  const [supplier, setSupplier] = useState("");
  const [q, setQ] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [applied, setApplied] = useState({ q: "", from: "", to: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<OrderPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get("view") === "attention") setView("attention");
    if (p.get("status")) { setView("all"); setStatus(p.get("status") ?? ""); }
    if (p.get("supplier")) setSupplier(p.get("supplier") ?? "");
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    const f: OrderFilters = { page, page_size: PAGE_SIZE };
    if (status) f.status = status;
    else if (view === "open") f.status = "open";
    if (view === "attention") f.attention = true;
    if (applied.q) f.q = applied.q;
    if (supplier) f.supplier = supplier;
    if (applied.from) f.date_from = applied.from;
    if (applied.to) f.date_to = applied.to;
    try {
      setData(await ordersApi.list(f));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load orders");
    } finally {
      setLoading(false);
    }
  }, [page, view, status, applied, supplier]);
  useEffect(() => { void load(); }, [load]);

  const pick = (v: View, s = "") => { setView(v); setStatus(s); setPage(1); };
  const openCount = data ? OPEN.reduce((n, s) => n + (data.counts[s] ?? 0), 0) : undefined;

  const columns: Column<OrderSummary>[] = [
    {
      key: "order", header: "Order",
      cell: (o) => (
        <Link href={`/channels/etsy/orders/${o.id}`} className="flex min-w-0 items-center gap-3 font-medium text-accent-strong hover:underline">
          <Thumb src={o.items[0]?.image} size="sm" />
          <span className="min-w-0">
            #{o.external_id}
            <span className="block truncate text-xs font-normal text-muted">{o.buyer_name ?? "Buyer"} · {formatDateTime(o.ordered_at)}</span>
          </span>
        </Link>
      ),
    },
    { key: "items", header: "Items", hide: "md",
      cell: (o) => <span className="line-clamp-2 max-w-64" title={o.items.map((i) => `${i.quantity}× ${i.title}`).join(", ")}>{o.items.map((i) => `${i.quantity}× ${i.title.split(" - ")[0]}`).join(", ")}</span> },
    { key: "supplier", header: "Supplier", hide: "lg", cell: (o) => o.supplier_name ?? <span className="text-xs text-muted">—</span> },
    { key: "status", header: "Status", cell: (o) => <Pill tone={STATUS_TONE[o.status] ?? "neutral"}>{STATUS_LABEL[o.status] ?? o.status}</Pill> },
    { key: "revenue", header: "Revenue", align: "right", hide: "sm", cell: (o) => <span className="num">{money(o.profit.revenue, o.currency)}</span> },
    { key: "profit", header: "Profit", align: "right",
      cell: (o) => o.profit.missing.includes("purchase_cost") ? <span className="text-xs text-muted">Cost missing</span>
        : <span className={Number(o.profit.net_profit) < 0 ? "num font-medium text-danger" : "num"}>{money(o.profit.net_profit, o.currency)}</span> },
    { key: "attention", header: <span className="sr-only">Needs attention</span>,
      cell: (o) => o.attention.length ? (
        <span className="inline-flex items-center gap-1 text-xs text-danger" title={o.attention.map((a) => ATTENTION_LABEL[a] ?? a).join(" · ")}>
          <Icon name="alert" className="size-4" />
          <span className="hidden lg:inline">{ATTENTION_LABEL[o.attention[0]] ?? o.attention[0]}{o.attention.length > 1 ? ` +${o.attention.length - 1}` : ""}</span>
          <span className="sr-only lg:hidden">{o.attention.map((a) => ATTENTION_LABEL[a] ?? a).join(", ")}</span>
        </span>
      ) : null },
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader title="Etsy orders" back={{ href: "/channels/etsy", label: "Etsy" }}
        description="Paid Etsy orders arrive here on their own within minutes. Enter what you paid and how you shipped; profit follows."
        actions={can("channels:manage") ? (
          <Button size="sm" variant="secondary" onClick={() => setRecalc(true)}>
            Recalculate costs
          </Button>
        ) : undefined} />
      <RecalculateCostsDialog open={recalc} onClose={() => setRecalc(false)} onDone={() => void load()} />
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Needs attention" value={data ? data.attention : "—"} sub="Late, unpurchased or missing a cost" tone={data?.attention ? "danger" : undefined}
          active={view === "attention" && !status} onClick={() => pick("attention")} />
        <Stat label="To purchase" value={data ? data.counts.new ?? 0 : "—"} sub="New, paid on Etsy" tone={data?.counts.new ? "warning" : undefined}
          active={status === "new"} onClick={() => pick("all", "new")} />
        <Stat label="To ship" value={data ? data.counts.purchased ?? 0 : "—"} sub="Purchased, not shipped"
          active={status === "purchased"} onClick={() => pick("all", "purchased")} />
        <Stat label="Shipped" value={data ? data.counts.shipped ?? 0 : "—"} sub="Delivery not confirmed yet"
          active={status === "shipped"} onClick={() => pick("all", "shipped")} />
      </div>
      <Panel>
        <div className="border-b border-line p-4">
          <Segmented<View> label="Which orders" value={view} onChange={(v) => pick(v)} options={[
            { value: "attention", label: `Needs attention${data ? ` (${data.attention})` : ""}` },
            { value: "open", label: `Open${openCount !== undefined ? ` (${openCount})` : ""}` },
            { value: "all", label: "All" },
          ]} />
        </div>
        <form className="grid grid-cols-[minmax(0,1fr)] gap-3 border-b border-line p-4 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr_1fr_auto] lg:items-end"
          onSubmit={(e) => { e.preventDefault(); setPage(1); setApplied({ q: q.trim(), from, to }); }}>
          <Field label="Search">{(p) => <Input {...p} maxLength={120} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Order #, buyer, item, SKU, tracking" />}</Field>
          <Field label="Status">
            {(p) => (
              <Select {...p} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
                <option value="">{view === "open" ? "Any open" : "Any"}</option>
                <optgroup label="Main path">{MAIN_PATH.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}{data ? ` (${data.counts[s] ?? 0})` : ""}</option>)}</optgroup>
                <optgroup label="Exceptions">{EXCEPTIONS.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}{data ? ` (${data.counts[s] ?? 0})` : ""}</option>)}</optgroup>
              </Select>
            )}
          </Field>
          <SupplierFilter value={supplier} onChange={(v) => { setSupplier(v); setPage(1); }} />
          <Field label="From">{(p) => <Input {...p} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />}</Field>
          <Field label="To">{(p) => <Input {...p} type="date" value={to} onChange={(e) => setTo(e.target.value)} />}</Field>
          <Button type="submit" size="sm">Filter orders</Button>
        </form>
        <div className="relative">
          <DataTable columns={columns} rows={data ? data.items : null} rowKey={(o) => o.id} caption="Etsy orders" loading={loading}
            empty={view === "attention" ? "Nothing needs attention." : "No Etsy orders match. New paid orders appear within a few minutes."} />
        </div>
        {data && data.total > PAGE_SIZE && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />}
      </Panel>
    </div>
  );
}
