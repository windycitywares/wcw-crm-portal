"use client";

import { useEffect, useState } from "react";
import Papa from "papaparse";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { TrendChart } from "@/components/ui/TrendChart";
import { useAuth } from "@/lib/auth";
import {
  reportsApi,
  type CustomerReport,
  type ReportBucket,
  type ReportsOverview,
  type SupplierListRow,
  type SupplierReport,
  type TicketReport,
  type TrendReport,
} from "@/modules/reports/api";

const windows = [7, 30, 90] as const;

function Metric({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="min-w-0 py-2">
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

function Breakdown({ title, rows }: { title: string; rows: ReportBucket[] }) {
  return (
    <div className="min-w-0">
      <h3 className="mb-2 text-sm font-medium">{title}</h3>
      {rows.length ? (
        <ul className="divide-y divide-line">
          {rows.map((row) => (
            <li key={row.label} className="flex items-center justify-between gap-3 py-2 text-sm">
              <span className="truncate text-muted">{row.label}</span>
              <span className="num font-medium">{row.count.toLocaleString()}</span>
            </li>
          ))}
        </ul>
      ) : <p className="py-2 text-sm text-muted">No records.</p>}
    </div>
  );
}

function formatMoney(value: string | number) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Number(value));
}

function formatRate(value: number | null) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function saveCsv(filename: string, rows: Record<string, string | number>[]) {
  const blob = new Blob([Papa.unparse(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadCsv(overview: ReportsOverview, customers: CustomerReport, tickets: TicketReport, suppliers: SupplierReport) {
  const rows: { section: string; metric: string; value: string | number }[] = [
    { section: "Sales", metric: "Open deals", value: overview.sales.open_count },
    { section: "Sales", metric: "Open pipeline value", value: overview.sales.open_value },
    { section: "Sales", metric: "Weighted forecast", value: overview.sales.weighted_value },
    { section: "Sales", metric: "Won this month", value: overview.sales.won_count },
    { section: "Sales", metric: "Won value this month", value: overview.sales.won_value },
    { section: "Sales", metric: "Lost this month", value: overview.sales.lost_count },
    { section: "Tickets", metric: "Open", value: overview.tickets.open },
    { section: "Tickets", metric: "Unassigned", value: overview.tickets.unassigned },
    { section: "Tickets", metric: "Overdue", value: overview.tickets.overdue },
    { section: "Campaigns", metric: "Window days", value: overview.campaigns.days },
    { section: "Campaigns", metric: "Campaigns", value: overview.campaigns.campaigns },
    { section: "Campaigns", metric: "Sent", value: overview.campaigns.sent },
    { section: "Campaigns", metric: "Opened", value: overview.campaigns.opened },
    { section: "Campaigns", metric: "Clicked", value: overview.campaigns.clicked },
    { section: "Campaigns", metric: "Unsubscribed", value: overview.campaigns.unsubscribed },
    { section: "Campaigns", metric: "Failed", value: overview.campaigns.failed },
    { section: "Campaigns", metric: "Skipped", value: overview.campaigns.skipped },
    { section: "Campaigns", metric: "Open rate", value: overview.campaigns.open_rate ?? "" },
    { section: "Campaigns", metric: "Click rate", value: overview.campaigns.click_rate ?? "" },
    { section: "Customers", metric: "Active customers", value: overview.active_customers },
    { section: "Suppliers", metric: "Active suppliers", value: overview.active_suppliers },
    { section: "Customers by type", metric: "Total", value: customers.total },
    { section: "Tickets by type", metric: "Total", value: tickets.total },
    { section: "Tickets by SLA", metric: "First response breached", value: tickets.first_response_breached },
    { section: "Tickets by SLA", metric: "Resolution breached", value: tickets.resolution_breached },
    { section: "Tickets by SLA", metric: "Open overdue", value: tickets.open_overdue },
    { section: "Suppliers", metric: "Average rating", value: suppliers.average_rating ?? "" },
    ...customers.by_type.map((item) => ({ section: "Customer type", metric: item.label, value: item.count })),
    ...customers.by_source.map((item) => ({ section: "Customer source", metric: item.label, value: item.count })),
    ...customers.by_status.map((item) => ({ section: "Customer status", metric: item.label, value: item.count })),
    ...tickets.by_type.map((item) => ({ section: "Ticket type", metric: item.label, value: item.count })),
    ...tickets.by_status.map((item) => ({ section: "Ticket status", metric: item.label, value: item.count })),
    ...tickets.by_priority.map((item) => ({ section: "Ticket priority", metric: item.label, value: item.count })),
    ...suppliers.by_type.map((item) => ({ section: "Supplier type", metric: item.label, value: item.count })),
    ...suppliers.by_status.map((item) => ({ section: "Supplier status", metric: item.label, value: item.count })),
  ];
  saveCsv("crm-report.csv", rows);
}

export default function ReportsPage() {
  const { can } = useAuth();
  const [campaignDays, setCampaignDays] = useState<number>(30);
  const [overview, setOverview] = useState<ReportsOverview | null>(null);
  const [customers, setCustomers] = useState<CustomerReport | null>(null);
  const [tickets, setTickets] = useState<TicketReport | null>(null);
  const [suppliers, setSuppliers] = useState<SupplierReport | null>(null);
  const [supplierRows, setSupplierRows] = useState<{ items: SupplierListRow[]; total: number; page: number; page_size: number } | null>(null);
  const [supplierPage, setSupplierPage] = useState(1);
  const [trend, setTrend] = useState<TrendReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!can("reports:view")) return;
    let active = true;
    setLoading(true);
    setError(null);
    void Promise.all([
      reportsApi.overview(campaignDays),
      reportsApi.customers(),
      reportsApi.tickets(),
      reportsApi.suppliers(),
      reportsApi.trend(campaignDays),
    ]).then(([overviewData, customerData, ticketData, supplierData, trendData]) => {
      if (!active) return;
      setOverview(overviewData);
      setCustomers(customerData);
      setTickets(ticketData);
      setSuppliers(supplierData);
      setTrend(trendData);
    }).catch((err: unknown) => {
      if (active) setError(err instanceof Error ? err.message : "Couldn't load reports");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [campaignDays, can]);

  useEffect(() => {
    if (!can("suppliers:view")) return;
    let active = true;
    void reportsApi.supplierList(supplierPage, 25).then((result) => {
      if (active) setSupplierRows(result);
    }).catch(() => {
      if (active) setSupplierRows(null);
    });
    return () => { active = false; };
  }, [supplierPage, can]);

  const exportSupplierRows = () => {
    if (!supplierRows) return;
    const csvRows: Record<string, string | number>[] = supplierRows.items.map((supplier) => ({
      name: supplier.name,
      supplier_type: supplier.supplier_type,
      status: supplier.status,
      primary_contact: supplier.contacts.find((contact) => contact.is_primary)?.name ?? "",
      email: supplier.contacts.find((contact) => contact.is_primary)?.email ?? "",
      lead_time_days: supplier.lead_time_days ?? "",
      currency: supplier.currency,
      rating: supplier.rating ?? "",
    }));
    saveCsv(`suppliers-page-${supplierPage}.csv`, csvRows);
  };

  if (!can("reports:view")) return <PageHeader title="Reports" description="You don't have permission to view reports." />;

  return (
    <>
      <PageHeader
        title="Reports"
        description="Sales, service, campaign, customer, and supplier activity."
        actions={
          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" disabled={!overview || !customers || !tickets || !suppliers || !trend} onClick={() => overview && customers && tickets && suppliers && downloadCsv(overview, customers, tickets, suppliers)}>
              <Icon name="download" className="size-4" /> Export CSV
            </Button>
          </div>
        }
      />

      {error && <div role="alert" className="mb-4 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</div>}
      {loading && !overview && <p className="mb-4 text-sm text-muted">Loading reports…</p>}

      {overview && customers && tickets && suppliers && trend && (
        <>
          <Panel className="mb-6">
            <PanelHeader title="Orders trend" description={`Orders placed over the last ${trend.points.length} days.`} />
            <PanelBody>
              <div className="flex items-center gap-3 mb-4">
                <label className="flex items-center gap-2 text-sm text-muted font-medium">
                  Window
                  <select value={campaignDays} onChange={(e) => setCampaignDays(Number(e.target.value))} className="h-9 rounded border border-line bg-surface px-2 text-sm text-ink">
                    {windows.map((days) => <option key={days} value={days}>{days} days</option>)}
                  </select>
                </label>
                <span className="mx-1 h-4 w-px bg-line" />
                <span className="text-sm font-medium text-ink">{trend.points.reduce((sum, p) => sum + p.count, 0).toLocaleString()} orders placed</span>
                <span className="text-xs text-muted">· ${trend.points.reduce((sum, p) => sum + Number(p.value || 0), 0).toLocaleString()} total</span>
              </div>
              <TrendChart points={trend.points} height={140} showValue />
            </PanelBody>
          </Panel>

          <div className="mb-6 grid gap-4 border-y border-line py-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Open pipeline value" value={formatMoney(overview.sales.open_value)} hint={`${overview.sales.open_count} open deals · raw amounts`} />
          <Metric label="Weighted forecast" value={formatMoney(overview.sales.weighted_value)} hint="Raw amounts, no FX conversion" />
          <Metric label="Open tickets" value={overview.tickets.open} hint={`${overview.tickets.overdue} overdue · ${overview.tickets.unassigned} unassigned`} />
          <Metric label="Active customers" value={overview.active_customers.toLocaleString()} hint={`${overview.active_suppliers.toLocaleString()} active suppliers`} />
        </div>

        <div className="grid items-start gap-6 xl:grid-cols-2">
          <Panel>
            <PanelHeader title="Campaign performance" description={`Campaigns started in the last ${overview.campaigns.days} days.`} />
            <PanelBody className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Metric label="Sent" value={overview.campaigns.sent} hint={`${overview.campaigns.failed} failed · ${overview.campaigns.skipped} skipped`} />
              <Metric label="Opened" value={overview.campaigns.opened} hint={formatRate(overview.campaigns.open_rate)} />
              <Metric label="Clicked" value={overview.campaigns.clicked} hint={formatRate(overview.campaigns.click_rate)} />
              <Metric label="Unsubscribed" value={overview.campaigns.unsubscribed} />
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Sales this month" description="Won and lost deals, alongside the current forecast." />
            <PanelBody className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric label="Won" value={overview.sales.won_count} hint={`${formatMoney(overview.sales.won_value)} raw amount`} />
              <Metric label="Lost" value={overview.sales.lost_count} />
              <Metric label="Open deals" value={overview.sales.open_count} />
              <Metric label="Weighted" value={formatMoney(overview.sales.weighted_value)} />
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Customers" description={`${customers.total.toLocaleString()} live records by type, source, and status.`} />
            <PanelBody className="grid gap-6 md:grid-cols-3">
              <Breakdown title="Type" rows={customers.by_type} />
              <Breakdown title="Source" rows={customers.by_source} />
              <Breakdown title="Status" rows={customers.by_status} />
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Tickets & SLA" description={`${tickets.total.toLocaleString()} tickets.`} />
            <PanelBody>
              <div className="mb-5 grid grid-cols-3 gap-3">
                <Metric label="First response breached" value={tickets.first_response_breached} />
                <Metric label="Resolution breached" value={tickets.resolution_breached} />
                <Metric label="Open overdue" value={tickets.open_overdue} />
              </div>
              <div className="grid gap-6 md:grid-cols-3">
                <Breakdown title="Type" rows={tickets.by_type} />
                <Breakdown title="Status" rows={tickets.by_status} />
                <Breakdown title="Priority" rows={tickets.by_priority} />
              </div>
            </PanelBody>
          </Panel>

          <Panel className="xl:col-span-2">
            <PanelHeader title="Supplier summary" description={`${suppliers.total.toLocaleString()} suppliers · average rating ${suppliers.average_rating?.toFixed(1) ?? "—"} / 5.`} />
            <PanelBody className="grid gap-6 md:grid-cols-2">
              <Breakdown title="Type" rows={suppliers.by_type} />
              <Breakdown title="Status" rows={suppliers.by_status} />
            </PanelBody>
          </Panel>

          {can("suppliers:view") && <Panel className="xl:col-span-2">
            <PanelHeader title="Supplier list" description={supplierRows ? `${supplierRows.total.toLocaleString()} suppliers` : "Directory records"} />
            <PanelBody className="p-0">
              <div className="flex justify-end border-b border-line px-4 py-3">
                <Button size="sm" variant="secondary" disabled={!supplierRows?.items.length} onClick={exportSupplierRows}>
                  <Icon name="download" className="size-4" /> Export page CSV
                </Button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-line bg-canvas text-xs uppercase text-muted"><tr>
                    <th className="px-4 py-3 font-medium">Supplier</th><th className="px-4 py-3 font-medium">Type</th><th className="px-4 py-3 font-medium">Status</th><th className="px-4 py-3 font-medium">Lead time</th><th className="px-4 py-3 font-medium">Rating</th>
                  </tr></thead>
                  <tbody className="divide-y divide-line">
                    {supplierRows?.items.map((supplier) => <tr key={supplier.id}>
                      <td className="px-4 py-3 font-medium">{supplier.name}</td><td className="px-4 py-3 text-muted">{supplier.supplier_type}</td><td className="px-4 py-3 text-muted">{supplier.status}</td><td className="px-4 py-3 text-muted">{supplier.lead_time_days == null ? "—" : `${supplier.lead_time_days} days`}</td><td className="px-4 py-3 text-muted">{supplier.rating == null ? "—" : `${supplier.rating} / 5`}</td>
                    </tr>)}
                    {supplierRows?.items.length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-muted">No suppliers found.</td></tr>}
                  </tbody>
                </table>
              </div>
              {supplierRows && <Pagination page={supplierRows.page} pageSize={supplierRows.page_size} total={supplierRows.total} onPage={setSupplierPage} />}
            </PanelBody>
          </Panel>}
        </div>
      </>)}
    </>
  );
}