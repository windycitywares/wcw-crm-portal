"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ColorTag } from "@/components/ui/ColorTag";
import { Select } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { CustomFieldsView } from "@/modules/records/CustomFields";
import { TagEditor } from "@/modules/records/TagEditor";
import { Timeline } from "@/modules/records/Timeline";
import { useDirectory } from "@/modules/records/useDirectory";
import { customFieldsApi, type FieldDef } from "@/modules/settings/api";
import { useLookups } from "@/modules/settings/useLookups";
import { RecordTasks } from "@/modules/tasks/RecordTasks";
import { NEXT_STATUSES, slaState, STATUS_LABEL, STATUS_TONE, ticketsApi, type Ticket, type TicketStatus } from "@/modules/tickets/api";
import { Conversation } from "@/modules/tickets/Conversation";
import { TicketDialog } from "@/modules/tickets/TicketDialog";

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 break-words text-sm">{children ?? <span className="text-muted">—</span>}</dd>
    </div>
  );
}

export default function TicketPage() {
  const { id } = useParams<{ id: string }>();
  const ticketId = Number(id);
  const router = useRouter();
  const toast = useToast();
  const { user, can } = useAuth();
  const directory = useDirectory();
  const { name } = directory;
  const lookups = useLookups();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [defs, setDefs] = useState<FieldDef[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);

  const load = useCallback(async () => {
    try {
      setTicket(await ticketsApi.get(ticketId));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the ticket");
    }
  }, [ticketId]);

  useEffect(() => {
    void load();
    customFieldsApi
      .list("ticket")
      .then(setDefs)
      .catch(() => setDefs([]));
  }, [load]);

  if (error) {
    return (
      <>
        <PageHeader title="Ticket" back={{ href: "/tickets", label: "Tickets" }} />
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      </>
    );
  }
  if (!ticket) return <p className="text-sm text-muted">Loading…</p>;

  const record = { type: "ticket", id: ticket.id };
  const mayEdit = can("tickets:edit");
  const canAssign = can("tickets:assign");
  const priority = lookups.find("ticket_priority", ticket.priority);
  const type = lookups.find("ticket_type", ticket.ticket_type);
  const sla = slaState(ticket);
  const changed = () => setRefresh((n) => n + 1);
  const owners = [...directory.people.values()]
    .filter((p) => p.is_active || p.id === ticket.assignee_id)
    .filter((p) => canAssign || p.id === user?.id || p.id === ticket.assignee_id)
    .sort((a, b) => a.full_name.localeCompare(b.full_name));

  const next = NEXT_STATUSES[ticket.status];
  const quick: { status: TicketStatus; label: string }[] = [];
  if (next.includes("open") && ticket.status !== "new") quick.push({ status: "open", label: ticket.status === "pending" ? "Resume" : "Reopen" });
  if (next.includes("pending")) quick.push({ status: "pending", label: "On hold" });
  if (next.includes("resolved")) quick.push({ status: "resolved", label: "Resolve" });
  if (next.includes("closed")) quick.push({ status: "closed", label: "Close" });

  async function setStatus(status: TicketStatus) {
    setBusy(true);
    try {
      setTicket(await ticketsApi.update(ticketId, { status }));
      toast.push({ title: `Ticket ${STATUS_LABEL[status].toLowerCase()}` });
      changed();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't change the status", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  async function assign(assigneeId: number | null) {
    try {
      setTicket(await ticketsApi.update(ticketId, { assignee_id: assigneeId }));
      toast.push({ title: assigneeId ? "Ticket assigned" : "Ticket unassigned" });
      changed();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't assign", description: err instanceof Error ? err.message : undefined });
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await ticketsApi.remove(ticketId);
      toast.push({ title: "Ticket deleted", description: ticket?.number ?? undefined });
      router.push("/tickets");
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't delete", description: err instanceof Error ? err.message : undefined });
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <>
      <PageHeader
        title={ticket.subject}
        back={{ href: "/tickets", label: "Tickets" }}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <span className="num text-muted">{ticket.number ?? `#${ticket.id}`}</span>
            <Pill tone={STATUS_TONE[ticket.status]}>{STATUS_LABEL[ticket.status]}</Pill>
            {priority && <ColorTag color={priority.color}>{priority.label}</ColorTag>}
            {type && <ColorTag color={type.color}>{type.label}</ColorTag>}
            {sla && (
              <span title={sla.title}>
                <Pill tone={sla.tone}>{sla.text}</Pill>
              </span>
            )}
            {ticket.customer_id && ticket.customer_name && (
              <Link href={`/customers/${ticket.customer_id}`} className="text-accent-strong underline">
                {ticket.customer_name}
              </Link>
            )}
          </span>
        }
        actions={
          <>
            {mayEdit &&
              quick.map((q) => (
                <Button key={q.status} variant="secondary" size="sm" disabled={busy} onClick={() => void setStatus(q.status)}>
                  {q.label}
                </Button>
              ))}
            {mayEdit && (
              <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            {mayEdit && (
              <Button variant="ghost" size="sm" className="text-danger" onClick={() => setConfirming(true)}>
                Delete
              </Button>
            )}
          </>
        }
      />

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <div className="grid content-start gap-6">
          <Panel>
            <PanelHeader title="Details" />
            <PanelBody>
              <dl className="grid gap-4 sm:grid-cols-2">
                <Detail label="Customer">
                  {ticket.customer_id && ticket.customer_name ? (
                    <Link href={`/customers/${ticket.customer_id}`} className="text-accent-strong underline">
                      {ticket.customer_name}
                    </Link>
                  ) : (
                    <span className="text-muted">Not linked</span>
                  )}
                </Detail>
                <Detail label="Shop order">{ticket.shop_order_id ? `#${ticket.shop_order_id}` : null}</Detail>
                <Detail label="Assignee">
                  {canAssign || ticket.assignee_id === user?.id || ticket.assignee_id == null ? (
                    <Select
                      aria-label="Assignee"
                      className="py-1.5 text-sm"
                      value={ticket.assignee_id ?? ""}
                      onChange={(e) => void assign(e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">Unassigned</option>
                      {owners.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.full_name}
                          {o.id === user?.id ? " (you)" : ""}
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <span>{ticket.assignee_name ?? "Unassigned"}</span>
                  )}
                </Detail>
                <Detail label="Opened">{`${formatDateTime(ticket.created_at)} by ${name(ticket.created_by)}`}</Detail>
                <Detail label="First reply">
                  {ticket.first_responded_at
                    ? formatDateTime(ticket.first_responded_at)
                    : ticket.first_response_due_at
                      ? `Due ${formatDateTime(ticket.first_response_due_at)}`
                      : null}
                  {ticket.first_response_breached && <Pill tone="danger">Late</Pill>}
                </Detail>
                <Detail label="Resolve by">
                  {ticket.resolve_due_at ? formatDateTime(ticket.resolve_due_at) : null}
                  {ticket.resolve_breached && ticket.status !== "resolved" && ticket.status !== "closed" && <Pill tone="danger">Overdue</Pill>}
                </Detail>
                {ticket.resolved_at && <Detail label="Resolved">{formatDateTime(ticket.resolved_at)}</Detail>}
                {ticket.closed_at && <Detail label="Closed">{formatDateTime(ticket.closed_at)}</Detail>}
              </dl>
              {ticket.description && <p className="mt-4 whitespace-pre-wrap border-t border-line pt-4 text-sm">{ticket.description}</p>}
              <div className="mt-4">
                <CustomFieldsView defs={defs} values={ticket.custom_fields} />
              </div>
            </PanelBody>
          </Panel>

          <Conversation ticket={ticket} onChanged={changed} />

          <Panel>
            <PanelHeader title="Tags" />
            <PanelBody>
              <TagEditor record={record} canEdit={mayEdit} onChange={changed} />
            </PanelBody>
          </Panel>
        </div>

        <div className="grid content-start gap-6">
          {can("tasks:view") && <RecordTasks type="ticket" id={ticket.id} label={`${ticket.number ?? ""} ${ticket.subject}`.trim()} onChange={changed} />}
          <Timeline record={record} refreshKey={`${refresh}-${ticket.updated_at}`} />
        </div>
      </div>

      <TicketDialog
        open={editing}
        ticket={ticket}
        onClose={() => setEditing(false)}
        onSaved={(saved) => {
          if (saved) setTicket(saved);
          changed();
        }}
      />

      <ConfirmDialog
        open={confirming}
        title="Delete this ticket?"
        message={`${ticket.number ?? ""} and its messages will be removed from the queue.`}
        confirmLabel="Delete ticket"
        tone="danger"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setConfirming(false)}
      />
    </>
  );
}
