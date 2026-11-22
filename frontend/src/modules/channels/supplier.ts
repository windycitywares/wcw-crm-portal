/** Shapes for the supplier's own screens (backend: app/modules/supplier_portal). */
export interface SupplierItem {
  title: string;
  quantity: number;
  sku: string | null;
  variations: { name: string; value: string }[];
  image?: string | null;
}
export interface SupplierOrder {
  id: number;
  external_id: number;
  ordered_at: string;
  ship_by: string | null;
  late: boolean;
  status: string;
  status_label: string;
  buyer_name: string | null;
  supplier_order_number: string | null;
  carrier: string | null;
  tracking_number: string | null;
  items: SupplierItem[];
  owed: string | null;
  payment: "pending" | "settled" | "cost_missing" | "not_due";
  paid_at: string | null;
  paid_amount: string | null;
}
export interface SupplierOrderDetail extends SupplierOrder {
  ship_address: Record<string, string>;
  gift_message: string | null;
  buyer_note: string | null;
  shipped_at: string | null;
  payment_ref: string | null;
  history: { id: number; message: string; source: string; actor_name: string | null; created_at: string }[];
}
export const PAYMENT_LABEL = { pending: "Not paid yet", settled: "Paid", cost_missing: "Price not agreed yet", not_due: "Not due" } as const;
export const PAYMENT_TONE = { pending: "warning", settled: "success", cost_missing: "neutral", not_due: "neutral" } as const;
