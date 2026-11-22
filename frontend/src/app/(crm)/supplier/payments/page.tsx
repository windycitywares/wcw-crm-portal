"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiDownload, apiFetch } from "@/lib/client-api";
import { fmtInt } from "@/components/charts/format";
import { formatDateTime as dateTime } from "@/lib/utils";
import { PAYMENT_LABEL, PAYMENT_TONE } from "@/modules/channels/supplier";
import { money, Stat } from "@/modules/channels/ui";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { Segmented } from "@/components/ui/Segmented";
import { useToast } from "@/components/ui/Toast";
import { Button } from "@/components/ui/Button";

function Alert({ tone, children }: { tone?: "danger"; children: React.ReactNode }) {
  return <p role={tone === "danger" ? "alert" : "status"} className={tone === "danger" ? "rounded-[var(--radius-control)] bg-danger/12 px-4 py-3 text-sm text-danger" : "rounded-[var(--radius-control)] bg-sand px-4 py-3 text-sm"}>{children}</p>;
}

type State = "pending" | "settled" | "all";
interface Row {
  id: number;
  external_id: number;
  ordered_at: string;
  supplier_order_number: string | null;
  items: string;
  owed: string | null;
  payment_status: keyof typeof PAYMENT_LABEL;
  paid_at: string | null;
  paid_amount: string | null;
  payment_ref: string | null;
}
interface Data {
  pending_count: number;
  pending_amount: string;
  settled_count: number;
  settled_amount: string;
  items: Row[];
  total: number;
}
const PAGE_SIZE = 50;
const m = (v: string | null | undefined) => (v == null ? "—" : money(v));

/** What the shop owes this supplier, and what it has paid — with an export for their books. */
export default function SupplierPayments() {
  const { push } = useToast();
  const [state, setState] = useState<State>("pending");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      setData(await apiFetch<Data>(`/supplier-portal/etsy/payments?state=${state}&page=${page}&page_size=${PAGE_SIZE}`));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    }
  }, [state, page]);
  useEffect(() => {
    void load();
  }, [load]);

  const exportAs = (format: "csv" | "xlsx") =>
    apiDownload(`/supplier-portal/etsy/payments/export?state=${state}&format=${format}`, `payments-${state}.${format}`).catch((e) =>
      push({ title: "Export failed", description: e instanceof Error ? e.message : undefined, tone: "danger" }));

  const columns: Column<Row>[] = [
    { key: "o", header: "Order", cell: (r) => <Link href={`/supplier/orders/${r.id}`} className="font-medium text-accent-strong hover:underline">#{r.external_id}<span className="block text-xs font-normal text-muted">{dateTime(r.ordered_at)}</span></Link> },
    { key: "ref", header: "Your order #", hide: "sm", cell: (r) => r.supplier_order_number ?? "—" },
    { key: "i", header: "Items", hide: "md", cell: (r) => <span className="line-clamp-2 max-w-72">{r.items}</span> },
    { key: "a", header: "Amount", align: "right", cell: (r) => <span className="num">{m(r.owed)}</span> },
    { key: "s", header: "Payment", cell: (r) => <Pill tone={PAYMENT_TONE[r.payment_status]}>{PAYMENT_LABEL[r.payment_status]}</Pill> },
    { key: "p", header: "Paid", hide: "sm", cell: (r) => (r.paid_at ? <span className="text-sm">{m(r.paid_amount)} on {r.paid_at.slice(0, 10)}{r.payment_ref ? <span className="block text-xs text-muted">{r.payment_ref}</span> : null}</span> : "—") },
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader
        title="Your payments"
        description="What Windy City Wares owes you for Etsy orders (item + shipping) and what has been paid."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => exportAs("csv")}>Export CSV</Button>
            <Button size="sm" variant="secondary" onClick={() => exportAs("xlsx")}>Export Excel</Button>
          </div>
        }
      />
      {error ? <Alert tone="danger">{error}</Alert> : null}
      <div className="grid grid-cols-2 gap-4">
        <Stat label="Not paid yet" value={data ? m(data.pending_amount) : "—"} sub={data ? `${fmtInt(data.pending_count)} orders` : undefined} tone={data?.pending_count ? "warning" : undefined}
          active={state === "pending"} onClick={() => { setState("pending"); setPage(1); }} />
        <Stat label="Paid" value={data ? m(data.settled_amount) : "—"} sub={data ? `${fmtInt(data.settled_count)} orders` : undefined} tone="success"
          active={state === "settled"} onClick={() => { setState("settled"); setPage(1); }} />
      </div>
      <Panel>
        <div className="border-b border-line p-4">
          <Segmented<State> label="Payments" value={state} onChange={(v) => { setState(v); setPage(1); }} options={[
            { value: "pending", label: `Not paid yet${data ? ` (${data.pending_count})` : ""}` },
            { value: "settled", label: `Paid${data ? ` (${data.settled_count})` : ""}` },
            { value: "all", label: "All" },
          ]} />
        </div>
        <div className="relative"><DataTable columns={columns} rows={data ? data.items : null} rowKey={(r) => r.id} caption="Your payments" empty="Nothing here yet." /></div>
        {data && data.total > PAGE_SIZE ? <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} /> : null}
      </Panel>
    </div>
  );
}
