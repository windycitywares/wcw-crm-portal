"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { apiDownload, apiFetch } from "@/lib/client-api";
import { formatDateTime as dateTime } from "@/lib/utils";
import { SettleDialog } from "@/modules/channels/SettleDialog";
import { SupplierFilter } from "@/modules/channels/SupplierFilter";
import { money } from "@/modules/channels/ui";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { ConfirmDialog } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { Segmented } from "@/components/ui/Segmented";
import { useToast } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";

const fmtInt = (n: number) => new Intl.NumberFormat().format(n);
function Alert({ tone, children }: { tone?: "danger"; children: React.ReactNode }) {
  return <div role={tone === "danger" ? "alert" : "status"} className={tone === "danger" ? "rounded-[var(--radius-control)] bg-danger/12 px-4 py-3 text-sm text-danger" : "rounded-[var(--radius-control)] bg-sand px-4 py-3 text-sm"}>{children}</div>;
}

type State = "pending" | "settled" | "cost_missing" | "all";
interface Row {
  id: number;
  external_id: number;
  ordered_at: string;
  status: string;
  buyer_name: string | null;
  supplier_account_id: number | null;
  supplier: string | null;
  supplier_order_number: string | null;
  items: string;
  purchase_cost: string | null;
  shipping_cost: string | null;
  owed: string | null;
  payment_status: "pending" | "settled" | "cost_missing" | "not_due";
  paid_at: string | null;
  paid_amount: string | null;
  payment_ref: string | null;
  paid_by: string | null;
}
interface SupplierSum {
  supplier_account_id: number | null;
  supplier: string | null;
  pending_count: number;
  pending_amount: string;
  settled_count: number;
  settled_amount: string;
}
interface Overview {
  suppliers: SupplierSum[];
  pending_count: number;
  pending_amount: string;
  settled_count: number;
  settled_amount: string;
  cost_missing: number;
}

const PAGE_SIZE = 50;
const m = (v: string | number | null | undefined) => money(v);
const LABEL: Record<Row["payment_status"], string> = { pending: "Pending", settled: "Settled", cost_missing: "Cost missing", not_due: "Not due" };
const TONE = { pending: "warning", settled: "success", cost_missing: "danger", not_due: "neutral" } as const;
const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);

