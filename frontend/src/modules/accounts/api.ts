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
  /** The parent organisation (a group above its companies, a head office above its branches). */
  parent_id: number | null;
  parent_name: string | null;
  children_count: number;
  custom_fields: Record<string, unknown>;
  contacts_count: number;
  created_by: number | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface AccountTreeNode {
  id: number;
  name: string;
  account_type: string;
  status: AccountStatus;
  /** 0 = the account the group was asked for; 1 = its sub-accounts; … */
  depth: number;
  parent_id: number | null;
  contacts_count: number;
  open_deals: number;
  open_value: number;
}

/** An account's place in its group and the totals of everything under it. */
export interface AccountGroup {
  ancestors: AccountOption[];
  tree: AccountTreeNode[];
  accounts: number;
  people: number;
  open_deals: number;
  open_value: number;
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
  parent_id?: number | null;
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

/** A person at an organisation: their role there and when it held. `is_primary` = it's their main account. */
export interface AccountLink {
  id: number;
  account_id: number;
  account_name: string | null;
  account_type: string | null;
  contact_id: number;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  title: string | null;
  role: string | null;
  is_primary: boolean;
  started_on: string | null;
  ended_on: string | null;
  active: boolean;
}

export interface AccountLinkInput {
  role?: string | null;
  is_primary?: boolean;
  started_on?: string | null;
  ended_on?: string | null;
}

const flat = (f: object) => f as Record<string, string | number | boolean | null | undefined>;

export const accountsApi = {
  list: (f: AccountFilters = {}) => apiFetch<Page<Account>>(`/accounts${qs(flat(f))}`),
  options: (q = "", type = "") => apiFetch<AccountOption[]>(`/accounts/options${qs({ q: q || undefined, type: type || undefined })}`),
  get: (id: number) => apiFetch<Account>(`/accounts/${id}`),
  contacts: (id: number, page = 1) => apiFetch<Page<Contact>>(`/accounts/${id}/contacts${qs({ page, page_size: 50 })}`),
  group: (id: number) => apiFetch<AccountGroup>(`/accounts/${id}/group`),
  people: (id: number, includeEnded = false) =>
    apiFetch<AccountLink[]>(`/accounts/${id}/people${qs({ include_ended: includeEnded || undefined })}`),
  link: (id: number, data: { contact_id: number; role?: string | null; is_primary?: boolean }) =>
    apiFetch<AccountLink>(`/accounts/${id}/people`, { method: "POST", body: JSON.stringify(data) }),
  linksFor: (contactId: number) => apiFetch<AccountLink[]>(`/accounts/links${qs({ contact_id: contactId })}`),
  updateLink: (linkId: number, data: AccountLinkInput) =>
    apiFetch<AccountLink>(`/accounts/links/${linkId}`, { method: "PATCH", body: JSON.stringify(data) }),
  endLink: (linkId: number) => apiFetch<void>(`/accounts/links/${linkId}`, { method: "DELETE" }),
  create: (data: AccountInput) => apiFetch<Account>("/accounts", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: AccountInput) => apiFetch<Account>(`/accounts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  archive: (id: number) => apiFetch<void>(`/accounts/${id}`, { method: "DELETE" }),
};
