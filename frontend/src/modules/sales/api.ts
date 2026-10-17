"use client";

import type { Tone } from "@/components/ui/Pill";
import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export type DealStatus = "open" | "won" | "lost";
export type DealView = "all" | "mine" | "unassigned";
/** Money may arrive as a JSON number or a string, depending on the field — always pass it through Number(). */
export type Money = string | number;

export interface DealStage {
  id: number;
  pipeline_id: number;
  name: string;
  position: number;
  probability: number;
  is_won: boolean;
  is_lost: boolean;
  color: string | null;
}

export interface Pipeline {
  id: number;
  name: string;
  is_default: boolean;
  stages: DealStage[];
}

export interface Deal {
  id: number;
  title: string;
  description: string | null;
  customer_id: number | null;
  customer_name: string | null;
  pipeline_id: number | null;
  pipeline_name: string | null;
  stage_id: number | null;
  stage_name: string | null;
  status: DealStatus;
  value: Money;
  currency: string;
  probability: number;
  weighted_value: Money;
  expected_close_on: string | null;
  closed_at: string | null;
  owner_id: number | null;
  owner_name: string | null;
  source: string | null;
  lost_reason: string | null;
  position: number;
  custom_fields: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DealInput {
  title?: string;
  description?: string | null;
  customer_id?: number | null;
  stage_id?: number | null;
  status?: DealStatus;
  value?: Money;
  currency?: string;
  probability?: number | null;
  expected_close_on?: string | null;
  owner_id?: number | null;
  source?: string | null;
  lost_reason?: string | null;
  position?: number;
}

export interface DealFilters {
  view?: DealView;
  /** "all" asks for every status (the API's default is open only). */
  status?: DealStatus | "all";
  pipeline_id?: number;
  stage_id?: number;
  owner_id?: number;
  customer_id?: number;
  q?: string;
  page?: number;
  page_size?: number;
}

export interface BoardColumn {
  stage: DealStage;
  deals: Deal[];
  total_value: Money;
  weighted_value: Money;
}

/** One pipeline's stages with their open deals — what the kanban draws. */
export interface Board {
  pipeline_id: number;
  pipeline_name: string;
  stages: BoardColumn[];
}

export interface SalesSummary {
  open_count: number;
  open_value: Money;
  weighted_value: Money;
  won_count: number;
  won_value: Money;
  lost_count: number;
}

export interface PipelineInput {
  name: string;
  is_default?: boolean;
}

/** One line on a deal: a product from the shop catalog, or a one-off typed in. `total` is quantity × unit price. */
export interface DealItem {
  id: number;
  deal_id: number;
  name: string;
  sku: string | null;
  shop_product_id: number | null;
  quantity: Money;
  unit_price: Money;
  total: Money;
  position: number;
  created_at: string;
  updated_at: string;
}

/** A deal's lines and what they add up to — put next to the deal's own value, never instead of it. */
export interface DealItems {
  items: DealItem[];
  count: number;
  total: Money;
}

export interface DealItemInput {
  name?: string;
  sku?: string | null;
  shop_product_id?: number | null;
  quantity?: Money;
  unit_price?: Money;
  position?: number;
}

export interface StageInput {
  name: string;
  probability?: number;
  is_won?: boolean;
  is_lost?: boolean;
  color?: string | null;
}

export const STATUS_LABEL: Record<DealStatus, string> = { open: "Open", won: "Won", lost: "Lost" };
export const STATUS_TONE: Record<DealStatus, Tone> = { open: "info", won: "success", lost: "danger" };
export const STATUSES: DealStatus[] = ["open", "won", "lost"];

/** "12 open deals · $48,300 · $21,400 weighted · 3 won this month" — the line under the page title. */
export function describeSummary(s: SalesSummary): string {
  const parts = [
    `${s.open_count} open ${s.open_count === 1 ? "deal" : "deals"} worth ${money(s.open_value)}`,
    `${money(s.weighted_value)} weighted`,
    `${s.won_count} won this month`,
  ];
  if (s.lost_count) parts.push(`${s.lost_count} lost`);
  return `${parts.join(" · ")}.`;
}

const formatters = new Map<string, Intl.NumberFormat>();

/** Money in a deal's own currency; falls back to a plain number if the code isn't a real one. */
export function money(value: Money, currency = "USD") {
  const code = (currency || "USD").toUpperCase();
  let format = formatters.get(code);
  if (!format) {
    try {
      format = new Intl.NumberFormat("en-US", { style: "currency", currency: code });
    } catch {
      format = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
    }
    formatters.set(code, format);
  }
  return format.format(Number(value) || 0);
}

/** The weighted forecast of one deal: value × probability. */
export function weightedValue(deal: Deal) {
  return (Number(deal.value) * deal.probability) / 100;
}

/** "Won" / "Lost" / the stage's name — what a deal's column says on a card. */
export function dealStageLabel(deal: Deal) {
  return deal.stage_name ?? STATUS_LABEL[deal.status];
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const salesApi = {
  summary: () => apiFetch<SalesSummary>("/sales/summary"),
  board: (pipelineId?: number) => apiFetch<Board>(`/sales/board${qs({ pipeline_id: pipelineId })}`),
  deals: (f: DealFilters) => apiFetch<Page<Deal>>(`/sales/deals${qs({ ...f })}`),
  deal: (id: number) => apiFetch<Deal>(`/sales/deals/${id}`),
  createDeal: (data: DealInput) => apiFetch<Deal>("/sales/deals", json("POST", data)),
  updateDeal: (id: number, data: DealInput) => apiFetch<Deal>(`/sales/deals/${id}`, json("PATCH", data)),
  removeDeal: (id: number) => apiFetch<void>(`/sales/deals/${id}`, { method: "DELETE" }),
  dealItems: (dealId: number) => apiFetch<DealItems>(`/sales/deals/${dealId}/items`),
  addDealItem: (dealId: number, data: DealItemInput) => apiFetch<DealItem>(`/sales/deals/${dealId}/items`, json("POST", data)),
  updateDealItem: (dealId: number, itemId: number, data: DealItemInput) =>
    apiFetch<DealItem>(`/sales/deals/${dealId}/items/${itemId}`, json("PATCH", data)),
  removeDealItem: (dealId: number, itemId: number) =>
    apiFetch<void>(`/sales/deals/${dealId}/items/${itemId}`, { method: "DELETE" }),
  pipelines: () => apiFetch<Pipeline[]>("/sales/pipelines"),
  createPipeline: (data: PipelineInput) => apiFetch<Pipeline>("/sales/pipelines", json("POST", data)),
  updatePipeline: (id: number, data: Partial<PipelineInput>) => apiFetch<Pipeline>(`/sales/pipelines/${id}`, json("PATCH", data)),
  removePipeline: (id: number) => apiFetch<void>(`/sales/pipelines/${id}`, { method: "DELETE" }),
  addStage: (pipelineId: number, data: StageInput) => apiFetch<DealStage>(`/sales/pipelines/${pipelineId}/stages`, json("POST", data)),
  updateStage: (pipelineId: number, stageId: number, data: Partial<StageInput> & { position?: number }) =>
    apiFetch<DealStage>(`/sales/pipelines/${pipelineId}/stages/${stageId}`, json("PATCH", data)),
  removeStage: (pipelineId: number, stageId: number) =>
    apiFetch<void>(`/sales/pipelines/${pipelineId}/stages/${stageId}`, { method: "DELETE" }),
};

/**
 * Only the fields that actually changed. Moving a card sends the stage alone, so the server can set the
 * stage's probability and outcome without the dialog's other fields getting in the way.
 */
export function dealPatch(before: Deal, desired: DealInput): DealInput {
  const patch: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(desired)) {
    const current = (before as unknown as Record<string, unknown>)[key] ?? null;
    if (JSON.stringify(current) !== JSON.stringify(value ?? null)) patch[key] = value ?? null;
  }
  return patch as DealInput;
}
