import { clearToken, getToken, isDemoMode } from "./auth";
import type { AgentRun, MetricsSummary, RunDetail, RunEvent, RunFilters, TokenResponse, ToolCall, User } from "./contracts";
import { mockDetail, mockMetrics, mockRuns } from "./mock-data";

const base = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend").replace(/\/$/, "");
type Json = Record<string, unknown>;
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); this.name = "ApiError"; } }
async function request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(init.headers); if (init.body) headers.set("Content-Type", "application/json");
  if (auth) { const token = getToken(); if (!token) throw new ApiError(401, "请先登录"); headers.set("Authorization", `Bearer ${token}`); }
  let response: Response; try { response = await fetch(`${base}${path}`, { ...init, headers }); } catch { throw new ApiError(0, "无法连接 Python 中台，请确认 8000 端口服务正常"); }
  if (!response.ok) { if (response.status === 401) clearToken(); let message = "服务暂时不可用"; try { const body = await response.json(); message = body.error?.message ?? body.detail ?? message; } catch { /* non-JSON error */ } throw new ApiError(response.status, message); }
  return response.status === 204 ? undefined as T : response.json();
}
const stringValue = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;
const numberValue = (value: unknown, fallback = 0) => typeof value === "number" ? value : fallback;
const nullableString = (value: unknown) => typeof value === "string" ? value : null;
const nullableNumber = (value: unknown) => typeof value === "number" ? value : null;
function mapRun(item: Json): AgentRun { return { id: stringValue(item.id), request_id: stringValue(item.requestId), turn_id: stringValue(item.turnId), user_id: stringValue(item.userId), employee_no: nullableString(item.employeeNo) ?? undefined, user_name: nullableString(item.userName) ?? undefined, session_id: stringValue(item.sessionId), case_id: nullableString(item.caseId), status: stringValue(item.status, "failed") as AgentRun["status"], model_provider: stringValue(item.modelProvider, "—"), model_id: stringValue(item.modelId, "—"), input_tokens: numberValue(item.inputTokens), output_tokens: numberValue(item.outputTokens), estimated_input_tokens: numberValue(item.estimatedInputTokens), tool_call_count: numberValue(item.toolCallCount), started_at: stringValue(item.startedAt), first_token_at: nullableString(item.firstTokenAt), completed_at: nullableString(item.completedAt), duration_ms: nullableNumber(item.durationMs), error_stage: nullableString(item.errorStage), error_code: nullableString(item.errorCode), error_message_safe: nullableString(item.errorMessage) }; }
function mapEvent(item: Json, index: number): RunEvent { return { id: `${stringValue(item.eventType)}-${index}`, sequence_no: numberValue(item.sequenceNo, index + 1), event_type: stringValue(item.eventType), event_time: stringValue(item.occurredAt), service: stringValue(item.service), tool_call_id: nullableString(item.toolCallId), payload_safe: (item.payload && typeof item.payload === "object" ? item.payload : {}) as Record<string, unknown> }; }
function mapTool(item: Json, index: number): ToolCall { return { id: `${stringValue(item.toolCallId)}-${index}`, tool_call_id: stringValue(item.toolCallId), tool_name: stringValue(item.name), status: stringValue(item.status), arguments_safe: (item.arguments && typeof item.arguments === "object" ? item.arguments : {}) as Record<string, unknown>, result_summary: (item.resultSummary && typeof item.resultSummary === "object" ? item.resultSummary : {}) as Record<string, unknown>, source_ids: Array.isArray(item.sourceIds) ? item.sourceIds.map(String) : [], error_code: nullableString(item.errorCode), started_at: stringValue(item.startedAt), duration_ms: nullableNumber(item.durationMs) }; }

export async function login(employeeNo: string, password: string): Promise<TokenResponse> { if (isDemoMode()) { if (employeeNo !== "000001" || password !== "Admin123456") throw new ApiError(401, "演示账号或密码不正确"); return { access_token: "demo-admin-token", requires_password_change: false }; } return request("/api/auth/login", { method: "POST", body: JSON.stringify({ employee_no: employeeNo, password }) }, false); }
export async function getMe(): Promise<User> { if (isDemoMode()) return { id: "demo-admin", employee_no: "000001", name: "系统管理员", role: "admin", must_change_password: false }; return request("/api/auth/me"); }
export async function listRuns(filters: RunFilters): Promise<AgentRun[]> {
  if (isDemoMode()) { const q = filters.query?.toLowerCase(); return mockRuns.filter((run) => (!filters.status || run.status === filters.status) && (!filters.error_code || run.error_code === filters.error_code) && (!q || `${run.request_id} ${run.session_id} ${run.employee_no} ${run.user_name}`.toLowerCase().includes(q))); }
  const params = new URLSearchParams(); if (filters.status) params.set("status", filters.status); if (filters.error_code) params.set("error_code", filters.error_code); if (filters.from) params.set("from", filters.from); if (filters.to) params.set("to", filters.to); if (filters.query?.startsWith("req-")) params.set("request_id", filters.query); else if (/^\d{6,10}$/.test(filters.query ?? "")) params.set("employee_no", filters.query!);
  const data = await request<{ items: Json[] }>(`/api/admin/agent-runs?${params}`); return data.items.map(mapRun);
}
export async function getRun(id: string): Promise<RunDetail> { if (isDemoMode()) return mockDetail(id); const [run, events, tools] = await Promise.all([request<Json>(`/api/admin/agent-runs/${id}`), request<Json[]>(`/api/admin/agent-runs/${id}/events`), request<Json[]>(`/api/admin/agent-runs/${id}/tool-calls`)]); return { ...mapRun(run), events: events.map(mapEvent), tool_calls: tools.map(mapTool) }; }
export async function getMetrics(): Promise<MetricsSummary> {
  if (isDemoMode()) return mockMetrics;
  const [summary, errorRows, running] = await Promise.all([request<Json>("/api/admin/agent-metrics/summary"), request<Json[]>("/api/admin/agent-metrics/errors"), request<{ items: Json[] }>("/api/admin/agent-runs?status=running&limit=1")]); const total = numberValue(summary.runCount); const success = numberValue(summary.successCount);
  return { total_runs: total, success_rate: numberValue(summary.successRate) * 100, failed_runs: Math.max(0, total - success), cancelled_runs: 0, active_runs: running.items.length, avg_duration_ms: nullableNumber(summary.averageDurationMs), avg_first_token_ms: nullableNumber(summary.averageFirstTokenMs), input_tokens: numberValue(summary.totalInputTokens), output_tokens: numberValue(summary.totalOutputTokens), tool_call_count: numberValue(summary.toolCallCount), tool_success_rate: null, trend: [], errors: errorRows.map((item) => ({ code: stringValue(item.errorCode, "UNKNOWN"), count: numberValue(item.count) })) };
}
