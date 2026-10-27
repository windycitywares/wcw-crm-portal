"use client";

import Link from "next/link";
import { Button, ButtonLink } from "@/components/ui/Button";
import { ConfirmationDialog } from "@/components/ui/ConfirmationDialog";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { LiveUpdatesBar } from "@/components/ui/LiveUpdatesBar";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { Badge } from "@/components/ui/Badge";
import { Avatar } from "@/components/ui/Avatar";
import { useToast } from "@/components/ui/Toast";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { customerFilesApi, customersApi, formatMoney, SORTS, STATUS_LABEL, type Customer, type CustomerFilters } from "@/modules/customers/api";
import { useDirectory } from "@/modules/records/useDirectory";
import { tagsApi, type Tag } from "@/modules/settings/api";
import { useLookups } from "@/modules/settings/useLookups";

const PAGE_SIZE = 25;
const STORE_KEY = "crm.customers.filters";
const BLANK: CustomerFilters = { q: "", type: "", status: "", owner: "any", tag_id: "", has_orders: "", deleted: false, sort: "-updated", page: 1 };

function loadFilters(): CustomerFilters {
  // The top bar's search (/customers?q=…) starts a fresh search.
  const q = new URLSearchParams(window.location.search).get("q");
  if (q) return { ...BLANK, q };
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORE_KEY) ?? "null") as CustomerFilters | null;
    return saved ? { ...BLANK, ...saved } : BLANK;
  } catch {
    return BLANK;
  }
}

