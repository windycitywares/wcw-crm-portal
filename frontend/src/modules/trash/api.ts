import { apiFetch, qs } from "@/lib/client-api";

export interface TrashItem {
  type: string;
  label: string;
  id: number;
  title: string;
  deleted_at: string;
  deleted_by: number | null;
  /** When the auto-empty removes it for good. */
  purge_after: string;
}

export interface TrashPage {
  items: TrashItem[];
  total: number;
  page: number;
  page_size: number;
  retention_days: number;
}

export interface TrashCount {
  type: string;
  label: string;
  count: number;
}

export const trashApi = {
  list: (type: string, page: number) =>
    apiFetch<TrashPage>(`/trash${qs({ type: type || undefined, page, page_size: 50 })}`),
  summary: () => apiFetch<TrashCount[]>("/trash/summary"),
  restore: (type: string, id: number) => apiFetch<{ title: string }>(`/trash/${type}/${id}/restore`, { method: "POST" }),
  purge: (type: string, id: number) => apiFetch<void>(`/trash/${type}/${id}`, { method: "DELETE" }),
  /** What still hangs off a record ("2 deals"); empty when it can be deleted. */
  blockers: (type: string, id: number) => apiFetch<string[]>(`/trash/blockers/${type}/${id}`),
};
