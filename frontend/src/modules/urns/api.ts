import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export interface UrnSize {
  id: number;
  code: string;
  label: string;
  position: number;
  aliases: string[];
  active: boolean;
}

export type VariationState = "proposed" | "unclear" | "approved";

export interface UrnVariation {
  id: number;
  urn_id: number;
  label: string;
  quantities: Record<string, number>;
  state: VariationState;
  note: string | null;
  sku: string | null;
  etsy_sku: string | null;
  removed: boolean;
  approved_at: string | null;
}

export interface ReviewRow extends UrnVariation {
  urn_name: string;
  supplier_id: number | null;
  supplier_name: string | null;
}

export interface CostExtra {
  id: number;
  urn_id: number | null;
  name: string;
  mode: "amount" | "percent";
  value: string;
  applies: "piece" | "order";
  size_code: string | null;
  party: "supplier" | "ours";
  effective_from: string;
  effective_to: string | null;
  active: boolean;
}

export type ExtraInput = Omit<CostExtra, "id" | "active" | "effective_from" | "effective_to"> & {
  effective_from?: string | null;
  effective_to?: string | null;
};

export interface Urn {
  id: number;
  name: string;
  supplier_id: number | null;
  supplier_name: string | null;
  listing_id: number | null;
  listing_title: string | null;
  listing_url: string | null;
  listing_state: string | null;
  image: string | null;
  notes: string | null;
  /** Today's supplier price per piece, by size code. */
  prices: Record<string, string | null>;
  variations_total: number;
  variations_open: number;
  variations_unclear: number;
  skus_differ: number;
  updated_at: string;
}

export interface UrnDetail extends Urn {
  variations: UrnVariation[];
  price_history: { id: number; size_code: string; amount: string; effective_from: string }[];
  extras: CostExtra[];
}

export interface UrnSummary {
  listings_without_urn: number;
  urns: number;
  ready: number;
  no_supplier: number;
  to_review: number;
  unclear: number;
  no_prices: number;
  sku_differs: number;
}

export interface SkuFormat {
  template: string;
  size_format: string;
  separator: string;
  etsy_push_enabled: boolean;
  problems: string[];
  examples: string[];
}

export interface SkuRow {
  urn_id: number;
  urn_name: string;
  variation_id: number;
  label: string;
  etsy_sku: string | null;
  crm_sku: string | null;
  state: VariationState;
  status: "same" | "new" | "different" | "not_ready";
  shared: boolean;
}

export type Needs = "" | "supplier" | "review" | "prices" | "ready";

const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const urnsApi = {
  summary: () => apiFetch<UrnSummary>("/urns/summary"),
  list: (f: { q?: string; supplier_id?: number | ""; needs?: Needs; page?: number; page_size?: number }) =>
    apiFetch<Page<Urn>>(`/urns${qs({ q: f.q || undefined, supplier_id: f.supplier_id || undefined, needs: f.needs || undefined, page: f.page, page_size: f.page_size })}`),
  get: (id: number) => apiFetch<UrnDetail>(`/urns/${id}`),
  update: (id: number, data: { name?: string; supplier_id?: number | null; notes?: string | null }) =>
    apiFetch<UrnDetail>(`/urns/${id}`, json("PATCH", data)),
  remove: (id: number) => apiFetch<void>(`/urns/${id}`, { method: "DELETE" }),
  refresh: (id: number) => apiFetch<UrnDetail>(`/urns/${id}/refresh`, { method: "POST" }),
  setup: () => apiFetch<{ created: number; variations_added: number }>("/urns/setup", { method: "POST" }),
  assignSupplier: (urnIds: number[], supplierId: number | null) =>
    apiFetch<{ updated: number }>("/urns/assign-supplier", json("POST", { urn_ids: urnIds, supplier_id: supplierId })),
  review: (state: string, page = 1) => apiFetch<Page<ReviewRow>>(`/urns/review${qs({ state, page, page_size: 100 })}`),
  approve: (data: { urn_ids?: number[]; variation_ids?: number[] }) =>
    apiFetch<{ approved: number }>("/urns/approve", json("POST", data)),
  setVariation: (urnId: number, variationId: number, quantities: Record<string, number>) =>
    apiFetch<UrnVariation>(`/urns/${urnId}/variations/${variationId}`, json("PUT", { quantities })),
  setPrice: (urnId: number, data: { size_code: string; amount: string; effective_from?: string | null }) =>
    apiFetch<void>(`/urns/${urnId}/prices`, json("POST", data)),
  removePrice: (urnId: number, priceId: number) => apiFetch<void>(`/urns/${urnId}/prices/${priceId}`, { method: "DELETE" }),
  sizes: () => apiFetch<UrnSize[]>("/urns/sizes"),
  addSize: (data: Partial<UrnSize>) => apiFetch<UrnSize>("/urns/sizes", json("POST", data)),
  editSize: (id: number, data: Partial<UrnSize>) => apiFetch<UrnSize>(`/urns/sizes/${id}`, json("PATCH", data)),
  format: () => apiFetch<SkuFormat>("/urns/sku-format"),
  checkFormat: (data: Partial<SkuFormat>) => apiFetch<SkuFormat>("/urns/sku-format/check", json("POST", data)),
  saveFormat: (data: Partial<SkuFormat>) => apiFetch<{ changed: number }>("/urns/sku-format", json("PUT", data)),
  skuPreview: (onlyDifferent: boolean) =>
    apiFetch<{ items: SkuRow[]; etsy_push_enabled: boolean }>(`/urns/sku-preview${qs({ only_different: onlyDifferent || undefined })}`),
  sharedExtras: () => apiFetch<CostExtra[]>("/urns/extras"),
  addExtra: (data: ExtraInput) => apiFetch<CostExtra>("/urns/extras", json("POST", data)),
  editExtra: (id: number, data: Partial<ExtraInput>) => apiFetch<CostExtra>(`/urns/extras/${id}`, json("PATCH", data)),
  endExtra: (id: number) => apiFetch<void>(`/urns/extras/${id}/end`, json("POST", {})),
};

