export type RunStatus = "running" | "completed" | "failed" | "cancelled" | "rejected";
export type User = { id: string; employee_no: string; name: string; role: "admin" | "employee"; must_change_password: boolean };
export type TokenResponse = { access_token: string; requires_password_change: boolean };
export type AgentRun = {
  id: string; request_id: string; turn_id: string; user_id: string; employee_no?: string; user_name?: string;
  session_id: string; case_id?: string | null; status: RunStatus; model_provider: string; model_id: string;
  input_tokens: number; output_tokens: number; estimated_input_tokens: number; tool_call_count: number;
  started_at: string; first_token_at?: string | null; completed_at?: string | null; duration_ms?: number | null;
  error_stage?: string | null; error_code?: string | null; error_message_safe?: string | null;
};
export type RunEvent = { id: string; sequence_no: number; event_type: string; event_time: string; service: string; tool_call_id?: string | null; payload_safe: Record<string, unknown> };
export type ToolCall = { id: string; tool_call_id: string; tool_name: string; status: string; arguments_safe: Record<string, unknown>; result_summary: Record<string, unknown>; source_ids: string[]; error_code?: string | null; started_at: string; duration_ms?: number | null };
export type RunDetail = AgentRun & { events: RunEvent[]; tool_calls: ToolCall[] };
export type RunFilters = { query?: string; status?: string; from?: string; to?: string; error_code?: string };
export type MetricsSummary = { total_runs: number; success_rate: number; failed_runs: number; cancelled_runs: number; active_runs: number; avg_duration_ms?: number | null; p50_duration_ms?: number; p95_duration_ms?: number; avg_first_token_ms: number | null; input_tokens: number; output_tokens: number; tool_call_count?: number; tool_success_rate: number | null; trend: { label: string; completed: number; failed: number }[]; errors: { code: string; count: number }[] };
