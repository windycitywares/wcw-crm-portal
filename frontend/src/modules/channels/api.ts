import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export interface ChannelInfo {
  key: string;
  label: string;
  available: boolean;
  connected: boolean;
}

export interface EtsyConnection {
  client_id: string | null;
  secret_set: boolean;
  connected: boolean;
  shop_name: string | null;
  external_shop_id: number | null;
  connected_at: string | null;
  listings_synced_at: string | null;
  orders_synced_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
  redirect_uri: string;
  scopes: string | null;
}

export interface HandoverCheck {
  shop: Record<string, number>;
  crm: Record<string, number>;
  matches: boolean;
}
export interface HandoverResult {
  listings: number;
  orders: number;
  orders_not_in_crm: number;
  events: number;
  suppliers_not_found: string[];
  check: HandoverCheck;
}

let cache: Promise<ChannelInfo[]> | null = null;

export const channelsApi = {
  list: () => apiFetch<{ items: ChannelInfo[] }>("/channels").then((r) => r.items),
  /** For the sidebar: fetched once per page load. */
  cached: () => (cache ??= channelsApi.list().catch(() => { cache = null; return []; })),
  forget: () => { cache = null; },
  etsy: {
    connection: () => apiFetch<EtsyConnection>("/channels/etsy/connection"),
    saveCredentials: (client_id: string | null, client_secret: string | null) =>
      apiFetch<EtsyConnection>("/channels/etsy/credentials", { method: "PUT", body: JSON.stringify({ client_id, client_secret }) }),
    connect: () => apiFetch<{ url: string }>("/channels/etsy/connect", { method: "POST" }),
    disconnect: () => apiFetch<EtsyConnection>("/channels/etsy/disconnect", { method: "POST" }),
    importFromShop: () => apiFetch<HandoverResult>("/channels/etsy/import-from-shop", { method: "POST" }),
    importCheck: () => apiFetch<HandoverCheck>("/channels/etsy/import-from-shop/check"),
  },
};

export interface Variation {
  sku: string | null;
  options: Record<string, string>;
  price: string | null;
  quantity: number | null;
}

export interface Listing {
  id: number;
  channel: string;
  external_id: number;
  title: string;
  state: string;
  price: string | null;
  currency: string;
  quantity: number | null;
  skus: string[];
  url: string | null;
  image: string | null;
  variations: Variation[];
  tags: string[];
  description: string | null;
  synced_at: string | null;
  supplier_account_id: number | null;
  supplier_name: string | null;
  purchase_cost: string | null;
  notes: string | null;
}

export interface ListingFilters {
  q?: string;
  state?: string;
  supplier?: string;
  page?: number;
  page_size?: number;
}

export const listingsApi = {
  list: (f: ListingFilters) => apiFetch<Page<Listing>>(`/channels/etsy/listings${qs(f as Record<string, string | number | undefined>)}`),
  update: (id: number, data: { supplier_account_id?: number | null; purchase_cost?: string | null; notes?: string | null }) =>
    apiFetch<Listing>(`/channels/etsy/listings/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  sync: () => apiFetch<{ listings: Record<string, unknown> }>("/channels/etsy/sync", { method: "POST" }),
};

export const LISTING_STATES: Record<string, string> = {
  active: "Active", inactive: "Inactive", sold_out: "Sold out", draft: "Draft", expired: "Expired", removed: "Removed from Etsy",
};
