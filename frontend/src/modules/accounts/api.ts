import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";
import type { Address, Contact } from "@/modules/contacts/api";

export type AccountStatus = "active" | "inactive";

/** An organisation: a customer's company, a supplier, a partner, a marketplace. */
export interface Account {
  id: number;
  name: string;
  account_type: string;
  status: AccountStatus;
  industry: string | null;
  website: string | null;
  email: string | null;
  phone: string | null;
  address: Address | null;
  notes: string | null;
  owner_id: number | null;
  primary_contact_id: number | null;
  custom_fields: Record<string, unknown>;
  contacts_count: number;
  created_by: number | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface AccountInput {
  name?: string;
  account_type?: string;
  status?: AccountStatus;
  industry?: string | null;
  website?: string | null;
  email?: string | null;
  phone?: string | null;
  address?: Address | null;
  notes?: string | null;
  owner_id?: number | null;
}

export interface AccountOption {
  id: number;
  name: string;
  account_type: string;
}

export interface AccountFilters {
  q?: string;
  type?: string;
  status?: "" | AccountStatus;
  owner?: "me" | "any";
  sort?: "name" | "-updated" | "-created";
  page?: number;
  page_size?: number;
}

const flat = (f: object) => f as Record<string, string | number | boolean | null | undefined>;

export const accountsApi = {
  list: (f: AccountFilters = {}) => apiFetch<Page<Account>>(`/accounts${qs(flat(f))}`),
  options: (q = "", type = "") => apiFetch<AccountOption[]>(`/accounts/options${qs({ q: q || undefined, type: type || undefined })}`),
  get: (id: number) => apiFetch<Account>(`/accounts/${id}`),
  contacts: (id: number, page = 1) => apiFetch<Page<Contact>>(`/accounts/${id}/contacts${qs({ page, page_size: 50 })}`),
  create: (data: AccountInput) => apiFetch<Account>("/accounts", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: AccountInput) => apiFetch<Account>(`/accounts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  archive: (id: number) => apiFetch<void>(`/accounts/${id}`, { method: "DELETE" }),
};
