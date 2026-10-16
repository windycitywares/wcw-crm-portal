"use client";

import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export interface ShopSettings {
  enabled: boolean;
  webhook_secret_set: boolean;
  shop_api_url: string;
  shop_api_token_set: boolean;
}

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

export const shopApi = {
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
