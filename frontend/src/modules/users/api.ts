"use client";

import { apiFetch, qs } from "@/lib/client-api";
import type { Me, Page, Role, User } from "@/lib/types";

export interface UserFilters {
  q?: string;
  role?: Role | "";
  active?: "true" | "false" | "";
  page?: number;
  page_size?: number;
}

export interface UserInput {
  email: string;
  full_name: string;
  role: Role;
  password: string;
  title?: string | null;
  phone?: string | null;
}

export type UserPatch = Partial<Pick<User, "full_name" | "role" | "is_active" | "title" | "phone">>;

export interface AuditEntry {
  id: number;
  at: string;
  actor_id: number | null;
  actor_email: string | null;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  changes: Record<string, unknown> | null;
  ip: string | null;
}

export const usersApi = {
  list: (f: UserFilters) => apiFetch<Page<User>>(`/users${qs({ ...f })}`),
  create: (data: UserInput) => apiFetch<User>("/users", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: UserPatch) => apiFetch<User>(`/users/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  setPassword: (id: number, new_password: string) =>
    apiFetch<{ detail: string }>(`/users/${id}/password`, { method: "POST", body: JSON.stringify({ new_password }) }),
  updateMe: (data: Partial<Pick<Me, "full_name" | "title" | "phone" | "timezone">>) =>
    apiFetch<Me>("/auth/me", { method: "PATCH", body: JSON.stringify(data) }),
  audit: (f: { action?: string; entity_type?: string; page?: number; page_size?: number }) =>
    apiFetch<Page<AuditEntry>>(`/audit${qs({ ...f })}`),
};
