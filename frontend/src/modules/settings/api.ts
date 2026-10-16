"use client";

import { apiFetch, qs } from "@/lib/client-api";

export interface LookupValue {
  id: number;
  kind: string;
  key: string;
  label: string;
  color: string | null;
  sort_order: number;
  is_active: boolean;
  updated_at: string;
}

export interface LookupKind {
  key: string;
  label: string;
  description: string;
  values: LookupValue[];
}

export interface Tag {
  id: number;
  name: string;
  color: string | null;
  uses?: number;
}

export type FieldType = "text" | "textarea" | "number" | "date" | "checkbox" | "select" | "multiselect" | "email" | "url";

export interface FieldDef {
  id: number;
  entity_type: string;
  key: string;
  label: string;
  field_type: FieldType;
  options: string[] | null;
  required: boolean;
  help_text: string | null;
  sort_order: number;
  is_active: boolean;
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const lookupsApi = {
  kinds: () => apiFetch<LookupKind[]>("/lookups"),
  create: (kind: string, data: { label: string; color?: string | null }) => apiFetch<LookupValue>(`/lookups/${kind}`, json("POST", data)),
  update: (kind: string, id: number, data: Partial<Pick<LookupValue, "label" | "color" | "is_active">>) =>
    apiFetch<LookupValue>(`/lookups/${kind}/${id}`, json("PATCH", data)),
  reorder: (kind: string, ids: number[]) => apiFetch<LookupValue[]>(`/lookups/${kind}/order`, json("PUT", { ids })),
};

export const tagsApi = {
  search: (q = "", limit = 200) => apiFetch<Tag[]>(`/tags${qs({ q, limit })}`),
  create: (data: { name: string; color?: string | null }) => apiFetch<Tag>("/tags", json("POST", data)),
  update: (id: number, data: { name?: string; color?: string | null }) => apiFetch<Tag>(`/tags/${id}`, json("PATCH", data)),
  remove: (id: number) => apiFetch<void>(`/tags/${id}`, { method: "DELETE" }),
};

export const customFieldsApi = {
  types: () => apiFetch<{ key: FieldType; label: string }[]>("/custom-fields/types"),
  recordTypes: () => apiFetch<{ key: string; label: string }[]>("/custom-fields/record-types"),
  list: (entity: string) => apiFetch<FieldDef[]>(`/custom-fields/${entity}`),
  create: (entity: string, data: { label: string; field_type: FieldType; options?: string[] | null; required?: boolean; help_text?: string | null }) =>
    apiFetch<FieldDef>(`/custom-fields/${entity}`, json("POST", data)),
  update: (entity: string, id: number, data: Partial<Pick<FieldDef, "label" | "options" | "required" | "help_text" | "is_active">>) =>
    apiFetch<FieldDef>(`/custom-fields/${entity}/${id}`, json("PATCH", data)),
  reorder: (entity: string, ids: number[]) => apiFetch<FieldDef[]>(`/custom-fields/${entity}/order`, json("PUT", { ids })),
};

/** Move item `index` one place up (-1) or down (+1) and return the new id order. */
export function moved<T extends { id: number }>(items: T[], index: number, delta: -1 | 1): number[] {
  const ids = items.map((i) => i.id);
  const j = index + delta;
  if (j < 0 || j >= ids.length) return ids;
  [ids[index], ids[j]] = [ids[j], ids[index]];
  return ids;
}

export function errorText(err: unknown) {
  return err instanceof Error ? err.message : "Something went wrong";
}
