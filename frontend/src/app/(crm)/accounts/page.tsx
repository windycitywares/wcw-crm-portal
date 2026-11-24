"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { AccountDialog } from "@/modules/accounts/AccountDialog";
import { accountsApi, type Account, type AccountFilters } from "@/modules/accounts/api";
import { useLookups } from "@/modules/settings/useLookups";

const PAGE_SIZE = 25;
const TYPE_TONE: Record<string, "success" | "warning" | "info" | "accent" | "neutral"> = {
  customer: "success", supplier: "warning", partner: "info", marketplace: "accent",
};

export default function AccountsPage() {
  const { can } = useAuth();
  const router = useRouter();
  const lookups = useLookups();
  const [filters, setFilters] = useState<AccountFilters>({ q: "", type: "", status: "", sort: "name", page: 1 });
  const [search, setSearch] = useState("");
  const [data, setData] = useState<Page<Account> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async (f: AccountFilters) => {
    setLoading(true);
    setError(null);
    try {
      setData(await accountsApi.list({ ...f, page_size: PAGE_SIZE }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load accounts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const type = new URLSearchParams(window.location.search).get("type");
    if (type) setFilters((f) => ({ ...f, type }));
  }, []);
  useEffect(() => { void load(filters); }, [filters, load]);
  useEffect(() => {
    if (search === (filters.q ?? "")) return;
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search, page: 1 })), 300);
    return () => clearTimeout(t);
  }, [search, filters.q]);

  const update = (patch: Partial<AccountFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const typeLabel = (key: string) => lookups.find("account_type", key)?.label ?? key;

  const columns: Column<Account>[] = [
    {
      key: "name", header: "Account",
      cell: (a) => (
        <div className="min-w-0">
          <Link href={`/accounts/${a.id}`} className="font-medium text-ink hover:text-accent-strong hover:underline">{a.name}</Link>
          <div className="truncate text-xs text-muted">{[a.parent_name && `Part of ${a.parent_name}`, a.children_count ? `${a.children_count} sub-account${a.children_count === 1 ? "" : "s"}` : null, a.industry, a.address?.city, a.address?.country].filter(Boolean).join(" · ")}</div>
        </div>
      ),
    },
    { key: "type", header: "Type", cell: (a) => <Badge variant={TYPE_TONE[a.account_type] ?? "neutral"}>{typeLabel(a.account_type)}</Badge> },
    { key: "contacts", header: "People", align: "right", hide: "sm", cell: (a) => a.contacts_count },
    { key: "reach", header: "Email / phone", hide: "lg", cell: (a) => [a.email, a.phone].filter(Boolean).join(" · ") || <span className="text-muted">—</span> },
    { key: "status", header: "Status", hide: "md", cell: (a) => <Badge variant={a.status === "active" ? "success" : "neutral"}>{a.status === "active" ? "Active" : "Inactive"}</Badge> },
  ];

  return (
    <div>
      <PageHeader title="Accounts"
        description="The organisations you deal with — customers' companies, suppliers, partners, marketplaces. People at an account are its contacts."
        actions={can("customers:edit_own") ? <Button size="sm" onClick={() => setAdding(true)}>Add account</Button> : undefined} />
      <Panel className="mb-4">
        <div className="grid grid-cols-[minmax(0,1fr)] items-end gap-3 p-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
          <Field label="Search">
            {(p) => <Input {...p} maxLength={120} type="search" placeholder="Name, industry, website, email or phone" value={search} onChange={(e) => setSearch(e.target.value)} />}
          </Field>
          <Field label="Type">
            {(p) => (
              <Select {...p} value={filters.type ?? ""} onChange={(e) => update({ type: e.target.value })}>
                <option value="">All types</option>
                {lookups.options("account_type").map((v) => <option key={v.key} value={v.key}>{v.label}</option>)}
              </Select>
            )}
          </Field>
          <Field label="Status">
            {(p) => (
              <Select {...p} value={filters.status ?? ""} onChange={(e) => update({ status: e.target.value as AccountFilters["status"] })}>
                <option value="">All</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </Select>
            )}
          </Field>
        </div>
      </Panel>
      {error && <p role="alert" className="mb-3 text-sm text-danger">{error}</p>}
      <div className="relative">
        <DataTable columns={columns} rows={data?.items ?? null} rowKey={(a) => a.id} caption="Accounts" loading={loading}
          empty="No accounts match these filters." />
      </div>
      {data && data.total > PAGE_SIZE && (
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(p) => setFilters((f) => ({ ...f, page: p }))} />
      )}
      <AccountDialog open={adding} account={null} defaultType={filters.type || undefined} onClose={() => setAdding(false)}
        onSaved={(a) => { setAdding(false); router.push(`/accounts/${a.id}`); }} />
    </div>
  );
}
