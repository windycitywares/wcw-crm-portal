import { apiFetch, qs } from "@/lib/client-api";
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
