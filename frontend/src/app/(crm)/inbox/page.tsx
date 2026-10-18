"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Field, Input } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { Segmented } from "@/components/ui/Segmented";
import type { Page } from "@/lib/types";
import { timeAgo } from "@/lib/utils";
import { InboxList } from "@/modules/inbox/InboxList";
import { useLookups } from "@/modules/settings/useLookups";
import { ticketsApi, type Ticket, type TicketFilters } from "@/modules/tickets/api";
import { Conversation } from "@/modules/tickets/Conversation";

const PAGE_SIZE = 25;
const SHOW = [
  { value: "waiting", label: "Waiting on us" },
  { value: "all", label: "Everything open" },
] as const;

/**
 * The unified inbox (SPEC §3.9): everything customers send — email, the shop's contact form, the
 * phone — arriving in the same tickets the rest of the CRM works on. The conversation opens beside
 * the list, so a reply is one box away; anything deeper (assigning, status, notes on the SLA clock)
 * is a click away on the ticket itself.
 */
export default function InboxPage() {
  const lookups = useLookups();
  const [filters, setFilters] = useState<TicketFilters>({ state: "unresolved", needs_reply: true, page: 1 });
  const [search, setSearch] = useState("");
  const [data, setData] = useState<Page<Ticket> | null>(null);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await ticketsApi.list({ ...filters, page_size: PAGE_SIZE }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the inbox");
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load]);

  // Deep links: /inbox?ticket=12 (from a customer or a ticket) opens that thread, ?channel=email the tab.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ticketId = Number(params.get("ticket"));
    const channel = params.get("channel");
    if (channel) setFilters((f) => ({ ...f, channel, page: 1 }));
    if (ticketId > 0) void ticketsApi.get(ticketId).then(setSelected).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (search === (filters.q ?? "")) return;
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search || undefined, page: 1 })), 300);
    return () => clearTimeout(t);
  }, [search, filters.q]);

  const update = (patch: Partial<TicketFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  // A reply can take the ticket off the waiting list, but the thread stays open where it is.
  const refresh = useCallback(() => {
    void load();
    if (selected) void ticketsApi.get(selected.id).then(setSelected).catch(() => undefined);
  }, [load, selected]);

  const channels = [{ value: "", label: "All channels" }, ...lookups.options("ticket_channel").map((v) => ({ value: v.key, label: v.label }))];
  const words = filters.needs_reply ? "waiting on a reply" : "open";
  const describe = data
    ? `${data.total.toLocaleString("en-US")} ${data.total === 1 ? "conversation" : "conversations"} ${words}${filters.channel ? " in this channel" : ""}.`
    : "Customer email, the shop's contact form and the phone in one queue.";

  return (
    <>
      <PageHeader title="Inbox" description={describe} />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Segmented label="Channel" options={channels} value={filters.channel ?? ""} onChange={(channel) => update({ channel: channel || undefined })} />
        <Segmented label="Show" options={SHOW} value={filters.needs_reply ? "waiting" : "all"} onChange={(show) => update({ needs_reply: show === "waiting" ? true : undefined })} />
        <Field label="Search" className="min-w-0 flex-1 sm:max-w-xs">
          {(p) => <Input {...p} type="search" placeholder="Subject or customer" value={search} onChange={(e) => setSearch(e.target.value)} />}
        </Field>
      </div>

      {error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      )}

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <div className="grid gap-4">
          <Panel className="overflow-hidden">
            <InboxList tickets={data?.items ?? null} selected={selected?.id ?? null} onPick={setSelected} />
          </Panel>
          {data && <Pagination page={filters.page ?? 1} pageSize={PAGE_SIZE} total={data.total} onPage={(page) => setFilters((f) => ({ ...f, page }))} />}
        </div>

        {selected ? (
          <div className="grid gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <h2 className="truncate text-base">{selected.subject}</h2>
                <p className="mt-0.5 text-xs text-muted">
                  <span className="num">{selected.number ?? `#${selected.id}`}</span> · {selected.customer_name ?? "No customer"} · updated {timeAgo(selected.updated_at)}
                </p>
              </div>
              <Link href={`/tickets/${selected.id}`} className="shrink-0 text-sm font-medium hover:text-accent-strong hover:underline">
                Open the full ticket
              </Link>
            </div>
            <Conversation ticket={selected} onChanged={refresh} />
          </div>
        ) : (
          <Panel className="px-6 py-16 text-center">
            <p className="text-sm text-muted">Pick a conversation to read it — and reply without leaving the inbox.</p>
          </Panel>
        )}
      </div>
    </>
  );
}
