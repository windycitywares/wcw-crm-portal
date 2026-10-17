"use client";

import type { Tone } from "@/components/ui/Pill";
import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export type LeadStatus = "new" | "contacted" | "qualified" | "unqualified" | "converted";
/** The statuses a person may set — `converted` only happens through the convert endpoint. */
export type LeadOpenStatus = Exclude<LeadStatus, "converted">;
export type LeadView = "all" | "mine" | "unassigned";
/** Money may arrive as a JSON number or a string — always pass it through Number(). */
export type Money = string | number;

export interface Lead {
  id: number;
  first_name: string | null;
  last_name: string | null;
  full_name: string;
  display_name: string;
  company: string | null;
  email: string | null;
  phone: string | null;
  source: string | null;
  status: LeadStatus;
  notes: string | null;
  owner_id: number | null;
  owner_name: string | null;
  converted_at: string | null;
  converted_customer_id: number | null;
  converted_customer_name: string | null;
  converted_deal_id: number | null;
  converted_deal_title: string | null;
  custom_fields: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface LeadInput {
  first_name?: string | null;
  last_name?: string | null;
  company?: string | null;
  email?: string | null;
  phone?: string | null;
  source?: string | null;
  status?: LeadOpenStatus;
  notes?: string | null;
  owner_id?: number | null;
}

export interface LeadFilters {
  view?: LeadView;
  /** "all" asks for every status (the API's default is every status too). */
  status?: LeadStatus | "all";
  source?: string;
  owner_id?: number;
  q?: string;
  page?: number;
  page_size?: number;
}

export interface LeadSummary {
  new: number;
  contacted: number;
  qualified: number;
  unqualified: number;
  converted: number;
  total: number;
  unassigned: number;
}

/** What converting a lead makes: a customer (given, matched by email, or made from the lead) and a deal. */
export interface LeadConvertInput {
  customer_id?: number | null;
  create_deal?: boolean;
  deal_title?: string | null;
  stage_id?: number | null;
  value?: Money;
  currency?: string;
  expected_close_on?: string | null;
}

export const STATUS_LABEL: Record<LeadStatus, string> = {
  new: "New",
  contacted: "Contacted",
  qualified: "Qualified",
  unqualified: "Unqualified",
  converted: "Converted",
};
export const STATUS_TONE: Record<LeadStatus, Tone> = {
  new: "info",
  contacted: "accent",
  qualified: "success",
  unqualified: "neutral",
  converted: "success",
};
/** The order a lead is worked in; "Unqualified" is where it goes when it is not worth chasing. */
export const WORKFLOW: LeadOpenStatus[] = ["new", "contacted", "qualified", "unqualified"];
export const STATUSES: LeadStatus[] = [...WORKFLOW, "converted"];

/** "3 new · 5 in progress · 2 converted · 7 unassigned of 12 leads." — the line under the page title. */
export function describeSummary(s: LeadSummary): string {
  const inProgress = s.contacted + s.qualified;
  const parts = [`${s.new} new`];
  if (inProgress) parts.push(`${inProgress} in progress`);
  if (s.unqualified) parts.push(`${s.unqualified} unqualified`);
  if (s.converted) parts.push(`${s.converted} converted`);
  if (s.unassigned) parts.push(`${s.unassigned} unassigned`);
  return `${parts.join(" · ")} of ${s.total} ${s.total === 1 ? "lead" : "leads"}.`;
}

/** Company and email under the name — blank when that would just repeat the name. */
export function leadSubtitle(lead: Lead): string {
  const line = [lead.company, lead.email].filter(Boolean).join(" · ");
  return line === lead.display_name ? "" : line;
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const leadsApi = {
  summary: () => apiFetch<LeadSummary>("/leads/summary"),
  list: (f: LeadFilters) => apiFetch<Page<Lead>>(`/leads${qs({ ...f })}`),
  lead: (id: number) => apiFetch<Lead>(`/leads/${id}`),
  create: (data: LeadInput) => apiFetch<Lead>("/leads", json("POST", data)),
  update: (id: number, data: LeadInput) => apiFetch<Lead>(`/leads/${id}`, json("PATCH", data)),
  remove: (id: number) => apiFetch<void>(`/leads/${id}`, { method: "DELETE" }),
  convert: (id: number, data: LeadConvertInput) => apiFetch<Lead>(`/leads/${id}/convert`, json("POST", data)),
};

/**
 * Only the fields that actually changed, so the lead's timeline says what really moved. A field left as
 * `undefined` isn't in the form at all (a converted lead has no status to set) and is never sent.
 */
export function leadPatch(before: Lead, desired: LeadInput): LeadInput {
  const patch: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(desired)) {
    if (value === undefined) continue;
    const current = (before as unknown as Record<string, unknown>)[key] ?? null;
    if (JSON.stringify(current) !== JSON.stringify(value ?? null)) patch[key] = value ?? null;
  }
  return patch as LeadInput;
}