/** Etsy → Supplier payments: what is owed to each supplier, what has been paid, and the export for the books. */
export default function SupplierPaymentsPage() {
  const { can } = useAuth();
  const admin = can("channels:payments");
  const { push } = useToast();
  const [state, setState] = useState<State>("pending");
  const [supplier, setSupplier] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [settling, setSettling] = useState<Row[] | null>(null);
  const [undoing, setUndoing] = useState<Row | null>(null);
  const [undoReason, setUndoReason] = useState("");
  const [busy, setBusy] = useState(false);

  const filters = useMemo(() => {
    const p = new URLSearchParams();
    if (supplier) p.set("supplier", supplier);
    if (from) p.set("date_from", from);
    if (to) p.set("date_to", to);
    return p;
  }, [supplier, from, to]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = new URLSearchParams(filters);
      list.set("state", state);
      list.set("page", String(page));
      list.set("page_size", String(PAGE_SIZE));
      const [ov, r] = await Promise.all([
        apiFetch<Overview>(`/channels/etsy/supplier-payments/overview?${filters}`),
        apiFetch<{ items: Row[]; total: number }>(`/channels/etsy/supplier-payments?${list}`),
      ]);
      setOverview(ov);
      setRows(r.items);
      setTotal(r.total);
      setSelected(new Set());
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [filters, state, page]);
  useEffect(() => {
    void load();
  }, [load]);

  const exportAs = async (format: "csv" | "xlsx") => {
    const p = new URLSearchParams(filters);
    p.set("state", state);
    p.set("format", format);
    try {
      await apiDownload(`/channels/etsy/supplier-payments/export?${p}`, `supplier-payments-${state}.${format}`);
    } catch (e) {
      push({ title: "Export failed", description: errorText(e), tone: "danger" });
    }
  };
  /** A clean printable statement (Save as PDF from the print dialog). Uses every row for the filters, not just this page. */
  const printStatement = async () => {
    const p = new URLSearchParams(filters);
    p.set("state", state);
    p.set("page_size", "200");
    const win = window.open("", "_blank");
    if (!win) {
      push({ title: "Allow pop-ups to print", tone: "danger" });
      return;
    }
    try {
      let all: Row[] = [];
      for (let pg = 1; pg < 50; pg++) {
        p.set("page", String(pg));
        const r = await apiFetch<{ items: Row[]; total: number }>(`/channels/etsy/supplier-payments?${p}`);
        all = all.concat(r.items);
        if (all.length >= r.total || r.items.length === 0) break;
      }
      const sum = all.reduce((n, r) => n + Number((state === "settled" ? r.paid_amount : r.owed) ?? 0), 0);
      const title = `Supplier payments — ${state === "cost_missing" ? "Cost missing" : state[0].toUpperCase() + state.slice(1)}${supplier ? ` — ${supplier === "none" ? "No supplier" : all[0]?.supplier ?? "Supplier"}` : ""}`;
      const body = all.map((r) => `<tr><td>${r.external_id}</td><td>${r.ordered_at.slice(0, 10)}</td><td>${esc(r.supplier ?? "")}</td><td>${esc(r.supplier_order_number ?? "")}</td><td>${esc(r.items)}</td><td class=n>${m(r.owed)}</td><td>${LABEL[r.payment_status]}</td><td>${r.paid_at ? r.paid_at.slice(0, 10) : ""}</td><td class=n>${r.paid_amount ? m(r.paid_amount) : ""}</td><td>${esc(r.payment_ref ?? "")}</td></tr>`).join("");
      win.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${esc(title)}</title><style>
        body{font:12px/1.4 system-ui,sans-serif;margin:24px;color:#111}h1{font-size:18px;margin:0 0 4px}p{margin:0 0 12px;color:#555}
        table{width:100%;border-collapse:collapse}th,td{border-bottom:1px solid #ddd;padding:5px 6px;text-align:left;vertical-align:top}
        th{background:#f3f3f3}.n{text-align:right;white-space:nowrap}tfoot td{font-weight:700;border-top:2px solid #111}
      </style></head><body><h1>${esc(title)}</h1><p>Windy City Wares · ${from || "all dates"} – ${to || "today"} · printed ${new Date().toLocaleString()}</p>
      <table><thead><tr><th>Etsy order</th><th>Date</th><th>Supplier</th><th>Supplier order #</th><th>Items</th><th class=n>Owed</th><th>Payment</th><th>Paid on</th><th class=n>Paid</th><th>Reference</th></tr></thead>
      <tbody>${body}</tbody><tfoot><tr><td colspan=5>${all.length} orders</td><td class=n colspan=5>${state === "settled" ? "Paid" : "Total"}: ${m(sum)}</td></tr></tfoot></table>
      <script>window.onload=()=>window.print()</script></body></html>`);
      win.document.close();
    } catch (e) {
      win.close();
      push({ title: "Couldn't prepare the statement", description: errorText(e), tone: "danger" });
    }
  };

  const undo = async () => {
    if (!undoing) return;
    setBusy(true);
    try {
      await apiFetch(`/channels/etsy/supplier-payments/${undoing.id}/undo`, { method: "POST", body: JSON.stringify({ reason: undoReason || null }) });
      push({ title: "Payment undone", description: `Order #${undoing.external_id} is pending again.` });
      setUndoing(null);
      void load();
    } catch (e) {
      push({ title: "Payment not undone", description: errorText(e), tone: "danger" });
    } finally {
      setBusy(false);
    }
  };

  const selectable = admin && state === "pending";
  const chosen = (rows ?? []).filter((r) => selected.has(r.id));
  const chosenTotal = chosen.reduce((n, r) => n + Number(r.owed ?? 0), 0);
  const toggle = (id: number) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const allOnPage = !!rows?.length && rows.every((r) => selected.has(r.id));

  const columns: Column<Row>[] = [
    ...(selectable
      ? [{
          key: "pick",
          header: (
            <input type="checkbox" aria-label="Select all on this page" checked={allOnPage}
              onChange={() => setSelected(allOnPage ? new Set() : new Set((rows ?? []).map((r) => r.id)))} />
          ),
          cell: (r: Row) => <input type="checkbox" aria-label={`Select order ${r.external_id}`} checked={selected.has(r.id)} onChange={() => toggle(r.id)} />,
        } satisfies Column<Row>]
      : []),
    {
      key: "order",
      header: "Order",
      cell: (r) => (
        <Link href={`/channels/etsy/orders/${r.id}`} className="block font-medium text-accent-strong hover:underline">
          #{r.external_id}
          <span className="block text-xs font-normal text-muted">{dateTime(r.ordered_at)}</span>
        </Link>
      ),
    },
    { key: "supplier", header: "Supplier", cell: (r) => <span>{r.supplier ?? <span className="text-muted">Not set</span>}{r.supplier_order_number ? <span className="block text-xs text-muted">#{r.supplier_order_number}</span> : null}</span> },
    { key: "items", header: "Items", hide: "lg", cell: (r) => <span className="line-clamp-2 max-w-72">{r.items}</span> },
    { key: "owed", header: "Owed", align: "right", cell: (r) => <span className="num">{m(r.owed)}</span> },
    { key: "status", header: "Payment", cell: (r) => <Pill tone={TONE[r.payment_status]}>{LABEL[r.payment_status]}</Pill> },
    {
      key: "paid",
      header: "Paid",
      hide: "md",
      cell: (r) => (r.paid_at ? (
        <span className="text-sm">{m(r.paid_amount)} on {r.paid_at.slice(0, 10)}<span className="block text-xs text-muted">{[r.payment_ref, r.paid_by].filter(Boolean).join(" · ")}</span></span>
      ) : <span className="text-muted">—</span>),
    },
    ...(admin
      ? [{
          key: "act",
          header: <span className="sr-only">Actions</span>,
          align: "right",
          cell: (r: Row) => r.payment_status === "pending"
            ? <Button size="sm" variant="secondary" onClick={() => setSettling([r])}>Mark paid</Button>
            : r.payment_status === "settled"
              ? <Button size="sm" variant="ghost" onClick={() => { setUndoReason(""); setUndoing(r); }}>Undo</Button>
              : null,
        } satisfies Column<Row>]
      : []),
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader
        title="Supplier payments"
        description="What you owe each supplier for Etsy orders (purchase cost + shipping cost) and what you have paid. Export it for your books."
        back={{ href: "/channels/etsy", label: "Etsy" }}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => exportAs("csv")}>Export CSV</Button>
            <Button size="sm" variant="secondary" onClick={() => exportAs("xlsx")}>Export Excel</Button>
            <Button size="sm" variant="secondary" onClick={printStatement}>Print or save PDF</Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-end gap-3" role="group" aria-label="Filters">
        <SupplierFilter value={supplier} onChange={(v) => { setSupplier(v); setPage(1); }} />
        <Field label={state === "settled" ? "Paid from" : "Ordered from"}>{(p) => <Input {...p} type="date" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1); }} />}</Field>
        <Field label="To">{(p) => <Input {...p} type="date" value={to} onChange={(e) => { setTo(e.target.value); setPage(1); }} />}</Field>
        {supplier || from || to ? <Button size="sm" variant="ghost" onClick={() => { setSupplier(""); setFrom(""); setTo(""); setPage(1); }}>Clear filters</Button> : null}
      </div>

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {overview && overview.cost_missing > 0 ? (
        <Alert>
          {fmtInt(overview.cost_missing)} order{overview.cost_missing === 1 ? " has" : "s have"} no purchase cost yet, so {overview.cost_missing === 1 ? "it isn't" : "they aren't"} counted as owed.{" "}
          <button type="button" className="font-medium underline" onClick={() => { setState("cost_missing"); setPage(1); }}>Show them</button>
        </Alert>
      ) : null}

      <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          ["Pending", overview ? m(overview.pending_amount) : "—", overview ? `${fmtInt(overview.pending_count)} orders to pay` : ""],
          ["Settled", overview ? m(overview.settled_amount) : "—", overview ? `${fmtInt(overview.settled_count)} orders paid` : ""],
          ["Suppliers owed", overview ? fmtInt(overview.suppliers.filter((s) => s.pending_count > 0).length) : "—", "with something pending"],
          ["Cost missing", overview ? fmtInt(overview.cost_missing) : "—", "orders not yet costed"],
        ].map(([label, value, sub]) => (
          <div key={label} className="rounded-[var(--radius-card)] border border-line bg-surface p-4">
            <dt className="text-sm text-muted">{label}</dt>
            <dd className="num font-admin mt-1 text-2xl font-bold">{value}</dd>
            <dd className="text-xs text-muted">{sub}</dd>
          </div>
        ))}
      </dl>

      <Panel>
        <PanelHeader title="By supplier" description="Click a supplier to see only their orders." />
        <DataTable
          columns={[
            { key: "s", header: "Supplier", cell: (s: SupplierSum) => (
              <button type="button" className="font-medium text-accent-strong hover:underline" onClick={() => { setSupplier(s.supplier_account_id ? String(s.supplier_account_id) : "none"); setPage(1); }}>
                {s.supplier ?? "Supplier not set"}
              </button>
            ) },
            { key: "pc", header: "Pending orders", align: "right", cell: (s: SupplierSum) => fmtInt(s.pending_count) },
            { key: "pa", header: "Pending", align: "right", cell: (s: SupplierSum) => <span className={s.pending_count ? "font-semibold" : undefined}>{m(s.pending_amount)}</span> },
            { key: "sc", header: "Settled orders", align: "right", hide: "sm", cell: (s: SupplierSum) => fmtInt(s.settled_count) },
            { key: "sa", header: "Settled", align: "right", cell: (s: SupplierSum) => m(s.settled_amount) },
          ]}
          rows={overview ? overview.suppliers : null}
          rowKey={(s) => s.supplier_account_id ?? "none"}
          caption="Amounts per supplier"
          empty="Nothing owed or paid for these filters."
        />
      </Panel>

      <Panel>
        <div className="border-b border-line p-4">
          <Segmented<State>
            label="Payment status"
            options={[
              { value: "pending", label: `Pending${overview ? ` (${overview.pending_count})` : ""}` },
              { value: "settled", label: `Settled${overview ? ` (${overview.settled_count})` : ""}` },
              { value: "cost_missing", label: `Cost missing${overview ? ` (${overview.cost_missing})` : ""}` },
              { value: "all", label: "All" },
            ]}
            value={state}
            onChange={(v) => { setState(v); setPage(1); }}
          />
        </div>
        {selectable && chosen.length > 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-sand px-4 py-3 text-sm" role="status">
            <span>{chosen.length} selected · {m(chosenTotal)}</span>
            <Button size="sm" onClick={() => setSettling(chosen)}>Mark {chosen.length} paid</Button>
          </div>
        ) : null}
        <div className="relative"><DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
          caption="Supplier payments"
          loading={loading}
          empty={state === "pending" ? "Nothing to pay for these filters." : state === "cost_missing" ? "Every order has a cost." : "Nothing here yet."}
        /></div>
        {total > PAGE_SIZE && <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />}
      </Panel>
      {!admin ? <p className="text-sm text-muted">Only an admin can mark payments.</p> : null}

      <SettleDialog open={!!settling} orders={settling ?? []} onClose={() => setSettling(null)} onDone={load} />
      <ConfirmDialog
        open={!!undoing}
        title={`Undo the payment for order #${undoing?.external_id ?? ""}?`}
        tone="primary"
        message={
          <div className="grid gap-3">
            <p>It goes back to Pending. The undo is kept in the order's history.</p>
            <Field label="Why (optional)">{(p) => <Input {...p} value={undoReason} onChange={(e) => setUndoReason(e.target.value)} maxLength={300} />}</Field>
          </div>
        }
        confirmLabel="Undo payment"
        busy={busy}
        onConfirm={undo}
        onCancel={() => setUndoing(null)}
      />
    </div>
  );
}
