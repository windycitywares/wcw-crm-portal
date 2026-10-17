"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { tasksApi, type Task } from "./api";
import { TaskDialog } from "./TaskDialog";
import { TaskList } from "./TaskList";

/** Dashboard: the signed-in user's next open tasks. */
export function MyTasksPanel() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [summary, setSummary] = useState<{ open: number; overdue: number; due_today: number } | null>(null);
  const [editing, setEditing] = useState<Task | null>(null);

  const load = useCallback(() => {
    tasksApi.list({ view: "mine", status: "open", page_size: 6 }).then((p) => setTasks(p.items)).catch(() => setTasks([]));
    tasksApi.summary().then(setSummary).catch(() => setSummary(null));
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  return (
    <Panel>
      <PanelHeader
        title="Your tasks"
        description={summary ? `${summary.open} open · ${summary.overdue} overdue · ${summary.due_today} due today` : undefined}
        actions={
          <Link href="/tasks" className="text-sm text-accent-strong underline">
            All tasks
          </Link>
        }
      />
      <TaskList tasks={tasks} onEdit={setEditing} onChanged={load} empty="Nothing on your list." />
      <TaskDialog open={editing !== null} task={editing} onClose={() => setEditing(null)} onSaved={load} />
    </Panel>
  );
}
