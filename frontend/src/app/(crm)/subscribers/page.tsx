"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { LiveUpdatesBar } from "@/components/ui/LiveUpdatesBar";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { cn, formatDate } from "@/lib/utils";
import {
  SOURCE_LABEL, subscribersApi, type Contact, type SubscriberFilters, type SubscriberPage, type SubscriberStatus,
} from "@/modules/contacts/api";

const PAGE_SIZE = 25;
const BLANK: SubscriberFilters = { q: "", status: "", source: "", sort: "-joined", page: 1 };

const TABS: { key: "" | SubscriberStatus; label: string; count: keyof SubscriberPage["counts"] }[] = [
  { key: "subscribed", label: "Subscribed", count: "subscribed" },
  { key: "paused", label: "Paused", count: "paused" },
  { key: "unsubscribed", label: "Unsubscribed", count: "unsubscribed" },
  { key: "", label: "Everyone", count: "all" },
];
const STATUS_BADGE = { subscribed: "success", paused: "warning", unsubscribed: "neutral" } as const;
const STATUS_LABEL = { subscribed: "Subscribed", paused: "Paused", unsubscribed: "Unsubscribed" } as const;
const sourceLabel = (s: string | null) => (s ? SOURCE_LABEL[s] ?? s : "—");

export default function SubscribersPage() {
  const { can } = useAuth();
  const toast = useToast();
  const canEdit = can("customers:edit_own");
  const [filters, setFilters] = useState<SubscriberFilters>({ ...BLANK, status: "subscribed" });
  const [search, setSearch] = useState("");
  const [data, setData] = useState<SubscriberPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<Contact | null>(null);

  const load = useCallback(async (f: SubscriberFilters) => {
    setLoading(true);
    setError(null);
    try {
      setData(await subscribersApi.list({ ...f, page_size: PAGE_SIZE }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load subscribers");
    } finally {
      setLoading(false);
    }
  }, []);

  // Links from the bell: /subscribers?q=…
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("q");
    if (q) {
      setSearch(q);
      setFilters((f) => ({ ...f, q, status: "", page: 1 }));
    }
  }, []);

  useEffect(() => {
    if (!ready) { setReady(true); return; }
    void load(filters);
  }, [filters, ready, load]);

  useEffect(() => {
    if (!ready || search === (filters.q ?? "")) return;
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search, page: 1 })), 300);
    return () => clearTimeout(t);
  }, [search, ready, filters.q]);

  const update = (patch: Partial<SubscriberFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  const act = async (c: Contact, action: "pause" | "resume" | "unsubscribe" | "resubscribe", done: string) => {
    setBusy(c.id);
    try {
      await subscribersApi.act(c.id, action);
      toast.push({ title: done, description: c.email ?? undefined });
      void load(filters);
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't update", description: e instanceof Error ? e.message : undefined });
    } finally {
      setBusy(null);
    }
  };

  const remove = async () => {
    if (!removing) return;
    try {
      await subscribersApi.remove(removing.id);
      toast.push({ title: "Removed from the list", description: `${removing.email ?? removing.display_name} stays in Contacts.` });
      void load(filters);
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't remove", description: e instanceof Error ? e.message : undefined });
    } finally {
      setRemoving(null);
    }
  };

  const exportCsv = () => {
    setExporting(true);
    subscribersApi
      .export(filters)
      .then(() => toast.push({ title: "Subscribers exported", description: "The file is in your downloads." }))
      .catch((e) => toast.push({ tone: "danger", title: "Couldn't export", description: e instanceof Error ? e.message : undefined }))
      .finally(() => setExporting(false));
  };

  const columns: Column<Contact>[] = [
    {
      key: "email",
      header: "Email",
      sort: "email",
      cell: (c) => (
        <div className="flex min-w-0 items-center gap-2">
          <Avatar name={c.display_name} size="sm" />
          <div className="min-w-0">
            <Link href={`/contacts?q=${encodeURIComponent(c.email ?? c.display_name)}`} className="block truncate font-medium text-ink hover:text-accent-strong hover:underline">
              {c.email ?? c.display_name}
            </Link>
            {c.full_name && <div className="truncate text-xs text-muted">{c.full_name}</div>}
            {c.customer_id && <Badge variant="accent" className="mt-0.5">Customer</Badge>}
          </div>
        </div>
      ),
    },
    { key: "source", header: "Source", hide: "md", cell: (c) => sourceLabel(c.subscribe_source) },
    { key: "language", header: "Language", hide: "lg", cell: (c) => (c.language ? c.language.toUpperCase() : <span className="text-muted">—</span>) },
    { key: "joined", header: "Joined", sort: "joined", hide: "sm", cell: (c) => formatDate(c.subscribed_at) },
    {
      key: "status",
      header: "Status",
      cell: (c) => {
        const s = c.subscription_status;
        return s ? <Badge variant={STATUS_BADGE[s]}>{STATUS_LABEL[s]}</Badge> : <span className="text-muted">—</span>;
      },
    },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (c) => {
        if (!canEdit) return null;
        const s = c.subscription_status;
        const name = c.email ?? c.display_name;
        const disabled = busy === c.id;
        return (
          <div className="flex flex-wrap justify-end gap-1.5">
            {s === "subscribed" && (
              <Button size="sm" variant="secondary" disabled={disabled} aria-label={`Pause ${name}`} onClick={() => void act(c, "pause", "Subscriber paused")}>Pause</Button>
            )}
            {s === "paused" && (
              <Button size="sm" variant="secondary" disabled={disabled} aria-label={`Resume ${name}`} onClick={() => void act(c, "resume", "Subscriber resumed")}>Resume</Button>
            )}
            {s === "unsubscribed" ? (
              <Button size="sm" variant="secondary" disabled={disabled} aria-label={`Resubscribe ${name}`} onClick={() => void act(c, "resubscribe", "Subscriber resubscribed")}>Resubscribe</Button>
            ) : (
              <Button size="sm" variant="secondary" disabled={disabled} aria-label={`Unsubscribe ${name}`} onClick={() => void act(c, "unsubscribe", "Subscriber unsubscribed")}>Unsubscribe</Button>
            )}
            <Button size="sm" variant="ghost" disabled={disabled} aria-label={`Remove ${name} from the list`} onClick={() => setRemoving(c)}>Remove</Button>
          </div>
        );
      },
    },
  ];

  const sortState = { key: filters.sort === "email" ? "email" : "joined", dir: filters.sort === "joined" || filters.sort === "email" ? ("asc" as const) : ("desc" as const) };
  const onSort = (key: string) =>
    update({ sort: key === "email" ? (filters.sort === "email" ? "-joined" : "email") : filters.sort === "-joined" ? "joined" : "-joined" });

  return (
    <div>
      <PageHeader
        title="Subscribers"
        description="Everyone who joined the newsletter from the shop's site, at checkout or in their account. A subscriber is a contact, so someone who is also a customer is still one person."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" disabled={exporting} onClick={exportCsv}>{exporting ? "Exporting…" : "Export CSV"}</Button>
            {canEdit && <Button size="sm" onClick={() => setAdding(true)}>Add subscriber</Button>}
          </div>
        }
      />
      <LiveUpdatesBar types={["contact"]} noun="subscriber change" onRefresh={() => void load(filters)} />

      <div role="group" aria-label="Status" className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {TABS.map((t) => {
          const active = (filters.status ?? "") === t.key;
          return (
            <button
              key={t.label}
              type="button"
              aria-pressed={active}
              onClick={() => update({ status: t.key })}
              className={cn(
                "rounded-[var(--radius-card)] bg-surface p-4 text-left shadow-[var(--shadow-card)] transition-colors focus-visible:outline-2 focus-visible:outline-accent",
                active ? "ring-2 ring-accent" : "hover:bg-sand",
              )}
            >
              <span className="font-admin block text-sm font-semibold text-muted">{t.label}</span>
              <span className="font-admin mt-1 block text-2xl font-bold text-ink">{data ? data.counts[t.count].toLocaleString() : "—"}</span>
            </button>
          );
        })}
      </div>

      <Panel className="mb-4">
        <div className="flex flex-wrap items-end gap-3 p-4">
          <Field label="Search subscribers" className="min-w-0 flex-1">
            {(p) => <Input {...p} type="search" placeholder="Email or name" value={search} onChange={(e) => setSearch(e.target.value)} />}
          </Field>
          <Field label="Source">
            {(p) => (
              <Select {...p} value={filters.source ?? ""} onChange={(e) => update({ source: e.target.value })}>
                <option value="">All sources</option>
                {(data?.sources ?? []).map((s) => <option key={s} value={s}>{sourceLabel(s)}</option>)}
              </Select>
            )}
          </Field>
        </div>
      </Panel>

      {error && <p className="mb-3 text-sm text-danger">{error}</p>}
      <DataTable
        columns={columns}
        rows={data?.items ?? null}
        rowKey={(c) => c.id}
        caption="Newsletter subscribers"
        loading={loading}
        sort={sortState}
        onSort={onSort}
        empty="No subscribers match these filters."
      />
      {data && data.total > PAGE_SIZE && (
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(p) => setFilters((f) => ({ ...f, page: p }))} />
      )}
      <p className="mt-4 max-w-3xl text-sm text-muted">
        People can leave with the link in every email. Pause someone to leave them out of campaigns for a while without taking them off the
        list; resume whenever you like. Removing someone takes them off the list but keeps them in Contacts.
      </p>

      <AddSubscriberDialog open={adding} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); void load(filters); }} />
      <ConfirmationDialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title="Remove from the list"
        message={`Take ${removing?.email ?? removing?.display_name ?? "this person"} off the newsletter list? They stay in Contacts.`}
        confirmLabel="Remove from list"
        onConfirm={remove}
      />
    </div>
  );
}

function AddSubscriberDialog({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) { setEmail(""); setFirst(""); setLast(""); }
  }, [open]);

  const submit = async () => {
    if (!email.trim()) { toast.push({ tone: "danger", title: "Enter an email address" }); return; }
    setSaving(true);
    try {
      await subscribersApi.add({ email: email.trim(), first_name: first || null, last_name: last || null });
      toast.push({ title: "Subscriber added", description: email.trim() });
      onSaved();
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't add", description: e instanceof Error ? e.message : undefined });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add subscriber"
      description="Someone who agreed to hear from you. If they are already in Contacts, they are added to the list there."
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={() => void submit()} disabled={saving}>{saving ? "Adding…" : "Add subscriber"}</Button>
        </>
      }
    >
      <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <Field label="Email">{(p) => <Input {...p} type="email" autoComplete="off" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="First name">{(p) => <Input {...p} value={first} onChange={(e) => setFirst(e.target.value)} />}</Field>
          <Field label="Last name">{(p) => <Input {...p} value={last} onChange={(e) => setLast(e.target.value)} />}</Field>
        </div>
      </form>
    </Modal>
  );
}
