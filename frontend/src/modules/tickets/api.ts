"use client";

import type { Tone } from "@/components/ui/Pill";
import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

export type TicketStatus = "new" | "open" | "pending" | "resolved" | "closed";
export type TicketView = "all" | "mine" | "unassigned";
export type TicketState = "unresolved" | "resolved" | "all";
/** Internal note (only the team sees it) or a reply (emailed to the customer). */
export type MessageKind = "note" | "reply";

export interface Ticket {
  id: number;
  number: string | null;
  subject: string;
  description: string | null;
  ticket_type: string | null;
  priority: string;
  channel: string;
  status: TicketStatus;
  customer_id: number | null;
  customer_name: string | null;
  shop_order_id: number | null;
  assignee_id: number | null;
  assignee_name: string | null;
  sla_policy_id: number | null;
  first_response_due_at: string | null;
  resolve_due_at: string | null;
  first_responded_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  first_response_breached: boolean;
  resolve_breached: boolean;
  is_overdue: boolean;
  custom_fields: Record<string, unknown>;
  created_at: string;
  created_by: number | null;
  updated_at: string;
}

export interface TicketMessage {
  id: number;
  direction: "internal" | "outbound" | "inbound";
  body: string;
  from_email: string | null;
  to_email: string | null;
  from_phone: string | null;
  created_by: number | null;
  created_at: string;
  author_name: string | null;
}

export interface TicketInput {
  subject?: string;
  description?: string | null;
  ticket_type?: string | null;
  priority?: string;
  channel?: string | null;
  customer_id?: number | null;
  shop_order_id?: number | null;
  assignee_id?: number | null;
  status?: TicketStatus;
  custom_fields?: Record<string, unknown>;
}

export interface TicketFilters {
  view?: TicketView;
  state?: TicketState;
  status?: TicketStatus | "";
  priority?: string;
  type?: string;
  channel?: string;
  customer_id?: number;
  breached?: boolean;
  /** The inbox's question: the customer's message is the newest one, so nobody has answered yet. */
  needs_reply?: boolean;
  q?: string;
  page?: number;
  page_size?: number;
}

export interface TicketSummary {
  open: number;
  unassigned: number;
  overdue: number;
  mine: number;
}

