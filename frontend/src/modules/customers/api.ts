"use client";

import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export type CustomerStatus = "active" | "inactive" | "blocked";

export interface Address {
  line1?: string | null;
  line2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
}

export interface Customer {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  display_name: string;
  company: string | null;
  email: string | null;
  alt_emails: string[];
  phone: string | null;
  address: Address | null;
  customer_type: string | null;
  source: string | null;
  status: CustomerStatus;
  owner_id: number | null;
  marketing_consent: boolean;
  consent_at: string | null;
  consent_source: string | null;
  unsubscribed_at: string | null;
  shop_user_id: number | null;
  orders_count: number;
  total_spent: string;
  first_order_at: string | null;
  last_order_at: string | null;
  custom_fields: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  deleted_at: string | null;
  tags: { id: number; name: string; color: string | null }[];
}

export interface CustomerInput {
  first_name?: string | null;
  last_name?: string | null;
  company?: string | null;
  email?: string | null;
  alt_emails?: string[];
  phone?: string | null;
  address?: Address | null;
  customer_type?: string | null;
  source?: string | null;
  status?: CustomerStatus;
  owner_id?: number | null;
  marketing_consent?: boolean;
  custom_fields?: Record<string, unknown>;
}

export interface CustomerFilters {
  q?: string;
  type?: string;
  status?: string;
  owner?: "me" | "any";
  tag_id?: number | "";
  has_orders?: "true" | "false" | "";
  deleted?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
}

export const SORTS: { value: string; label: string }[] = [
  { value: "-updated", label: "Recently updated" },
  { value: "-created", label: "Newest" },
  { value: "name", label: "Name A–Z" },
  { value: "-last_order", label: "Last order" },
  { value: "-total_spent", label: "Total spent" },
];

export const STATUS_LABEL: Record<CustomerStatus, string> = { active: "Active", inactive: "Inactive", blocked: "Blocked" };

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const customersApi = {
  list: (f: CustomerFilters) => apiFetch<Page<Customer>>(`/customers${qs({ ...f })}`),
  get: (id: number, deleted = false) => apiFetch<Customer>(`/customers/${id}${deleted ? "?deleted=true" : ""}`),
  create: (data: CustomerInput) => apiFetch<Customer>("/customers", json("POST", data)),
  update: (id: number, data: CustomerInput) => apiFetch<Customer>(`/customers/${id}`, json("PATCH", data)),
  remove: (id: number) => apiFetch<void>(`/customers/${id}`, { method: "DELETE" }),
  restore: (id: number) => apiFetch<Customer>(`/customers/${id}/restore`, { method: "POST" }),
  checkEmail: (email: string, excludeId?: number) =>
    apiFetch<{ exists: boolean; customer_id: number | null; display_name: string | null }>(`/customers/check-email${qs({ email, exclude_id: excludeId })}`),
};

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
export const formatMoney = (value: string | number) => money.format(Number(value));
