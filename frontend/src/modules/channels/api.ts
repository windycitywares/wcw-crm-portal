import { apiFetch } from "@/lib/client-api";

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
  },
};