export interface CostLine {
  label: string;
  amount: string;
  party: "supplier" | "ours";
  kind: "price" | "extra" | "adjustment";
}

export interface Adjustment {
  id: number;
  label: string;
  amount: string;
  party: "supplier" | "ours";
  note: string;
  created_at: string;
}

export interface OrderCosts {
  source: "sku" | "listing" | "manual" | null;
  saved: { lines: CostLine[]; on: string | null; supplier: string; ours: string } | null;
  purchase_cost: string | null;
  other_costs: string | null;
  live: { lines: CostLine[]; missing: string[]; on: string | null; supplier: string; ours: string; complete: boolean };
  differs: boolean;
  locked: boolean;
  adjustments: Adjustment[];
}

export interface RecalcRow {
  order_id: number;
  external_id: number;
  ordered_at: string;
  source: string | null;
  purchase_cost: string | null;
  other_costs: string | null;
  new_purchase_cost: string;
  new_other_costs: string;
}

export const orderCostsApi = {
  get: (orderId: number) => apiFetch<OrderCosts>(`/channels/etsy/orders/${orderId}/costs`),
  recalculate: (orderId: number) => apiFetch<OrderCosts>(`/channels/etsy/orders/${orderId}/costs/recalculate`, { method: "POST" }),
  addAdjustment: (orderId: number, data: { label: string; amount: string; party: "supplier" | "ours"; note: string }) =>
    apiFetch<OrderCosts>(`/channels/etsy/orders/${orderId}/adjustments`, json("POST", data)),
  removeAdjustment: (orderId: number, id: number) =>
    apiFetch<OrderCosts>(`/channels/etsy/orders/${orderId}/adjustments/${id}`, { method: "DELETE" }),
  preview: () => apiFetch<{ items: RecalcRow[] }>("/channels/etsy/costs/recalculate"),
  apply: (orderIds: number[]) => apiFetch<{ updated: number }>("/channels/etsy/costs/recalculate", json("POST", { order_ids: orderIds })),
};

/** "10″ × 1 + 3″ × 4" from {"10": 1, "3": 4}, in the sizes list's order. */
export function quantitiesText(q: Record<string, number>, sizes: UrnSize[]): string {
  const parts = sizes.filter((s) => (q[s.code] ?? 0) > 0).map((s) => `${s.label} × ${q[s.code]}`);
  const unknown = Object.keys(q).filter((c) => !sizes.some((s) => s.code === c) && q[c] > 0).map((c) => `${c} × ${q[c]}`);
  return [...parts, ...unknown].join(" + ") || "—";
}

export const STATE_LABEL: Record<VariationState, string> = { proposed: "To check", unclear: "Needs you", approved: "Approved" };
export const STATE_BADGE: Record<VariationState, "warning" | "danger" | "success"> = { proposed: "warning", unclear: "danger", approved: "success" };
