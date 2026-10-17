"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  describeSummary,
  salesApi,
  STATUS_LABEL,
  STATUSES,
  type Board,
  type Deal,
  type DealFilters,
  type DealStatus,
  type DealView,
  type Pipeline,
  type SalesSummary,
} from "@/modules/sales/api";
import { DealBoard } from "@/modules/sales/DealBoard";
import { DealDialog } from "@/modules/sales/DealDialog";
import { DealList } from "@/modules/sales/DealList";

const PAGE_SIZE = 50;
const MODES = [
  { value: "board", label: "Board" },
  { value: "list", label: "List" },
] as const;
const VIEWS: readonly { value: DealView; label: string }[] = [
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
 * Sales: the pipeline board and the same deals as a list. The board answers "what is moving and where",
 * the list answers "what is closing soon" — filters, search and paging live on the list side.
 */
export default function SalesPage() {
  const { user, can } = useAuth();
  const [mode, setMode] = useState<(typeof MODES)[number]["value"]>("board");
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [pipelineId, setPipelineId] = useState<number | null>(null);
  const [board, setBoard] = useState<Board | null>(null);
  const [filters, setFilters] = useState<DealFilters>({ view: "all", status: "open", page: 1 });
  const [search, setSearch] = useState("");
  const [data, setData] = useState<Page<Deal> | null>(null);
  const [summary, setSummary] = useState<SalesSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Deal | null>(null);
  const [adding, setAdding] = useState(false);

  const loadSummary = useCallback(() => {
    salesApi.summary().then(setSummary).catch(() => setSummary(null));
  }, []);

  useEffect(() => {
    loadSummary();
    salesApi
      .pipelines()
      .then((list) => {
        setPipelines(list);
        setPipelineId((id) => id ?? list.find((p) => p.is_default)?.id ?? list[0]?.id ?? null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't load the pipelines"));
  }, [loadSummary]);

  const loadBoard = useCallback(async () => {
    if (mode !== "board") return;
    if (pipelines.length === 0) return;
    setError(null);
    try {
      setBoard(await salesApi.board(pipelineId ?? undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load the board");
      setBoard(null);
    }
  }, [mode, pipelines.length, pipelineId]);

  const loadList = useCallback(async () => {
    if (mode !== "list") return;
    setError(null);
    try {
      setData(await salesApi.deals({ ...filters, pipeline_id: pipelineId ?? undefined, page_size: PAGE_SIZE }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load deals");
      setData(null);
    }
  }, [mode, filters, pipelineId]);

  useEffect(() => {
    void loadBoard();
  }, [loadBoard]);
  useEffect(() => {
    void loadList();
  }, [loadList]);

  const refresh = useCallback(() => {
    loadSummary();
    void loadBoard();
    void loadList();
  }, [loadSummary, loadBoard, loadList]);

  // Links from the dashboard and a customer's page: /sales?deal=42, /sales?customer_id=7
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = Number(params.get("deal"));
    if (id) salesApi.deal(id).then(setEditing).catch(() => undefined);
    const customerId = Number(params.get("customer_id"));
    if (customerId) {
      setMode("list");
      setFilters((f) => ({ ...f, customer_id: customerId, page: 1 }));
    }
  }, []);

  useEffect(() => {
    if (search === (filters.q ?? "")) return;
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search || undefined, page: 1 })), 300);
    return () => clearTimeout(t);
  }, [search, filters.q]);

  const update = (patch: Partial<DealFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const canCreate = can("sales:edit_own");
  const canMove = (deal: Deal) => can("sales:edit_any") || (can("sales:edit_own") && deal.owner_id === user?.id);
  const noPipeline = pipelines.length === 0;

  return (
    <>
      <PageHeader
        title="Sales"
        description={summary ? describeSummary(summary) : "Leads and deals on a pipeline board."}
        actions={
          canCreate && !noPipeline ? (
            <Button size="sm" onClick={() => setAdding(true)}>
              Add deal
            </Button>
          ) : undefined
        }
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Segmented label="View" options={MODES} value={mode} onChange={(m) => setMode(m)} />
        {pipelines.length > 1 && (
          <Field label="Pipeline" className="w-48">
            {(p) => (
              <Select {...p} value={pipelineId ?? ""} onChange={(e) => setPipelineId(Number(e.target.value))}>
                {pipelines.map((pl) => (
                  <option key={pl.id} value={pl.id}>
                    {pl.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        {mode === "list" && (
          <>
            <Segmented label="Whose deals" options={VIEWS} value={filters.view ?? "all"} onChange={(view) => update({ view })} />
            <Field label="Show" className="w-36">
              {(p) => (
                <Select {...p} value={filters.status} onChange={(e) => update({ status: e.target.value as DealStatus | "all" })}>
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABEL[s]}
                    </option>
                  ))}
                  <option value="all">Everything</option>
                </Select>
              )}
            </Field>
            <Field label="Search" className="min-w-0 flex-1 sm:max-w-xs">
              {(p) => <Input {...p} type="search" placeholder="Deal or customer" value={search} onChange={(e) => setSearch(e.target.value)} />}
            </Field>
          </>
        )}
      </div>

      {filters.customer_id && (
        <p className="mb-4 text-sm text-muted">
          Showing one customer&apos;s deals.{" "}
          <button type="button" className="text-accent-strong underline" onClick={() => update({ customer_id: undefined })}>
            Show everyone
          </button>
        </p>
      )}

      {error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      )}

      {noPipeline ? (
        <Panel className="px-5 py-12 text-center">
          <p className="text-sm text-muted">
            There is no pipeline yet.{" "}
            {can("lookups:manage") ? (
              <Link href="/settings/pipelines" className="text-accent-strong underline">
                Set one up
              </Link>
            ) : (
              "Ask an admin to set one up"
            )}{" "}
            and deals will have stages to move through.
          </p>
        </Panel>
      ) : mode === "board" ? (
        <Panel className="overflow-hidden">
          <DealBoard board={board} canMove={canMove} onEdit={setEditing} onChanged={refresh} />
        </Panel>
      ) : (
        <>
          <Panel className="overflow-hidden">
            <DealList deals={data?.items ?? null} onEdit={setEditing} empty="No deals match." />
          </Panel>
          {data && data.total > PAGE_SIZE && (
            <Pagination className="mt-4" page={filters.page ?? 1} pageSize={PAGE_SIZE} total={data.total} onPage={(page) => setFilters((f) => ({ ...f, page }))} />
          )}
        </>
      )}

      <DealDialog
        open={adding || editing !== null}
        deal={editing}
        pipelines={pipelines}
        onClose={() => {
          setAdding(false);
          setEditing(null);
        }}
        onSaved={refresh}
      />
    </>
  );
}
