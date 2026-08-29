import { apiFetch } from "./client";
import type { CaseInput, UserCase } from "./contracts";

export const listCases = () => apiFetch<UserCase[]>("/api/cases");
export const getCase = (id: string) => apiFetch<UserCase>(`/api/cases/${id}`);
export const createCase = (input: CaseInput) => apiFetch<UserCase>("/api/cases", { method: "POST", body: JSON.stringify(input) });
export const updateCase = (id: string, input: Partial<CaseInput> & { status?: string }) =>
  apiFetch<UserCase>(`/api/cases/${id}`, { method: "PATCH", body: JSON.stringify(input) });
export const deleteCase = (id: string) => apiFetch<void>(`/api/cases/${id}`, { method: "DELETE" });
