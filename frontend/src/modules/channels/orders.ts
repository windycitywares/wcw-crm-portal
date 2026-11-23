/** Shapes and words shared by the Etsy order screens (backend: app/modules/channels/orders.py). */
import { apiFetch, qs } from "@/lib/client-api";
import type { Tone } from "@/components/ui/Pill";

export interface Profit {
  revenue: string;
  total_cost: string;
  net_profit: string;
  margin_pct: string | null;
  missing: string[];
  days_to_ship: number | null;
}
export interface OrderSummary {
  id: number;
  external_id: number;
  status: string;
  ordered_at: string;
  paid_at: string | null;
  ship_by: string | null;
  buyer_name: string | null;
  supplier_account_id: number | null;
  supplier_name: string | null;
  currency: string;
  tracking_number: string | null;
  items: { title: string; quantity: number; image?: string | null }[];
  profit: Profit;
  attention: string[];
  /** Already shipped when it first came in from Etsy: kept for history, never flagged. */
  past_order: boolean;
}
export interface HistoryLine {
  id: number;
  kind: string;
  from_status: string | null;
  to_status: string | null;
  message: string;
  source: "team" | "etsy" | "supplier";
  actor_name: string | null;
  created_at: string;
}
export interface OrderDetail extends OrderSummary {
  external_state: string | null;
  external_buyer_id: number | null;
  buyer_email: string | null;
  buyer_phone: string | null;
  ship_address: Record<string, string>;
  gift_message: string | null;
  buyer_note: string | null;
  items_total: string;
  shipping_charged: string;
  discounts: string;
  tax: string;
  grand_total: string;
  marketplace_fees: string | null;
  purchase_cost: string | null;
  costs_prefilled: boolean;
  other_costs: string | null;
  cost_source: "sku" | "listing" | "manual" | null;
  supplier_order_number: string | null;
  shipping_cost: string | null;
  carrier: string | null;
  tracking_sent_at: string | null;
  tracking_error: string | null;
  purchased_at: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  notes: string | null;
  synced_at: string | null;
  external_url: string;
  supplier_owed: string | null;
  supplier_payment: "pending" | "settled" | "cost_missing" | "not_due";
  supplier_paid_at: string | null;
  supplier_paid_amount: string | null;
  supplier_payment_ref: string | null;
  line_items: { id: number; listing_external_id: number | null; title: string; image?: string | null; sku: string | null; variations: { name: string; value: string }[]; quantity: number; unit_price: string }[];
  history: HistoryLine[];
}

export const STATUS_LABEL: Record<string, string> = {
  new: "New (paid)", purchased: "Purchased", shipped: "Shipped", delivered: "Delivered", closed: "Closed",
  cancelled: "Cancelled", issue: "Issue reported", replacement: "Replacement sent", return_requested: "Return requested",
  returned: "Returned", refunded: "Refunded",
};
export const MAIN_PATH = ["new", "purchased", "shipped", "delivered", "closed"];
export const EXCEPTIONS = ["cancelled", "issue", "replacement", "return_requested", "returned", "refunded"];
export const STATUS_TONE: Record<string, Tone> = {
  new: "info", purchased: "accent", shipped: "accent", delivered: "success", closed: "neutral", cancelled: "neutral",
  issue: "danger", replacement: "warning", return_requested: "warning", returned: "warning", refunded: "warning",
};
export const ATTENTION_LABEL: Record<string, string> = {
  not_purchased: "Not purchased after 24 h",
  late: "Past ship-by date",
  cost_missing: "Cost missing",
  shipping_cost_missing: "Shipping cost missing",
  negative_profit: "Losing money",
};
export const MISSING_LABEL: Record<string, string> = {
  purchase_cost: "purchase cost", shipping_cost: "shipping cost", marketplace_fees: "Etsy fees (later phase)",
};

export interface OrderPage {
  items: OrderSummary[];
  total: number;
  page: number;
  page_size: number;
  counts: Record<string, number>;
  attention: number;
}

export interface OrderFilters {
  q?: string;
  status?: string;
  attention?: boolean;
  supplier?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

export type OrderPatch = Partial<{
  purchase_cost: string | null; shipping_cost: string | null; supplier_account_id: number | null;
  supplier_order_number: string | null; carrier: string | null; tracking_number: string | null; notes: string | null;
  buyer_phone: string | null;
}>;

export const ordersApi = {
  list: (f: OrderFilters) => apiFetch<OrderPage>(`/channels/etsy/orders${qs(f as Record<string, string | number | boolean | undefined>)}`),
  get: (id: number) => apiFetch<OrderDetail>(`/channels/etsy/orders/${id}`),
  update: (id: number, data: OrderPatch) => apiFetch<OrderDetail>(`/channels/etsy/orders/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  setStatus: (id: number, status: string, note?: string) =>
    apiFetch<OrderDetail>(`/channels/etsy/orders/${id}/status`, { method: "POST", body: JSON.stringify({ status, note: note || null }) }),
};
