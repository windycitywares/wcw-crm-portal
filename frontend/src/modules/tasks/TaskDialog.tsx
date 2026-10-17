"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ConfirmDialog, Modal } from "@/components/ui/Modal";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/utils";
import { useDirectory } from "@/modules/records/useDirectory";
import { useLookups } from "@/modules/settings/useLookups";
import { joinLocal, splitLocal, tasksApi, type Recurrence, type Task, type TaskInput, type TaskPriority } from "./api";

type Reminder = "none" | "morning" | "hour" | "daybefore" | "keep";

interface Form {
  title: string;
  description: string;
  task_type: string;
  priority: TaskPriority;
  date: string;
  time: string;
  reminder: Reminder;
  recurrence: Recurrence | "";
  owner_id: string;
}

function reminderAt(form: Form, keep: string | null): string | null {
  if (!form.date || form.reminder === "none") return null;
  if (form.reminder === "keep") return keep;
  if (form.reminder === "hour" && form.time) return new Date(new Date(`${form.date}T${form.time}:00`).getTime() - 3600_000).toISOString();
  const day = new Date(`${form.date}T09:00:00`);
  if (form.reminder === "daybefore") day.setDate(day.getDate() - 1);
  return day.toISOString();
}

/** Add or edit a task. `related` links a new task to a record (e.g. the customer page). */
export function TaskDialog({
  open,
  task,
  related,
  onClose,
  onSaved,
}: {
  open: boolean;
  task: Task | null;
  related?: { type: string; id: number; label?: string };
  onClose: () => void;
  onSaved: () => void;
}) {
  const { user, can } = useAuth();
  const { people } = useDirectory();
  const lookups = useLookups();
  const toast = useToast();
  const [form, setForm] = useState<Form | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!open) return;
    const due = splitLocal(task?.due_at ?? null, task?.due_has_time ?? false);
    setForm({
      title: task?.title ?? "",
      description: task?.description ?? "",
      task_type: task?.task_type ?? "",
      priority: task?.priority ?? "normal",
      date: due.date,
      time: due.time,
      reminder: task?.reminder_at ? "keep" : "none",
      recurrence: task?.recurrence ?? "",
      owner_id: String(task?.owner_id ?? user?.id ?? ""),
    });
    setError(null);
  }, [open, task, user?.id]);

  if (!form) return null;
  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm({ ...form, [key]: value });
  const canAssign = can("tasks:assign");
  const owners = [...people.values()].filter((p) => p.is_active || String(p.id) === form.owner_id).sort((a, b) => a.full_name.localeCompare(b.full_name));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    if (!form.title.trim()) return setError("Give the task a title.");
    setBusy(true);
    setError(null);
    const data: TaskInput = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      task_type: form.task_type || null,
      priority: form.priority,
      due_at: joinLocal(form.date, form.time),
      due_has_time: Boolean(form.date && form.time),
      reminder_at: reminderAt(form, task?.reminder_at ?? null),
      recurrence: form.date ? form.recurrence || null : null,
      owner_id: form.owner_id ? Number(form.owner_id) : null,
    };
    try {
      if (task) await tasksApi.update(task.id, data);
      else await tasksApi.create({ ...data, related_type: related?.type ?? null, related_id: related?.id ?? null });
      toast.push({ title: task ? "Task saved" : "Task added", description: form.title.trim() });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!task) return;
    setBusy(true);
    try {
      await tasksApi.remove(task.id);
      toast.push({ title: "Task deleted", description: task.title });
      setDeleting(false);
      onSaved();
      onClose();
    } catch (err) {
      toast.push({ tone: "danger", title: "Couldn't delete", description: err instanceof Error ? err.message : undefined });
    } finally {
      setBusy(false);
    }
  }

  const linked = task?.related_label ?? related?.label;
  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={task ? "Edit task" : "Add a task"}
        description={linked ? `About ${linked}` : undefined}
        footer={
          <>
            {task && (
              <Button variant="ghost" size="sm" className="mr-auto text-danger" onClick={() => setDeleting(true)}>
                Delete
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" form="task-form" size="sm" disabled={busy}>
              {busy ? "Saving…" : task ? "Save task" : "Add task"}
            </Button>
          </>
        }
      >
        <form id="task-form" onSubmit={save} className="grid gap-4 sm:grid-cols-2">
          {error && (
            <p role="alert" className="text-sm text-danger sm:col-span-2">
              {error}
            </p>
          )}
          <Field label="Title" className="sm:col-span-2">
            {(p) => <Input {...p} required maxLength={200} autoFocus value={form.title} onChange={(e) => set("title", e.target.value)} />}
          </Field>
          <Field label="Type">
            {(p) => (
              <Select {...p} value={form.task_type} onChange={(e) => set("task_type", e.target.value)}>
                <option value="">Not set</option>
                {lookups.options("task_type", task?.task_type).map((v) => (
                  <option key={v.key} value={v.key}>
                    {v.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Priority">
            {(p) => (
              <Select {...p} value={form.priority} onChange={(e) => set("priority", e.target.value as TaskPriority)}>
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
              </Select>
            )}
          </Field>
          <Field label="Due date" hint="Optional.">
            {(p) => <Input {...p} type="date" value={form.date} onChange={(e) => set("date", e.target.value)} />}
          </Field>
          <Field label="Time" hint="Leave empty for all day.">
            {(p) => <Input {...p} type="time" disabled={!form.date} value={form.time} onChange={(e) => set("time", e.target.value)} />}
          </Field>
          <Field label="Reminder email" hint={form.reminder === "keep" && task?.reminder_at ? `Currently ${formatDateTime(task.reminder_at)}` : undefined}>
            {(p) => (
              <Select {...p} disabled={!form.date} value={form.date ? form.reminder : "none"} onChange={(e) => set("reminder", e.target.value as Reminder)}>
                <option value="none">No reminder</option>
                {task?.reminder_at && <option value="keep">Keep the current reminder</option>}
                <option value="morning">Morning of the due day (9:00)</option>
                {form.time && <option value="hour">1 hour before</option>}
                <option value="daybefore">The day before (9:00)</option>
              </Select>
            )}
          </Field>
          <Field label="Repeat" hint={form.recurrence ? "Finishing it adds the next one." : undefined}>
            {(p) => (
              <Select {...p} disabled={!form.date} value={form.date ? form.recurrence : ""} onChange={(e) => set("recurrence", e.target.value as Recurrence | "")}>
                <option value="">Doesn&apos;t repeat</option>
                <option value="daily">Every day</option>
                <option value="weekly">Every week</option>
                <option value="monthly">Every month</option>
              </Select>
            )}
          </Field>
          <Field label="Assigned to" className="sm:col-span-2" hint={canAssign ? undefined : "Managers can give tasks to someone else."}>
            {(p) => (
              <Select {...p} disabled={!canAssign} value={form.owner_id} onChange={(e) => set("owner_id", e.target.value)}>
                {owners.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.full_name}
                    {o.id === user?.id ? " (you)" : ""}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Details" className="sm:col-span-2" hint="Optional.">
            {(p) => <Textarea {...p} rows={3} maxLength={10000} value={form.description} onChange={(e) => set("description", e.target.value)} />}
          </Field>
        </form>
      </Modal>
      <ConfirmDialog
        open={deleting}
        title="Delete this task?"
        message={`“${task?.title}” will be removed from everyone's lists.`}
        confirmLabel="Delete task"
        tone="danger"
        busy={busy}
        onConfirm={() => void remove()}
        onCancel={() => setDeleting(false)}
      />
    </>
  );
}
