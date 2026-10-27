"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { LiveUpdatesBar } from "@/components/ui/LiveUpdatesBar";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { Segmented } from "@/components/ui/Segmented";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { useLookups } from "@/modules/settings/useLookups";
import { ticketsApi, type Ticket, type TicketFilters } from "@/modules/tickets/api";
import { TicketDialog } from "@/modules/tickets/TicketDialog";
import { TicketList } from "@/modules/tickets/TicketList";

const PAGE_SIZE = 25;
const VIEWS = [
  { value: "all", label: "All" },
  { value: "mine", label: "Mine" },
  { value: "unassigned", label: "Unassigned" },
] as const;
const STATES = [
  { value: "unresolved", label: "Open" },
  { value: "resolved", label: "Resolved" },
  { value: "all", label: "Everything" },
] as const;

export default function TicketsPage() {
  const { can } = useAuth();
  const lookups = useLookups();
  const [filters, setFilters] = useState<TicketFilters>({ view: "all", state: "unresolved", page: 1 });
  const [search, setSearch] = useState("");
  const [data, setData] = useState<Page<Ticket> | null>(null);
  const [summary, setSummary] = useState<{ open: number; unassigned: number; overdue: number; mine: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await ticketsApi.list({ ...filters, page_size: PAGE_SIZE }));
      setSummary(await ticketsApi.summary());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load tickets");
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load]);

  // Deep links: /tickets?customer_id=7&state=all (from a customer page) pre-fills the filters.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const customerId = Number(params.get("customer_id"));
    const state = params.get("state");
    const patch: Partial<TicketFilters> = {};
    if (customerId > 0) patch.customer_id = customerId;
    if (state === "unresolved" || state === "resolved" || state === "all") patch.state = state;
    if (params.get("priority")) patch.priority = params.get("priority") as string;
    if (params.get("type")) patch.type = params.get("type") as string;
    if (params.get("channel")) patch.channel = params.get("channel") as string;
    const q = params.get("q");
    if (q) {
      patch.q = q;
      setSearch(q);
    }
    if (Object.keys(patch).length > 0) setFilters((f) => ({ ...f, ...patch, page: 1 }));
  }, []);

  useEffect(() => {
    if (search === (filters.q ?? "")) return;
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search || undefined, page: 1 })), 300);
    return () => clearTimeout(t);
  }, [search, filters.q]);

  const update = (patch: Partial<TicketFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const describe = summary
    ? `${summary.open} open${summary.unassigned ? `, ${summary.unassigned} unassigned` : ""}${summary.overdue ? `, ${summary.overdue} overdue` : ""}${summary.mine ? ` · ${summary.mine} assigned to you` : ""}.`
    : "Customer questions, complaints and requests.";

  return (
    <>
      <PageHeader
        title="Tickets"
        description={describe}
        actions={
          can("tickets:edit") ? (
            <Button size="sm" onClick={() => setAdding(true)}>
              New ticket
            </Button>
          ) : undefined
        }
      />
      <LiveUpdatesBar types={["ticket"]} noun="ticket" onRefresh={() => void load()} />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Segmented label="Whose tickets" options={VIEWS} value={filters.view ?? "all"} onChange={(view) => update({ view })} />
        <Segmented label="Show" options={STATES} value={filters.state ?? "unresolved"} onChange={(state) => update({ state })} />
        <Field label="Priority" className="w-40">
          {(p) => (
            <Select {...p} value={filters.priority ?? ""} onChange={(e) => update({ priority: e.target.value })}>
              <option value="">Any priority</option>
              {lookups.options("ticket_priority").map((v) => (
                <option key={v.key} value={v.key}>
                  {v.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Type" className="w-40">
          {(p) => (
            <Select {...p} value={filters.type ?? ""} onChange={(e) => update({ type: e.target.value })}>
              <option value="">Any type</option>
              {lookups.options("ticket_type").map((v) => (
                <option key={v.key} value={v.key}>
                  {v.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Channel" className="w-40">
          {(p) => (
            <Select {...p} value={filters.channel ?? ""} onChange={(e) => update({ channel: e.target.value })}>
              <option value="">Any channel</option>
              {lookups.options("ticket_channel").map((v) => (
                <option key={v.key} value={v.key}>
                  {v.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Search" className="min-w-0 flex-1 sm:max-w-xs">
          {(p) => <Input {...p} type="search" placeholder="Subject or customer" value={search} onChange={(e) => setSearch(e.target.value)} />}
        </Field>
      </div>

      {filters.customer_id != null && (
        <p className="mb-4 text-sm">
          <span className="inline-flex items-center gap-2 rounded-full bg-sand px-3 py-1">
            Showing one customer&apos;s tickets
            <button type="button" className="inline-flex items-center gap-1 text-muted hover:text-ink" onClick={() => update({ customer_id: undefined })}>
              <Icon name="close" className="size-3.5" />
              Clear
            </button>
          </span>
        </p>
      )}

      {error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      )}

      <Panel>
        <TicketList
          tickets={data?.items ?? null}
          empty={filters.state === "unresolved" ? "No open tickets. Nice." : "No tickets match."}
        />
      </Panel>
      {data && data.total > PAGE_SIZE && (
        <Pagination className="mt-4" page={filters.page ?? 1} pageSize={PAGE_SIZE} total={data.total} onPage={(page) => setFilters((f) => ({ ...f, page }))} />
      )}

      <TicketDialog open={adding} ticket={null} onClose={() => setAdding(false)} onSaved={() => void load()} />
    </>
  );
}
