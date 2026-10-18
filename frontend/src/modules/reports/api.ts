import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export interface ReportBucket {
  label: string;
  count: number;
}

export interface ReportsOverview {
  sales: {
    open_count: number;
    open_value: string | number;
    weighted_value: string | number;
    won_count: number;
    won_value: string | number;
    lost_count: number;
  };
  tickets: { open: number; unassigned: number; overdue: number; mine: number };
  campaigns: {
    days: number;
    campaigns: number;
    sent: number;
    opened: number;
    clicked: number;
    unsubscribed: number;
    failed: number;
    skipped: number;
    open_rate: number | null;
    click_rate: number | null;
  };
  active_customers: number;
  active_suppliers: number;
}

export interface CustomerReport {
  total: number;
  by_type: ReportBucket[];
  by_source: ReportBucket[];
  by_status: ReportBucket[];
}

export interface TicketReport {
  total: number;
  by_type: ReportBucket[];
  by_status: ReportBucket[];
  by_priority: ReportBucket[];
  first_response_breached: number;
  resolution_breached: number;
  open_overdue: number;
}

export interface SupplierReport {
  total: number;
  by_type: ReportBucket[];
  by_status: ReportBucket[];
  average_rating: number | null;
}

export interface SupplierListRow {
  id: number;
  name: string;
  supplier_type: string;
  status: "active" | "inactive";
  lead_time_days: number | null;
  currency: string;
  rating: number | null;
  contacts: { name: string; email: string | null; is_primary: boolean }[];
}

export const reportsApi = {
  overview: (campaignDays = 30) => apiFetch<ReportsOverview>(`/reports/overview${qs({ campaign_days: campaignDays })}`),
  customers: () => apiFetch<CustomerReport>("/reports/customers"),
  tickets: () => apiFetch<TicketReport>("/reports/tickets"),
  suppliers: () => apiFetch<SupplierReport>("/reports/suppliers"),
  supplierList: (page = 1, pageSize = 25) =>
    apiFetch<Page<SupplierListRow>>(`/suppliers${qs({ page, page_size: pageSize })}`),
};