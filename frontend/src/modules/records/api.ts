"use client";

import { apiFetch, qs } from "@/lib/client-api";
import type { Page } from "@/lib/types";
import type { Tag } from "@/modules/settings/api";

/** A record any shared feature can attach to, e.g. { type: "customer", id: 42 }. */
export interface RecordRef {
  type: string;
  id: number;
}

export interface Note {
  id: number;
  body: string;
  pinned: boolean;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface Activity {
  id: number;
  at: string;
  actor_id: number | null;
  kind: string;
  title: string;
  data: Record<string, unknown> | null;
}

export interface Attachment {
  id: number;
  entity_type: string;
  entity_id: number;
  message_id: number | null;
  filename: string;
  content_type: string;
  size: number;
  source: string;
  created_by: number | null;
  created_at: string;
}

export interface Colleague {
  id: number;
  full_name: string;
  title: string | null;
  is_active: boolean;
}

const base = (r: RecordRef) => `/entities/${r.type}/${r.id}`;
const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export const recordsApi = {
  notes: (r: RecordRef) => apiFetch<Note[]>(`${base(r)}/notes`),
  addNote: (r: RecordRef, body: string, pinned = false) => apiFetch<Note>(`${base(r)}/notes`, json("POST", { body, pinned })),
  updateNote: (id: number, data: { body?: string; pinned?: boolean }) => apiFetch<Note>(`/notes/${id}`, json("PATCH", data)),
  deleteNote: (id: number) => apiFetch<void>(`/notes/${id}`, { method: "DELETE" }),
  timeline: (r: RecordRef, page = 1, kind?: string) => apiFetch<Page<Activity>>(`${base(r)}/timeline${qs({ page, page_size: 25, kind })}`),
  tags: (r: RecordRef) => apiFetch<Tag[]>(`${base(r)}/tags`),
  setTags: (r: RecordRef, names: string[]) => apiFetch<Tag[]>(`${base(r)}/tags`, json("PUT", { names })),
  directory: () => apiFetch<Colleague[]>("/users/directory"),
  attachments: (r: RecordRef) => apiFetch<Attachment[]>(`${base(r)}/attachments`),
  uploadAttachment: (r: RecordRef, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<Attachment>(`${base(r)}/attachments`, { method: "POST", body: form });
  },
  attachmentUrl: (id: number) => `/attachments/${id}`, // fetched with the token by `apiDownload`
  deleteAttachment: (id: number) => apiFetch<void>(`/attachments/${id}`, { method: "DELETE" }),
};
