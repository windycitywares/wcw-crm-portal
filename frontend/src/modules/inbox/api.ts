"use client";

import { apiFetch } from "@/lib/client-api";

/**
 * The mailboxes the CRM reads (SPEC §3.9). Reading one means the CRM owns it: unread mail becomes
 * tickets. The password goes one way — it is sent when saving and never comes back.
 */

export type MailboxSecurity = "ssl" | "starttls" | "none";

export interface Mailbox {
  id: number;
  address: string;
  display_name: string | null;
  imap_host: string;
  imap_port: number;
  imap_security: MailboxSecurity;
  imap_user: string | null;
  folder: string;
  is_active: boolean;
  /** When the poller last read it, and whatever went wrong the last time it tried. */
  last_polled_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface MailboxInput {
  address: string;
  display_name: string | null;
  imap_host: string;
  imap_port: number;
  imap_security: MailboxSecurity;
  imap_user: string | null;
  /** Blank on an edit keeps the stored password; required when adding. */
  imap_password?: string;
  folder: string;
  is_active: boolean;
}

/** What the mailbox answered when we opened it just now — a test writes nothing. */
export interface MailboxCheck {
  ok: boolean;
  detail: string;
  folder: string | null;
  messages: number | null;
  unseen: number | null;
}

/** IMAP's usual ports, so choosing a security fills the port in for you. */
export const PORT_FOR: Record<MailboxSecurity, number> = { ssl: 993, starttls: 143, none: 143 };
export const SECURITY_LABEL: Record<MailboxSecurity, string> = { ssl: "SSL/TLS", starttls: "STARTTLS", none: "None" };

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const inboxApi = {
  list: () => apiFetch<Mailbox[]>("/inbox/accounts"),
  create: (data: MailboxInput) => apiFetch<Mailbox>("/inbox/accounts", json("POST", data)),
  update: (id: number, data: Partial<MailboxInput>) => apiFetch<Mailbox>(`/inbox/accounts/${id}`, json("PATCH", data)),
  remove: (id: number) => apiFetch<void>(`/inbox/accounts/${id}`, { method: "DELETE" }),
  test: (id: number) => apiFetch<MailboxCheck>(`/inbox/accounts/${id}/test`, { method: "POST" }),
};
