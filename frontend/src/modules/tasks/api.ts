"use client";

import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";

export type TaskStatus = "open" | "done" | "cancelled";
export type TaskPriority = "low" | "normal" | "high";
export type Recurrence = "daily" | "weekly" | "monthly";

export interface Task {
  id: number;
  title: string;
  description: string | null;
  task_type: string | null;
  priority: TaskPriority;
  status: TaskStatus;
  due_at: string | null;
  due_has_time: boolean;
  reminder_at: string | null;
  recurrence: Recurrence | null;
  owner_id: number | null;
  related_type: string | null;
  related_id: number | null;
  related_label: string | null;
  completed_at: string | null;
  completed_by: number | null;
  created_at: string;
  created_by: number | null;
  updated_at: string;
  is_overdue: boolean;
}

export interface TaskInput {
  title?: string;
  description?: string | null;
  task_type?: string | null;
  priority?: TaskPriority;
  due_at?: string | null;
  due_has_time?: boolean;
  reminder_at?: string | null;
  recurrence?: Recurrence | null;
  owner_id?: number | null;
  related_type?: string | null;
  related_id?: number | null;
  status?: TaskStatus;
}

export interface TaskFilters {
  view?: "mine" | "team" | "created";
  status?: TaskStatus | "all";
  due?: "any" | "overdue" | "today" | "week" | "none";
  related_type?: string;
  related_id?: number;
  owner_id?: number;
  type?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const tasksApi = {
  list: (f: TaskFilters) => apiFetch<Page<Task>>(`/tasks${qs({ ...f })}`),
  summary: () => apiFetch<{ open: number; overdue: number; due_today: number }>("/tasks/summary"),
  get: (id: number) => apiFetch<Task>(`/tasks/${id}`),
  create: (data: TaskInput) => apiFetch<Task>("/tasks", json("POST", data)),
  update: (id: number, data: TaskInput) => apiFetch<Task>(`/tasks/${id}`, json("PATCH", data)),
  remove: (id: number) => apiFetch<void>(`/tasks/${id}`, { method: "DELETE" }),
};

/** Where a related record lives in the app. */
export function recordHref(type: string | null, id: number | null) {
  if (!type || !id) return null;
  return { customer: `/customers/${id}`, ticket: `/tickets/${id}`, deal: `/sales/${id}` }[type] ?? null;
}

const dayFmt = new Intl.DateTimeFormat("en-US", { weekday: "short", month: "short", day: "numeric" });
const timeFmt = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" });

/** "Today", "Tomorrow", "Mon, Oct 19" (+ time when the task has one). */
export function formatDue(task: Pick<Task, "due_at" | "due_has_time">, now = new Date()) {
  if (!task.due_at) return null;
  const d = new Date(task.due_at);
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((startOf(d) - startOf(now)) / 86400000);
  const day = days === 0 ? "Today" : days === 1 ? "Tomorrow" : days === -1 ? "Yesterday" : dayFmt.format(d);
  return task.due_has_time ? `${day}, ${timeFmt.format(d)}` : day;
}

/** Local date ("2026-10-19") and time ("14:30" or "") from an ISO string, for inputs. */
export function splitLocal(iso: string | null, hasTime: boolean): { date: string; time: string } {
  if (!iso) return { date: "", time: "" };
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: hasTime ? `${pad(d.getHours())}:${pad(d.getMinutes())}` : "",
  };
}

/** ISO from local inputs; an all-day task is due at the end of that day. */
export function joinLocal(date: string, time: string): string | null {
  if (!date) return null;
  return new Date(`${date}T${time || "23:59"}:00`).toISOString();
}
