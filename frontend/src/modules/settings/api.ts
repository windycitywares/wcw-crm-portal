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

export interface EmailSettings {
  enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_security: "ssl" | "starttls" | "none";
  smtp_user: string;
  smtp_password_set: boolean;
  from_name: string;
  from_address: string;
  reply_to: string;
  footer_address: string;
  daily_limit: number;
  per_minute: number;
}

export type Day = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";
export interface BusinessHours {
  timezone: string;
  days: Record<Day, { open: string; close: string } | null>;
  holidays: string[];
}

interface Group<T> {
  key: string;
  label: string;
  values: T;
}

export const settingsApi = {
  get: <T>(key: string) => apiFetch<Group<T>>(`/settings/${key}`),
  save: <T>(key: string, values: Record<string, unknown>) => apiFetch<Group<T>>(`/settings/${key}`, json("PUT", values)),
  testEmail: (to: string) => apiFetch<{ ok: boolean; detail: string }>("/settings/email/test", json("POST", { to })),
};

export type DeployMode = "auto" | "schedule" | "paused";
export interface DeployStatus {
  mode: DeployMode;
  interval_minutes: number;
  schedule_times: string[];
  timezone: string;
  requested_at: string | null;
  requested_by: string | null;
  last_check_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  running: boolean;
  last_reason: string | null;
  last_result: string | null;
  api: { commit: string | null; subject: string | null; date: string | null };
  web_build: string | null;
  cron_seen: boolean;
}

export const deployApi = {
  status: () => apiFetch<DeployStatus>("/deploy"),
  configure: (data: { mode: DeployMode; interval_minutes: number; schedule_times: string[] }) =>
    apiFetch<DeployStatus>("/deploy/config", json("PUT", data)),
  now: () => apiFetch<DeployStatus>("/deploy/now", { method: "POST" }),
  cancel: () => apiFetch<DeployStatus>("/deploy/now", { method: "DELETE" }),
  log: (lines = 200) => apiFetch<{ log: string }>(`/deploy/log?lines=${lines}`),
};
