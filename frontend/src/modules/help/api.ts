import { apiFetch, qs } from "@/lib/client-api";

export interface TopicSummary { topic_id: string; helpful: number; not_helpful: number; last_at: string }
export interface FeedbackRow { id: number; topic_id: string; page: string; helpful: boolean; comment: string | null; user_name: string | null; created_at: string }

export const helpApi = {
  send: (data: { topic_id: string; page: string; helpful: boolean; comment?: string }) =>
    apiFetch<void>("/help/feedback", { method: "POST", body: JSON.stringify(data) }),
  summary: () => apiFetch<TopicSummary[]>("/help/feedback/summary"),
  list: (params: { topic_id?: string; helpful?: boolean; limit?: number }) => apiFetch<FeedbackRow[]>(`/help/feedback${qs(params)}`),
};
