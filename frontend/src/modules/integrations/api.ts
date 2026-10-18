"use client";

import { API_URL, apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export interface ShopSettings {
  enabled: boolean;
  webhook_secret_set: boolean;
  shop_api_url: string;
  shop_api_token_set: boolean;
}

/** Admin → Settings → Integrations → Inbox channels: the door a chat, an Etsy message or an SMS comes in. */
export interface InboxSettings {
  enabled: boolean;
  ingest_secret_set: boolean;
}

/** Where a connector posts one message from a channel that isn't a mailbox (docs/INBOX_CHANNELS.md). */
export const INTAKE_URL = `${API_URL}/inbox/messages`;

export interface ShopStatus {
  enabled: boolean;
  secret_set: boolean;
  webhook_url: string;
  last_event_at: string | null;
  counts: Record<string, number>;
}

export type ShopEventStatus = "pending" | "done" | "failed" | "ignored";

export interface ShopEvent {
  id: number;
  event_id: string;
  event_type: string;
  status: ShopEventStatus;
  attempts: number;
  error: string | null;
  customer_id: number | null;
  occurred_at: string | null;
  received_at: string;
  processed_at: string | null;
}

export interface Backfill {
  status: "idle" | "running" | "done" | "failed";
  phase: "customers" | "orders" | "newsletter";
  counts: Record<string, number>;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface ShopOrder {
  id: number;
  number: string;
  status: string;
  payment_status: string;
  currency: string;
  grand_total: string;
  refunded_total: string;
  placed_at: string | null;
}

export const shopApi = {
  test: () => apiFetch<{ ok: boolean; detail: string }>("/integrations/shop/test"),
  backfill: () => apiFetch<Backfill>("/integrations/shop/backfill"),
  startBackfill: () => apiFetch<Backfill>("/integrations/shop/backfill", { method: "POST" }),
  cancelBackfill: () => apiFetch<Backfill>("/integrations/shop/backfill/cancel", { method: "POST" }),
  customerOrders: (customerId: number) => apiFetch<ShopOrder[]>(`/integrations/shop/customers/${customerId}/orders`),
  status: () => apiFetch<ShopStatus>("/integrations/shop/status"),
  events: (status: ShopEventStatus | "", page: number) => apiFetch<Page<ShopEvent>>(`/integrations/shop/events${qs({ status: status || undefined, page, page_size: 20 })}`),
  retry: (id: number) => apiFetch<ShopEvent>(`/integrations/shop/events/${id}/retry`, { method: "POST" }),
};

/** A random secret for signing webhooks (48 URL-safe characters), made in the browser. */
export function newSecret() {
  const bytes = new Uint8Array(36);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_");
}
