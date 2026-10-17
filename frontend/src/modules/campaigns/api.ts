"use client";

import type { Tone } from "@/components/ui/Pill";
import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export type CampaignStatus = "draft" | "scheduled" | "sending" | "paused" | "sent";

export interface RecipientCounts {
  total: number;
  pending: number;
  queued: number;
  sent: number;
  failed: number;
  skipped: number;
}

export interface CampaignSummary {
  id: number;
  name: string;
  status: CampaignStatus;
  scheduled_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  template_name: string | null;
  target_list_name: string | null;
  audience: number;
  reachable: number;
  recipients: RecipientCounts;
  updated_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface TemplateSummary {
  id: number;
  name: string;
  subject: string;
  preheader: string | null;
  version: number;
  updated_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface TargetList {
  id: number;
  name: string;
  description: string | null;
  kind: "static" | "segment";
  rules: SegmentRules | null;
  members: number;
  reachable: number;
  updated_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface SegmentOp {
  op: string;
  label: string;
}

export interface SegmentField {
  field: string;
  label: string;
  value_kind: string;
  ops: SegmentOp[];
}

export interface SegmentRule {
  field: string;
  op: string;
  value: unknown;
}

export interface SegmentRules {
  match: "all" | "any";
  rules: SegmentRule[];
}

export interface AudienceMember {
  customer_id: number;
  full_name: string;
  company: string | null;
  email: string | null;
  customer_type: string | null;
  marketing_consent: boolean;
  unsubscribed: boolean;
  suppressed: boolean;
  reachable: boolean;
  added_at: string | null;
}

export interface MembersAdded {
  added: number;
  already: number;
  missing: number;
  total: number;
}

export interface Template {
  id: number;
  name: string;
  subject: string;
  preheader: string | null;
  html: string;
  text: string;
  version: number;
  updated_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export type SuppressionReason = "unsubscribed" | "bounced" | "complained" | "manual";

export interface Suppression {
  id: number;
  email: string;
  reason: SuppressionReason;
  source: string | null;
  note: string | null;
  created_at: string;
}

export interface LinkClicks {
  url: string;
  recipients: number;
}

export interface CampaignReport {
  campaign_id: number;
  name: string;
  status: CampaignStatus;
  scheduled_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  template_name: string | null;
  target_list_name: string | null;
  recipients: RecipientCounts;
  delivered: number;
  opened: number;
  clicked: number;
  unsubscribed: number;
  open_rate: number | null;
  click_rate: number | null;
  links: LinkClicks[];
}

export interface CampaignStats {
  days: number;
  campaigns: number;
  sent: number;
  opened: number;
  clicked: number;
  unsubscribed: number;
  failed: number;
  skipped: number;
  open_rate: number | null;
  click_rate: number | null;
}

export const STATUS_LABEL: Record<CampaignStatus, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  sending: "Sending",
  paused: "Paused",
  sent: "Sent",
};

export const STATUS_TONE: Record<CampaignStatus, Tone> = {
  draft: "neutral",
  scheduled: "info",
  sending: "accent",
  paused: "warning",
  sent: "success",
};

export function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}%`;
}

export const campaignsApi = {
  list: (page = 1, pageSize = 25, status?: string, q?: string) =>
    apiFetch<Page<CampaignSummary>>(`/campaigns${qs({ page, page_size: pageSize, status, q })}`),
  get: (id: number) => apiFetch<CampaignSummary>(`/campaigns/${id}`),
  create: (data: { name: string; template_id: number; target_list_id: number }) =>
    apiFetch<CampaignSummary>("/campaigns", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Partial<{ name: string; template_id: number; target_list_id: number }>) =>
    apiFetch<CampaignSummary>(`/campaigns/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) => apiFetch<void>(`/campaigns/${id}`, { method: "DELETE" }),
  schedule: (id: number, scheduledAt: string) =>
    apiFetch<CampaignSummary>(`/campaigns/${id}/schedule`, {
      method: "POST",
      body: JSON.stringify({ scheduled_at: scheduledAt }),
    }),
  send: (id: number) => apiFetch<CampaignSummary>(`/campaigns/${id}/send`, { method: "POST" }),
  pause: (id: number) => apiFetch<CampaignSummary>(`/campaigns/${id}/pause`, { method: "POST" }),
  resume: (id: number) => apiFetch<CampaignSummary>(`/campaigns/${id}/resume`, { method: "POST" }),
  stats: (days = 7) => apiFetch<CampaignStats>(`/campaigns/stats${qs({ days })}`),
  report: (id: number) => apiFetch<CampaignReport>(`/campaigns/${id}/report`),
  segmentFields: () => apiFetch<SegmentField[]>("/campaigns/segment-fields"),
  lists: {
    list: (page = 1, pageSize = 25, kind?: string, q?: string) =>
      apiFetch<Page<TargetList>>(`/campaigns/lists${qs({ page, page_size: pageSize, kind, q })}`),
    get: (id: number) => apiFetch<TargetList>(`/campaigns/lists/${id}`),
    members: (id: number, page = 1, pageSize = 25, q?: string) =>
      apiFetch<Page<AudienceMember>>(`/campaigns/lists/${id}/members${qs({ page, page_size: pageSize, q })}`),
    addMembers: (id: number, customerIds: number[]) =>
      apiFetch<MembersAdded>(`/campaigns/lists/${id}/members`, {
        method: "POST",
        body: JSON.stringify({ customer_ids: customerIds }),
      }),
    removeMember: (id: number, customerId: number) =>
      apiFetch<void>(`/campaigns/lists/${id}/members/${customerId}`, { method: "DELETE" }),
    create: (data: { name: string; description?: string | null; kind?: "static" | "segment"; rules?: SegmentRules | null }) =>
      apiFetch<TargetList>("/campaigns/lists", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Partial<{ name: string; description?: string | null; rules?: SegmentRules | null }>) =>
      apiFetch<TargetList>(`/campaigns/lists/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    remove: (id: number) => apiFetch<void>(`/campaigns/lists/${id}`, { method: "DELETE" }),
  },
  templates: {
    list: (page = 1, pageSize = 25, q?: string) =>
      apiFetch<Page<TemplateSummary>>(`/campaigns/templates${qs({ page, page_size: pageSize, q })}`),
    get: (id: number) => apiFetch<Template>(`/campaigns/templates/${id}`),
    create: (data: { name: string; subject: string; preheader?: string | null; html: string; text?: string | null }) =>
      apiFetch<Template>("/campaigns/templates", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Partial<{ name: string; subject: string; preheader?: string | null; html: string; text?: string | null }>) =>
      apiFetch<Template>(`/campaigns/templates/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    remove: (id: number) => apiFetch<void>(`/campaigns/templates/${id}`, { method: "DELETE" }),
    preview: (id: number, customerId?: number) =>
      apiFetch<{ subject: string; preheader: string | null; html: string; text: string }>(
        `/campaigns/templates/${id}/preview${qs({ customer_id: customerId })}`,
      ),
  },
  suppressions: {
    list: (page = 1, pageSize = 25, reason?: SuppressionReason, q?: string) =>
      apiFetch<Page<Suppression>>(`/campaigns/suppressions${qs({ page, page_size: pageSize, reason, q })}`),
    add: (data: { email: string; reason: SuppressionReason; note?: string | null }) =>
      apiFetch<Suppression>("/campaigns/suppressions", { method: "POST", body: JSON.stringify(data) }),
    release: (id: number) => apiFetch<void>(`/campaigns/suppressions/${id}`, { method: "DELETE" }),
  },
};
