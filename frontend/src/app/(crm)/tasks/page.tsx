"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Panel } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import type { Page } from "@/lib/types";
import { cn } from "@/lib/utils";
import { tasksApi, type Task, type TaskFilters } from "@/modules/tasks/api";
import { TaskDialog } from "@/modules/tasks/TaskDialog";
import { TaskList } from "@/modules/tasks/TaskList";

const PAGE_SIZE = 50;
const VIEWS = [
  { value: "mine", label: "My tasks" },
  { value: "team", label: "Team" },
  { value: "created", label: "I created" },
] as const;
const DUES = [
  { value: "any", label: "All" },
  { value: "overdue", label: "Overdue" },
  { value: "today", label: "Today" },
  { value: "week", label: "Next 7 days" },
  { value: "none", label: "No date" },
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

export default function TasksPage() {
  const { can } = useAuth();
  const [filters, setFilters] = useState<TaskFilters>({ view: "mine", status: "open", due: "any", page: 1 });
  const [search, setSearch] = useState("");
  const [data, setData] = useState<Page<Task> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<{ open: number; overdue: number; due_today: number } | null>(null);
  const [editing, setEditing] = useState<Task | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await tasksApi.list({ ...filters, page_size: PAGE_SIZE }));
      setSummary(await tasksApi.summary());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load tasks");
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load]);

  // Links from reminder emails: /tasks?task=42 opens that task.
  useEffect(() => {
    const id = Number(new URLSearchParams(window.location.search).get("task"));
    if (id) tasksApi.get(id).then(setEditing).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (search === (filters.q ?? "")) return;
    const t = setTimeout(() => setFilters((f) => ({ ...f, q: search || undefined, page: 1 })), 300);
    return () => clearTimeout(t);
  }, [search, filters.q]);

  const update = (patch: Partial<TaskFilters>) => setFilters((f) => ({ ...f, ...patch, page: 1 }));
  const describe = summary
    ? `${summary.open} open${summary.overdue ? `, ${summary.overdue} overdue` : ""}${summary.due_today ? `, ${summary.due_today} due today` : ""} for you.`
    : "Calls, follow-ups and to-dos.";

  return (
    <>
      <PageHeader
        title="Tasks"
        description={describe}
        actions={
          can("tasks:edit_own") ? (
            <Button size="sm" onClick={() => setAdding(true)}>
              Add task
            </Button>
          ) : undefined
        }
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Segmented label="Whose tasks" options={VIEWS} value={filters.view ?? "mine"} onChange={(view) => update({ view })} />
        <Segmented label="Due" options={DUES} value={filters.due ?? "any"} onChange={(due) => update({ due })} />
        <Field label="Show" className="w-36">
          {(p) => (
            <Select {...p} value={filters.status} onChange={(e) => update({ status: e.target.value as TaskFilters["status"] })}>
              <option value="open">To do</option>
              <option value="done">Done</option>
              <option value="cancelled">Cancelled</option>
              <option value="all">Everything</option>
            </Select>
          )}
        </Field>
        <Field label="Search" className="min-w-0 flex-1 sm:max-w-xs">
          {(p) => <Input {...p} type="search" placeholder="Title or details" value={search} onChange={(e) => setSearch(e.target.value)} />}
        </Field>
      </div>

      {error && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      )}

      <Panel>
        <TaskList
          tasks={data?.items ?? null}
          onEdit={setEditing}
          onChanged={() => void load()}
          showOwner={filters.view !== "mine"}
          empty={filters.status === "open" ? "Nothing to do here. Nice." : "No tasks match."}
        />
      </Panel>
      {data && data.total > PAGE_SIZE && (
        <Pagination className="mt-4" page={filters.page ?? 1} pageSize={PAGE_SIZE} total={data.total} onPage={(page) => setFilters((f) => ({ ...f, page }))} />
      )}

      <TaskDialog open={adding || editing !== null} task={editing} onClose={() => {
          setAdding(false);
          setEditing(null);
        }} onSaved={() => void load()} />
    </>
  );
}