export default function CustomersPage() {
  const { can } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const [exporting, setExporting] = useState<"csv" | "xlsx" | null>(null);
  const { name } = useDirectory();
  const lookups = useLookups();
  const [filters, setFilters] = useState<CustomerFilters>(BLANK);
  const [search, setSearch] = useState("");
  const [data, setData] = useState<Page<Customer> | null>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null);

  useEffect(() => {
    const f = loadFilters();
    setFilters(f);
    setSearch(f.q ?? "");
    setReady(true);
    tagsApi.search().then(setTags).catch(() => setTags([]));
  }, []);

  const load = useCallback(async (f: CustomerFilters) => {
    setLoading(true);
    setError(null);
    try {
      setData(await customersApi.list({ ...f, page_size: PAGE_SIZE }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load customers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify(filters));
    } catch {
      /* private mode: filters just aren't remembered */
    }
    void load(filters);
  }, [filters, ready, load]);

  // Search as you type, after a short pause.
  useEffect(() => {
    if (!ready || search === filters.q) return;
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search, page: 1 })), 300);
    return () => clearTimeout(t);
  }, [search, ready, filters.q]);

  const update = (patch: Partial<CustomerFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  const handleEdit = useCallback((c: Customer) => {
    router.push(`/customers/${c.id}/edit`);
  }, [router]);

  const handleDelete = useCallback((c: Customer) => {
    setDeleteTarget({ id: c.id, name: c.display_name });
  }, []);

  const handleDeleteConfirmed = useCallback(async () => {
    if (!deleteTarget) return;
    setDeletingId(deleteTarget.id);
    try {
      await customersApi.remove(deleteTarget.id);
      toast.push({ title: "Customer deleted", description: `${deleteTarget.name} was removed.` });
      void load(filters);
    } catch (e) {
      toast.push({ tone: "danger", title: "Couldn't delete", description: e instanceof Error ? e.message : undefined });
    } finally {
      setDeletingId(null);
      setDeleteTarget(null);
    }
  }, [deleteTarget, load, toast]);

  const filtered = JSON.stringify({ ...filters, page: 1 }) !== JSON.stringify({ ...BLANK, page: 1 });

  const columns: Column<Customer>[] = [
    {
      key: "name",
      header: "Customer",
      cell: (c) => (
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Avatar name={c.display_name} size="sm" />
            <Link href={`/customers/${c.id}`} className="font-medium text-ink hover:text-accent-strong hover:underline">
              {c.display_name}
            </Link>
          </div>
          {c.company && c.display_name !== c.company && <div className="truncate text-xs text-muted">{c.company}</div>}
          {c.email && <div className="truncate text-xs text-muted">{c.email}</div>}
        </div>
      ),
    },
    {
      key: "type",
      header: "Type",
      hide: "md",
      cell: (c) => {
        const t = lookups.find("customer_type", c.customer_type);
        return t ? <Badge variant="accent">{t.label}</Badge> : <span className="text-muted">—</span>;
      },
    },
    {
      key: "status",
      header: "Status",
      hide: "sm",
      cell: (c) =>
        c.deleted_at ? (
          <Badge variant="danger">Deleted</Badge>
        ) : (
          <Badge variant={c.status === "active" ? "success" : c.status === "blocked" ? "danger" : "neutral"}>
            {STATUS_LABEL[c.status]}
          </Badge>
        ),
    },
    { key: "owner", header: "Owner", hide: "lg", cell: (c) => (c.owner_id ? name(c.owner_id) : <span className="text-muted">—</span>) },
    { key: "orders", header: "Orders", align: "right", hide: "md", cell: (c) => c.orders_count },
    { key: "spent", header: "Spent", align: "right", hide: "sm", cell: (c) => formatMoney(c.total_spent) },
    { key: "last", header: "Last order", hide: "lg", cell: (c) => (c.last_order_at ? formatDate(c.last_order_at) : <span className="text-muted">—</span>) },
  ];

  return (
    <>
      <PageHeader
        title="Customers"
        description={data ? `${data.total.toLocaleString()} ${data.total === 1 ? "customer" : "customers"}${filtered ? " match" : ""}` : "Everyone who buys from or talks to Windy City Wares."}
        actions={
          <>
            {can("data:export") && (
              <>
                {(["csv", "xlsx"] as const).map((format) => (
                  <Button
                    key={format}
                    variant="secondary"
                    size="sm"
                    disabled={exporting !== null}
                    onClick={() => {
                      setExporting(format);
                      customerFilesApi
                        .export(filters, format)
                        .then(() => toast.push({ title: "Customers exported", description: "The file is in your downloads." }))
                        .catch((err) => toast.push({ tone: "danger", title: "Couldn't export", description: err instanceof Error ? err.message : undefined }))
                        .finally(() => setExporting(null));
                    }}
                  >
                    {exporting === format ? "Exporting…" : format === "csv" ? "Export CSV" : "Export Excel"}
                  </Button>
                ))}
                <ButtonLink href="/customers/import" variant="secondary" size="sm">
                  Import
                </ButtonLink>
              </>
            )}
            {(can("customers:edit_own") || can("customers:edit_any")) && (
              <ButtonLink href="/customers/new" size="sm">
                Add customer
              </ButtonLink>
            )}
          </>
        }
      />
      <LiveUpdatesBar types={["customer"]} noun="customer" onRefresh={() => void load(filters)} />

      <Panel className="mb-4 p-4">
        <form role="search" onSubmit={(e) => e.preventDefault()} className="grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Search" className="sm:col-span-2">
            {(p) => <Input {...p} type="search" placeholder="Name, company, email or phone" value={search} onChange={(e) => setSearch(e.target.value)} />}
          </Field>
          <Field label="Type">
            {(p) => (
              <Select {...p} value={filters.type} onChange={(e) => update({ type: e.target.value })}>
                <option value="">All types</option>
                {lookups.values("customer_type").map((v) => (
                  <option key={v.key} value={v.key}>
                    {v.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Status">
            {(p) => (
              <Select {...p} value={filters.deleted ? "deleted" : filters.status} onChange={(e) => (e.target.value === "deleted" ? update({ status: "", deleted: true }) : update({ status: e.target.value, deleted: false }))}>
                <option value="">Any status</option>
                {Object.entries(STATUS_LABEL).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
                {can("customers:edit_any") && <option value="deleted">Deleted</option>}
              </Select>
            )}
          </Field>
          <Field label="Owner">
            {(p) => (
              <Select {...p} value={filters.owner} onChange={(e) => update({ owner: e.target.value as "me" | "any" })}>
                <option value="any">Anyone</option>
                <option value="me">Mine</option>
              </Select>
            )}
          </Field>
          <Field label="Tag">
            {(p) => (
              <Select {...p} value={String(filters.tag_id ?? "")} onChange={(e) => update({ tag_id: e.target.value ? Number(e.target.value) : "" })}>
                <option value="">Any tag</option>
                {tags.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Orders">
            {(p) => (
              <Select {...p} value={filters.has_orders} onChange={(e) => update({ has_orders: e.target.value as CustomerFilters["has_orders"] })}>
                <option value="">Any</option>
                <option value="true">Has ordered</option>
                <option value="false">No orders yet</option>
              </Select>
            )}
          </Field>
          <Field label="Sort by">
            {(p) => (
              <Select {...p} value={filters.sort} onChange={(e) => update({ sort: e.target.value })}>
                {SORTS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </form>
        {filtered && (
          <button
            type="button"
            className="mt-3 text-sm text-accent-strong underline focus-visible:outline-2 focus-visible:outline-accent"
            onClick={() => {
              setSearch("");
              setFilters(BLANK);
            }}
          >
            Clear filters
          </button>
        )}
      </Panel>

      {error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      )}

      <Panel>
        <div className="relative overflow-x-auto">
          <DataTable
            caption="Customers"
            columns={columns}
            rows={data?.items ?? null}
            rowKey={(c) => c.id}
            loading={loading}
            onEdit={handleEdit}
            onDelete={handleDelete}
            empty={filtered ? "No customers match these filters." : "No customers yet. Add the first one, or connect the shop to bring them in."}
          />
        </div>
      </Panel>
      {data && data.total > PAGE_SIZE && (
        <Pagination className="mt-4" page={filters.page ?? 1} pageSize={PAGE_SIZE} total={data.total} onPage={(page) => setFilters((f) => ({ ...f, page }))} />
      )}

      <ConfirmationDialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete customer"
        message={`Delete "${deleteTarget?.name}"? This can't be undone.`}
        onConfirm={handleDeleteConfirmed}
      />
    </>
  );
}
