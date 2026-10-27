"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { LiveUpdatesBar } from "@/components/ui/LiveUpdatesBar";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  describeSummary,
  leadsApi,
  STATUS_LABEL,
  STATUSES,
  type Lead,
  type LeadFilters,
  type LeadOpenStatus,
  type LeadStatus,
  type LeadSummary,
  type LeadView,
} from "@/modules/leads/api";
import { LeadConvertDialog } from "@/modules/leads/LeadConvertDialog";
import { LeadDialog } from "@/modules/leads/LeadDialog";
import { LeadList } from "@/modules/leads/LeadList";
import { salesApi, type Pipeline } from "@/modules/sales/api";
import { useLookups } from "@/modules/settings/useLookups";

const PAGE_SIZE = 50;
const VIEWS: readonly { value: LeadView; label: string }[] = [
  { value: "all", label: "Everyone" },
  { value: "mine", label: "Mine" },
  { value: "unassigned", label: "Unassigned" },
];

function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: readonly { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
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

/**
 * Leads: the funnel before a customer. The tabs are the statuses with how many sit in each, so the page
 * answers "what is new and who is working it" at a glance. Converting is the one action that leaves the
 * page — it makes the customer and their first deal.
 */
export default function LeadsPage() {
  const { user, can } = useAuth();
  const lookups = useLookups();
  const toast = useToast();
  const [filters, setFilters] = useState<LeadFilters>({ view: "all", status: "all", page: 1 });
  const [search, setSearch] = useState("");
  const [data, setData] = useState<Page<Lead> | null>(null);
  const [summary, setSummary] = useState<LeadSummary | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Lead | null>(null);
  const [converting, setConverting] = useState<Lead | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await leadsApi.list({ ...filters, page_size: PAGE_SIZE }));
      setSummary(await leadsApi.summary());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load leads");
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    salesApi
      .pipelines()
      .then(setPipelines)
      .catch(() => setPipelines([]));
  }, []);

  // Deep links: /leads?status=new&view=mine (the dashboard card links here).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const patch: Partial<LeadFilters> = {};
    const status = params.get("status");
    if (status && STATUSES.includes(status as LeadStatus)) patch.status = status as LeadStatus;
    const view = params.get("view");
    if (view === "mine" || view === "unassigned" || view === "all") patch.view = view;
    const source = params.get("source");
    if (source) patch.source = source;
    if (Object.keys(patch).length > 0) setFilters((f) => ({ ...f, ...patch, page: 1 }));
  }, []);

  useEffect(() => {
    if (search === (filters.q ?? "")) return;
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search || undefined, page: 1 })), 300);
    return () => clearTimeout(t);
  }, [search, filters.q]);

  const update = (patch: Partial<LeadFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));

  const count = (status: LeadStatus) => (summary ? String(summary[status]) : "");
  const tabs: { value: LeadStatus | "all"; label: string }[] = [
    { value: "all", label: summary ? `All ${summary.total}` : "All" },
    ...STATUSES.map((s) => ({ value: s, label: summary ? `${STATUS_LABEL[s]} ${count(s)}` : STATUS_LABEL[s] })),
  ];

  const canEdit = (lead: Lead) => can("sales:edit_any") || (can("sales:edit_own") && lead.owner_id === user?.id);

  async function changeStatus(lead: Lead, status: LeadOpenStatus) {
    try {
      await leadsApi.update(lead.id, { status });
      toast.push({ title: `${lead.display_name} is now ${STATUS_LABEL[status].toLowerCase()}` });
      void load();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't change the status", description: err instanceof Error ? err.message : undefined });
    }
  }

  const empty =
    filters.status === "new"
      ? "No new leads. Nice."
      : filters.status === "converted"
        ? "Nothing has been converted yet."
        : "No leads match.";

  return (
    <>
      <PageHeader
        title="Leads"
        description={summary ? describeSummary(summary) : "People who might become customers."}
        actions={
          can("sales:edit_own") ? (
            <Button size="sm" onClick={() => setAdding(true)}>
              Add lead
            </Button>
          ) : undefined
        }
      />
      <LiveUpdatesBar types={["lead"]} noun="lead" onRefresh={() => void load()} />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Segmented label="Status" options={tabs} value={filters.status ?? "all"} onChange={(status) => update({ status })} />
        <Segmented label="Whose leads" options={VIEWS} value={filters.view ?? "all"} onChange={(view) => update({ view })} />
        <Field label="Source" className="w-44">
          {(p) => (
            <Select {...p} value={filters.source ?? ""} onChange={(e) => update({ source: e.target.value || undefined })}>
              <option value="">Any source</option>
              {lookups.options("lead_source", filters.source).map((v) => (
                <option key={v.key} value={v.key}>
                  {v.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Search" className="min-w-0 flex-1 sm:max-w-xs">
          {(p) => <Input {...p} type="search" placeholder="Name, company, email or phone" value={search} onChange={(e) => setSearch(e.target.value)} />}
        </Field>
      </div>

      {error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      )}

      <Panel className="overflow-hidden">
        <LeadList
          leads={data?.items ?? null}
          canEdit={canEdit}
          empty={empty}
          onEdit={setEditing}
          onConvert={can("sales:edit_own") ? setConverting : undefined}
          onStatusChange={(lead, status) => void changeStatus(lead, status)}
        />
      </Panel>
      {data && data.total > PAGE_SIZE && (
        <Pagination className="mt-4" page={filters.page ?? 1} pageSize={PAGE_SIZE} total={data.total} onPage={(page) => setFilters((f) => ({ ...f, page }))} />
      )}

      <LeadDialog
        open={adding || editing !== null}
        lead={editing}
        onClose={() => {
          setAdding(false);
          setEditing(null);
        }}
        onSaved={() => void load()}
        onConvert={setConverting}
      />
      <LeadConvertDialog
        open={converting !== null}
        lead={converting}
        pipelines={pipelines}
        onClose={() => setConverting(null)}
        onConverted={() => void load()}
      />
    </>
  );
}
