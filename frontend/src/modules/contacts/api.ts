import { apiDownload, apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export type ContactStatus = "active" | "inactive" | "blocked";

export interface Address {
  line1?: string | null;
  line2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
}

export interface Contact {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  display_name: string;
  company: string | null;
  title: string | null;
  email: string | null;
  alt_emails: string[];
  phone: string | null;
  address: Address | null;
  types: string[];
  notes: string | null;
  status: ContactStatus;
  source: string;
  owner_id: number | null;
  user_id: number | null;
  customer_id: number | null;
  subscribed_at: string | null;
  unsubscribed_at: string | null;
  subscribe_source: string | null;
  paused_at: string | null;
  language: string | null;
  subscription_status: "subscribed" | "paused" | "unsubscribed" | null;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  deleted_at: string | null;
}

export interface ContactInput {
  first_name?: string | null;
  last_name?: string | null;
  company?: string | null;
  title?: string | null;
  email?: string | null;
  alt_emails?: string[];
  phone?: string | null;
  address?: Address | null;
  types?: string[];
  notes?: string | null;
  status?: ContactStatus;
  owner_id?: number | null;
}

export interface ContactFilters {
  q?: string;
  type?: string;
  status?: string;
  owner?: "me" | "any";
  subscription?: "" | "subscribed" | "unsubscribed";
  sort?: string;
  page?: number;
  page_size?: number;
}

export const contactsApi = {
  list: (f: ContactFilters = {}) => apiFetch<Page<Contact>>(`/contacts${qs(f as Record<string, string | number | boolean | null | undefined>)}`),
  get: (id: number) => apiFetch<Contact>(`/contacts/${id}`),
  create: (data: ContactInput) => apiFetch<Contact>("/contacts", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: ContactInput) => apiFetch<Contact>(`/contacts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) => apiFetch<void>(`/contacts/${id}`, { method: "DELETE" }),
};

export type SubscriberStatus = "subscribed" | "paused" | "unsubscribed";
export interface SubscriberFilters {
  q?: string;
  status?: "" | SubscriberStatus;
  source?: string;
  sort?: "-joined" | "joined" | "email";
  page?: number;
  page_size?: number;
}
export interface SubscriberPage extends Page<Contact> {
  counts: { subscribed: number; paused: number; unsubscribed: number; all: number };
  sources: string[];
}
export interface SubscriberInput {
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  language?: string | null;
}

/** Where a subscriber signed up, in words. Unknown sources show as written. */
export const SOURCE_LABEL: Record<string, string> = {
  site: "Website", checkout: "Checkout", account: "Account", manual: "Added by hand", import: "Import",
};

const flat = (f: SubscriberFilters) => f as Record<string, string | number | boolean | null | undefined>;

export const subscribersApi = {
  list: (f: SubscriberFilters = {}) => apiFetch<SubscriberPage>(`/contacts/subscribers${qs(flat(f))}`),
  add: (data: SubscriberInput) => apiFetch<Contact>("/contacts/subscribers", { method: "POST", body: JSON.stringify(data) }),
  act: (id: number, action: "pause" | "resume" | "unsubscribe" | "resubscribe") =>
    apiFetch<Contact>(`/contacts/subscribers/${id}/${action}`, { method: "POST" }),
  remove: (id: number) => apiFetch<void>(`/contacts/subscribers/${id}`, { method: "DELETE" }),
  export: (f: SubscriberFilters) => apiDownload(`/contacts/subscribers/export.csv${qs(flat({ q: f.q, status: f.status, source: f.source }))}`, "subscribers.csv"),
};
