"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Icon } from "@/components/ui/Icon";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { cn } from "@/lib/utils";
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

function Segmented<T extends string>({ label, options, value, onChange }: { label: string; options: readonly { value: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap rounded-[var(--radius-control)] border border-line bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-[calc(var(--radius-control)-2px)] px-3 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-accent",
            value === o.value ? "bg-accent text-on-accent" : "text-ink hover:bg-sand",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

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