export interface SlaPolicy {
  id: number;
  name: string;
  ticket_type: string | null;
  priority: string | null;
  first_response_minutes: number;
  resolve_minutes: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SlaPolicyInput {
  name: string;
  ticket_type?: string | null;
  priority?: string | null;
  first_response_minutes: number;
  resolve_minutes: number;
  is_active?: boolean;
}

export interface CannedResponse {
  id: number;
  title: string;
  body: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CannedResponseInput {
  title: string;
  body: string;
  is_active?: boolean;
}

export const STATUS_LABEL: Record<TicketStatus, string> = {
  new: "New",
  open: "Open",
  pending: "On hold",
  resolved: "Resolved",
  closed: "Closed",
};

export const STATUS_TONE: Record<TicketStatus, Tone> = {
  new: "accent",
  open: "info",
  pending: "warning",
  resolved: "success",
  closed: "neutral",
};

export const STATUSES: TicketStatus[] = ["new", "open", "pending", "resolved", "closed"];

/** Mirrors the API's status rules, so the UI never offers a move the server would refuse. */
export const NEXT_STATUSES: Record<TicketStatus, TicketStatus[]> = {
  new: ["open", "pending", "resolved", "closed"],
  open: ["pending", "resolved", "closed"],
  pending: ["open", "resolved", "closed"],
  resolved: ["open", "closed"],
  closed: ["open"],
};

export interface SlaBadge {
  tone: Tone;
  text: string;
  title: string;
}

/** The response-time badge for a ticket: met, due soon, late or overdue. `null` when no target applies. */
export function slaState(t: Ticket, now = Date.now()): SlaBadge | null {
  if (!t.resolve_due_at) return null;
  const title = `Reply by ${formatDateTime(t.first_response_due_at)} · resolve by ${formatDateTime(t.resolve_due_at)}`;
  if (t.status === "resolved" || t.status === "closed") {
    return t.first_response_breached || t.resolve_breached
      ? { tone: "danger", text: "SLA missed", title }
      : { tone: "success", text: "SLA met", title };
  }
  const left = new Date(t.resolve_due_at).getTime() - now;
  if (t.resolve_breached || left < 0) return { tone: "danger", text: "Overdue", title };
  const reply = t.first_response_due_at ? new Date(t.first_response_due_at).getTime() : null;
  const replyLate = t.first_response_breached || (reply !== null && t.first_responded_at === null && reply < now);
  const text = `Due ${slaSpan(left)}`;
  if (replyLate) return { tone: "warning", text: `Reply late · ${text}`, title };
  return { tone: left < 4 * 3600_000 ? "warning" : "neutral", text, title };
}

/** "in 3h", "in 2d" — how long is left before a target. */
export function slaSpan(ms: number): string {
  const minutes = Math.max(0, Math.round(ms / 60000));
  if (minutes < 60) return `in ${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `in ${hours}h`;
  return `in ${Math.round(hours / 24)}d`;
}

/** "8 hours" / "2 business days" — SLA targets are counted in business hours (8 h = one day). */
export function formatBusinessMinutes(minutes: number): string {
  if (minutes % 480 === 0) {
    const days = minutes / 480;
    return `${days} business ${days === 1 ? "day" : "days"}`;
  }
  const hours = Math.round((minutes / 60) * 10) / 10;
  return `${hours} ${hours === 1 ? "hour" : "hours"}`;
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const ticketsApi = {
  list: (f: TicketFilters) => apiFetch<Page<Ticket>>(`/tickets${qs({ ...f })}`),
  summary: () => apiFetch<TicketSummary>("/tickets/summary"),
  get: (id: number) => apiFetch<Ticket>(`/tickets/${id}`),
  create: (data: TicketInput) => apiFetch<Ticket>("/tickets", json("POST", data)),
  update: (id: number, data: TicketInput) => apiFetch<Ticket>(`/tickets/${id}`, json("PATCH", data)),
  remove: (id: number) => apiFetch<void>(`/tickets/${id}`, { method: "DELETE" }),
  messages: (id: number) => apiFetch<TicketMessage[]>(`/tickets/${id}/messages`),
  addMessage: (id: number, data: { body: string; kind: MessageKind }) => apiFetch<TicketMessage>(`/tickets/${id}/messages`, json("POST", data)),
  slaPolicies: () => apiFetch<SlaPolicy[]>("/tickets/sla-policies"),
  createSla: (data: SlaPolicyInput) => apiFetch<SlaPolicy>("/tickets/sla-policies", json("POST", data)),
  updateSla: (id: number, data: Partial<SlaPolicyInput>) => apiFetch<SlaPolicy>(`/tickets/sla-policies/${id}`, json("PATCH", data)),
  cannedResponses: () => apiFetch<CannedResponse[]>("/tickets/canned-responses"),
  createCanned: (data: CannedResponseInput) => apiFetch<CannedResponse>("/tickets/canned-responses", json("POST", data)),
  updateCanned: (id: number, data: Partial<CannedResponseInput>) => apiFetch<CannedResponse>(`/tickets/canned-responses/${id}`, json("PATCH", data)),
  removeCanned: (id: number) => apiFetch<void>(`/tickets/canned-responses/${id}`, { method: "DELETE" }),
};

/** Only the fields that actually changed — so saving a ticket never resets its SLA clock. */
export function ticketPatch(before: Ticket, desired: TicketInput): TicketInput {
  const patch: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(desired)) {
    const current = (before as unknown as Record<string, unknown>)[key] ?? null;
    if (JSON.stringify(current) !== JSON.stringify(value ?? null)) patch[key] = value ?? null;
  }
  return patch as TicketInput;
}
