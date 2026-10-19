"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Textarea, Select } from "@/components/ui/Field";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { Segmented } from "@/components/ui/Segmented";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { cn, formatDateTime } from "@/lib/utils";
import { Attachments } from "@/modules/records/Attachments";
import { ticketsApi, type CannedResponse, type MessageKind, type Ticket, type TicketMessage } from "./api";

const KIND_LABEL: Record<TicketMessage["direction"], string> = {
  internal: "Internal note",
  outbound: "Reply sent",
  inbound: "Customer replied",
};

const KINDS = [
  { value: "note", label: "Internal note" },
  { value: "reply", label: "Email reply" },
] as const;

/**
 * The ticket thread, oldest first: internal notes, replies emailed to the customer, and any inbound
 * messages. The composer switches between a note (team only) and a reply (emails the customer).
 */
export function Conversation({ ticket, onChanged }: { ticket: Ticket; onChanged: () => void }) {
  const { can } = useAuth();
  const toast = useToast();
  const [messages, setMessages] = useState<TicketMessage[] | null>(null);
  const [kind, setKind] = useState<MessageKind>("note");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [canned, setCanned] = useState<CannedResponse[]>([]);

  const load = useCallback(() => {
    ticketsApi
      .messages(ticket.id)
      .then(setMessages)
      .catch(() => setMessages([]));
  }, [ticket.id]);

  useEffect(() => {
    load();
  }, [load, ticket.updated_at]);

  useEffect(() => {
    ticketsApi
      .cannedResponses()
      .then((rows) => setCanned(rows.filter((r) => r.is_active)))
      .catch(() => setCanned([]));
  }, []);

  const mayWrite = can("tickets:edit");
  const canReply = ticket.customer_id != null;

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    try {
      await ticketsApi.addMessage(ticket.id, { body: body.trim(), kind });
      setBody("");
      load();
      onChanged();
      toast.push({ title: kind === "reply" ? "Reply sent" : "Note added", description: ticket.number ?? undefined });
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't send", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel>
      <PanelHeader title="Conversation" description="Internal notes stay in the CRM; replies are emailed to the customer." />
      <PanelBody className="grid gap-4">
        {messages === null ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : messages.length === 0 ? (
          <p className="text-sm text-muted">No messages yet.</p>
        ) : (
          <ol className="grid gap-3">
            {messages.map((m) => (
              <li
                key={m.id}
                id={`message-${m.id}`}
                className={cn(
                  "scroll-mt-24 rounded-[var(--radius-control)] border px-4 py-3",
                  m.direction === "internal" && "border-line bg-sand",
                  m.direction === "outbound" && "border-accent/25 bg-accent-soft",
                  m.direction === "inbound" && "border-line bg-surface",
                )}
              >
                <div className="mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                  <Pill tone={m.direction === "inbound" ? "info" : m.direction === "outbound" ? "accent" : "neutral"}>{KIND_LABEL[m.direction]}</Pill>
                  <span>{m.direction === "inbound" ? m.from_email ?? m.from_phone ?? "Customer" : m.author_name ?? "System"}</span>
                  <span>{formatDateTime(m.created_at)}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm">{m.body}</p>
              </li>
            ))}
          </ol>
        )}

        {/* What the customer sent with their message: the ticket's files, not the thread's. A file that
            came with a message names it and links back to it above. */}
        <Attachments
          record={{ type: "ticket", id: ticket.id }}
          canEdit={mayWrite}
          refreshKey={ticket.updated_at}
          sources={Object.fromEntries((messages ?? []).map((m) => [m.id, formatDateTime(m.created_at)]))}
        />

        {mayWrite && (
          <form onSubmit={send} className="grid gap-3 border-t border-line pt-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Segmented label="Message kind" options={KINDS} value={kind} onChange={setKind} />
              {canned.length > 0 && (
                <Select
                  aria-label="Insert a saved reply"
                  className="w-full sm:w-72"
                  value=""
                  onChange={(e) => {
                    const picked = canned.find((c) => String(c.id) === e.target.value);
                    if (picked) setBody((b) => (b.trim() ? `${b.trimEnd()}\n\n${picked.body}` : picked.body));
                  }}
                >
                  <option value="">Insert a saved reply…</option>
                  {canned.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
                </Select>
              )}
            </div>
            <label className="sr-only" htmlFor="ticket-message">
              {kind === "note" ? "Internal note" : "Reply to the customer"}
            </label>
            <Textarea
              id="ticket-message"
              rows={4}
              maxLength={20000}
              placeholder={kind === "note" ? "Only your team will see this." : "This is emailed to the customer."}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted">
                {kind === "reply"
                  ? canReply
                    ? "Emails the customer and records the reply as the first response."
                    : "Link a customer before emailing a reply."
                  : "Notes are never sent to the customer."}
              </p>
              <Button type="submit" size="sm" disabled={busy || !body.trim() || (kind === "reply" && !canReply)}>
                {busy ? "Sending…" : kind === "reply" ? "Send reply" : "Add note"}
              </Button>
            </div>
          </form>
        )}
      </PanelBody>
    </Panel>
  );
}
