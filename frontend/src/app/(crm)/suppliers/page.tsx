"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ButtonLink } from "@/components/ui/Button";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { Field, Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel, PanelBody } from "@/components/ui/Panel";
import { Pill } from "@/components/ui/Pill";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { suppliersApi, type Supplier, type SupplierStatus } from "@/modules/suppliers/api";
import { useLookups } from "@/modules/settings/useLookups";

const PAGE_SIZE = 25;

export default function SuppliersPage() {
  const { can } = useAuth();
  const lookups = useLookups();
  const canEdit = can("suppliers:edit");
  const [data, setData] = useState<Page<Supplier> | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [supplierType, setSupplierType] = useState("");
  const [status, setStatus] = useState<"" | SupplierStatus>("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void suppliersApi.list(page, PAGE_SIZE, query || undefined, supplierType || undefined, status || undefined)
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Couldn't load suppliers");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [page, query, supplierType, status]);

  const columns: Column<Supplier>[] = [
    {
      key: "name",
      header: "Supplier",
      cell: (supplier) => (
        <div className="min-w-0">
          <Link href={`/suppliers/${supplier.id}`} className="font-medium text-ink hover:text-accent-strong hover:underline">
            {supplier.name}
          </Link>
          {supplier.website && <div className="truncate text-xs text-muted">{supplier.website}</div>}
        </div>
      ),
    },
    {
      key: "supplier_type",
      header: "Type",
      cell: (supplier) => lookups.find("supplier_type", supplier.supplier_type)?.label ?? supplier.supplier_type,
      hide: "sm",
    },
    {
      key: "status",
      header: "Status",
      cell: (supplier) => <Pill tone={supplier.status === "active" ? "success" : "neutral"}>{supplier.status}</Pill>,
    },
    {
      key: "contact",
      header: "Primary contact",
      cell: (supplier) => {
        const contact = supplier.contacts.find((item) => item.is_primary) ?? supplier.contacts[0];
        return contact ? (
          <div className="min-w-0">
            <div className="truncate">{contact.name}</div>
            {contact.email && <div className="truncate text-xs text-muted">{contact.email}</div>}
          </div>
        ) : <span className="text-muted">—</span>;
      },
      hide: "md",
    },
    {
      key: "lead_time",
      header: "Lead time",
      align: "right",
      cell: (supplier) => supplier.lead_time_days == null ? <span className="text-muted">—</span> : `${supplier.lead_time_days} days`,
      hide: "lg",
    },
  ];

  return (
    <>
      <PageHeader
        title="Suppliers"
        description={data ? `${data.total.toLocaleString()} suppliers` : "Supplier directory and purchasing details."}
        actions={canEdit ? <ButtonLink href="/suppliers/new" size="sm">Add supplier</ButtonLink> : undefined}
      />

      {error && <div role="alert" className="mb-4 rounded border border-danger/50 bg-danger/8 px-3 py-2 text-sm text-danger">{error}</div>}

      <Panel className="mb-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Search suppliers">
            {(p) => <Input {...p} type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, type, or website" />}
          </Field>
          <Field label="Supplier type">
            {(p) => <Select {...p} value={supplierType} onChange={(e) => { setSupplierType(e.target.value); setPage(1); }}>
              <option value="">All types</option>
              {lookups.values("supplier_type").map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
            </Select>}
          </Field>
          <Field label="Status">
            {(p) => <Select {...p} value={status} onChange={(e) => { setStatus(e.target.value as "" | SupplierStatus); setPage(1); }}>
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </Select>}
          </Field>
        </div>
      </Panel>

      <Panel>
        <DataTable columns={columns} rows={loading && !data ? null : data?.items ?? null} rowKey={(supplier) => supplier.id} caption="Suppliers" empty="No suppliers found." />
        {data && <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
        {loading && data && <PanelBody className="py-2 text-xs text-muted">Updating results…</PanelBody>}
      </Panel>
    </>
  );
}