import { apiFetch } from "./client";
import type { MessagePage, Session } from "./contracts";

export const listSessions = () => apiFetch<Session[]>("/api/sessions");
export const getSession = (id: string) => apiFetch<Session>(`/api/sessions/${id}`);
export const createSession = (input: { title?: string; active_case_id?: string | null } = {}) =>
  apiFetch<Session>("/api/sessions", { method: "POST", body: JSON.stringify({ title: input.title ?? "新会话", active_case_id: input.active_case_id ?? null }) });
export const updateSession = (id: string, input: Partial<Pick<Session, "title" | "active_case_id" | "status">>) =>
  apiFetch<Session>(`/api/sessions/${id}`, { method: "PATCH", body: JSON.stringify(input) });
export const deleteSession = (id: string) => apiFetch<void>(`/api/sessions/${id}`, { method: "DELETE" });
export const listMessages = (id: string, cursor?: number) =>
  apiFetch<MessagePage>(`/api/sessions/${id}/messages?limit=50${cursor ? `&cursor=${cursor}` : ""}`);
