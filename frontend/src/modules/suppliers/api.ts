import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export type SupplierStatus = "active" | "inactive";

export interface SupplierAddress {
  line1?: string | null;
  line2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
}

export interface SupplierContact {
  id: number;
  supplier_id: number;
  name: string;
  title: string | null;
  email: string | null;
  phone: string | null;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
}

export interface SupplierProduct {
  id: number;
  supplier_id: number;
  shop_sku: string;
  supplier_sku: string | null;
  description: string | null;
  unit_cost: string;
  currency: string;
  minimum_order_quantity: string | null;
  lead_time_days: number | null;
  notes: string | null;
  created_by: number | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface Supplier {
  id: number;
  name: string;
  supplier_type: string;
  status: SupplierStatus;
  address: SupplierAddress | null;
  website: string | null;
  payment_terms: string | null;
  lead_time_days: number | null;
  currency: string;
  rating: number | null;
  custom_fields: Record<string, unknown>;
  contacts: SupplierContact[];
  created_by: number | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface SupplierInput {
  name: string;
  supplier_type: string;
  status?: SupplierStatus;
  address?: SupplierAddress | null;
  website?: string | null;
  payment_terms?: string | null;
  lead_time_days?: number | null;
  currency?: string;
  rating?: number | null;
  custom_fields?: Record<string, unknown> | null;
  contacts?: Array<Pick<SupplierContact, "name" | "title" | "email" | "phone" | "is_primary">>;
}

export interface SupplierProductInput {
  shop_sku: string;
  supplier_sku?: string | null;
  description?: string | null;
  unit_cost: string | number;
  currency?: string;
  minimum_order_quantity?: string | number | null;
  lead_time_days?: number | null;
  notes?: string | null;
}

export const suppliersApi = {
  list: (page = 1, pageSize = 25, q?: string, supplierType?: string, status?: SupplierStatus) =>
    apiFetch<Page<Supplier>>(`/suppliers${qs({ page, page_size: pageSize, q, supplier_type: supplierType, status })}`),
  get: (id: number) => apiFetch<Supplier>(`/suppliers/${id}`),
  create: (data: SupplierInput) => apiFetch<Supplier>("/suppliers", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Partial<SupplierInput>) =>
    apiFetch<Supplier>(`/suppliers/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  remove: (id: number) => apiFetch<void>(`/suppliers/${id}`, { method: "DELETE" }),
  contacts: {
    add: (id: number, data: Omit<SupplierContact, "id" | "supplier_id" | "created_at" | "updated_at">) =>
      apiFetch<SupplierContact>(`/suppliers/${id}/contacts`, { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, contactId: number, data: Partial<SupplierContact>) =>
      apiFetch<SupplierContact>(`/suppliers/${id}/contacts/${contactId}`, { method: "PATCH", body: JSON.stringify(data) }),
    remove: (id: number, contactId: number) =>
      apiFetch<void>(`/suppliers/${id}/contacts/${contactId}`, { method: "DELETE" }),
  },
  products: {
    list: (id: number, page = 1, pageSize = 25, q?: string) =>
      apiFetch<Page<SupplierProduct>>(`/suppliers/${id}/products${qs({ page, page_size: pageSize, q })}`),
    add: (id: number, data: SupplierProductInput) =>
      apiFetch<SupplierProduct>(`/suppliers/${id}/products`, { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, productId: number, data: Partial<SupplierProductInput>) =>
      apiFetch<SupplierProduct>(`/suppliers/${id}/products/${productId}`, { method: "PATCH", body: JSON.stringify(data) }),
    remove: (id: number, productId: number) =>
      apiFetch<void>(`/suppliers/${id}/products/${productId}`, { method: "DELETE" }),
  },
};