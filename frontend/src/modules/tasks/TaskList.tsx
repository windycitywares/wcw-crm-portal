"use client";

import Link from "next/link";
import { useState } from "react";
import { ColorTag } from "@/components/ui/ColorTag";
import { Pill } from "@/components/ui/Pill";
import { useToast } from "@/components/ui/Toast";
import { useDirectory } from "@/modules/records/useDirectory";
import { useLookups } from "@/modules/settings/useLookups";
import { formatDue, recordHref, tasksApi, type Task } from "./api";

/** Tasks as a checklist: tick to finish (untick to reopen), click the title to edit. */
export function TaskList({
  tasks,
  onEdit,
  onChanged,
  showOwner = false,
  showRelated = true,
  empty = "Nothing here.",
}: {
  tasks: Task[] | null;
  onEdit: (t: Task) => void;
  onChanged: () => void;
  showOwner?: boolean;
  showRelated?: boolean;
  empty?: string;
}) {
  const toast = useToast();
  const lookups = useLookups();
  const { name } = useDirectory();
  const [busy, setBusy] = useState<number | null>(null);

  async function toggle(t: Task) {
    setBusy(t.id);
    try {
      const done = t.status !== "done";
      await tasksApi.update(t.id, { status: done ? "done" : "open" });
      toast.push({
        title: done ? "Task done" : "Task reopened",
        description: done && t.recurrence ? "The next one has been added." : t.title,
      });
      onChanged();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't update the task", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(null);
    }
  }

  if (tasks === null) return <p className="px-5 py-4 text-sm text-muted">Loading…</p>;
  if (tasks.length === 0) return <p className="px-5 py-4 text-sm text-muted">{empty}</p>;

  return (
    <ul className="divide-y divide-line">
      {tasks.map((t) => {
        const type = lookups.find("task_type", t.task_type);
        const due = formatDue(t);
        const href = recordHref(t.related_type, t.related_id);
        const done = t.status === "done";
        return (
          <li key={t.id} className="flex items-start gap-3 px-5 py-3">
            <input
              type="checkbox"
              aria-label={done ? `Reopen “${t.title}”` : `Mark “${t.title}” done`}
              className="mt-1 size-4 shrink-0 accent-[var(--color-accent)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              checked={done}
              disabled={busy === t.id || t.status === "cancelled"}
              onChange={() => void toggle(t)}
            />
            <div className="min-w-0 flex-1">
              <button
                type="button"
                onClick={() => onEdit(t)}
                className={`text-left font-medium hover:text-accent-strong hover:underline focus-visible:outline-2 focus-visible:outline-accent ${done || t.status === "cancelled" ? "text-muted line-through" : ""}`}
              >
                {t.title}
              </button>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                {due && <span className={t.is_overdue ? "font-medium text-danger" : undefined}>{t.is_overdue ? `Overdue · ${due}` : due}</span>}
                {t.recurrence && <span>Repeats {t.recurrence}</span>}
                {type && <ColorTag color={type.color}>{type.label}</ColorTag>}
                {t.priority === "high" && <Pill tone="warning">High</Pill>}
                {t.status === "cancelled" && <Pill>Cancelled</Pill>}
                {showRelated && t.related_label && (href ? (
                  <Link href={href} className="text-accent-strong underline">
                    {t.related_label}
                  </Link>
                ) : (
                  <span>{t.related_label}</span>
                ))}
                {showOwner && <span>{name(t.owner_id)}</span>}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
