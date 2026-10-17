"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Panel, PanelHeader } from "@/components/ui/Panel";
import { useAuth } from "@/lib/auth";
import { tasksApi, type Task } from "./api";
import { TaskDialog } from "./TaskDialog";
import { TaskList } from "./TaskList";

/** Open tasks about one record (customer, ticket …), with "Add task" linking new ones to it. */
export function RecordTasks({ type, id, label, onChange }: { type: string; id: number; label?: string; onChange?: () => void }) {
  const { can } = useAuth();
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [showDone, setShowDone] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(() => {
    tasksApi
      .list({ related_type: type, related_id: id, status: showDone ? "all" : "open", page_size: 50 })
      .then((page) => setTasks(page.items))
      .catch(() => setTasks([]));
  }, [type, id, showDone]);

  useEffect(() => {
    load();
  }, [load]);

  const changed = () => {
    load();
    onChange?.();
  };

  return (
    <Panel>
      <PanelHeader
        title="Tasks"
        actions={
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" aria-pressed={showDone} onClick={() => setShowDone((v) => !v)}>
              {showDone ? "Hide finished" : "Show finished"}
            </Button>
            {can("tasks:edit_own") && (
              <Button variant="secondary" size="sm" onClick={() => setAdding(true)}>
                Add task
              </Button>
            )}
          </div>
        }
      />
      <TaskList tasks={tasks} onEdit={setEditing} onChanged={changed} showOwner showRelated={false} empty="No open tasks." />
      <TaskDialog
        open={adding || editing !== null}
        task={editing}
        related={{ type, id, label }}
        onClose={() => {
          setAdding(false);
          setEditing(null);
        }}
        onSaved={changed}
      />
    </Panel>
  );
}
