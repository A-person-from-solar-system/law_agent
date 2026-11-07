import type { AgentRun, MetricsSummary, RunDetail } from "./contracts";

const now = Date.now();
const iso = (minutes: number) => new Date(now - minutes * 60_000).toISOString();
export const mockRuns: AgentRun[] = [
  { id: "run-a81f2", request_id: "req-20260911-a81f2c", turn_id: "turn-8841", user_id: "u-1", employee_no: "100086", user_name: "张明", session_id: "session-3894", case_id: "case-114", status: "completed", model_provider: "openai", model_id: "gpt-5.6-sol", input_tokens: 4182, output_tokens: 1260, estimated_input_tokens: 4390, tool_call_count: 2, started_at: iso(4), first_token_at: iso(3.96), completed_at: iso(3.8), duration_ms: 12480 },
  { id: "run-6d937", request_id: "req-20260911-6d937e", turn_id: "turn-8839", user_id: "u-2", employee_no: "100032", user_name: "李雯", session_id: "session-3671", status: "failed", model_provider: "openai", model_id: "gpt-5.6-sol", input_tokens: 2910, output_tokens: 0, estimated_input_tokens: 3024, tool_call_count: 1, started_at: iso(12), completed_at: iso(11.9), duration_ms: 6840, error_stage: "rag", error_code: "RAG_TIMEOUT", error_message_safe: "知识检索服务响应超时，可稍后重试。" },
  { id: "run-b219c", request_id: "req-20260911-b219cf", turn_id: "turn-8836", user_id: "u-3", employee_no: "100017", user_name: "王涛", session_id: "session-3510", status: "completed", model_provider: "openai", model_id: "gpt-5.6-sol", input_tokens: 6870, output_tokens: 2084, estimated_input_tokens: 7100, tool_call_count: 3, started_at: iso(25), first_token_at: iso(24.95), completed_at: iso(24.6), duration_ms: 23860 },
  { id: "run-f112a", request_id: "req-20260911-f112ae", turn_id: "turn-8828", user_id: "u-1", employee_no: "100086", user_name: "张明", session_id: "session-3427", status: "cancelled", model_provider: "openai", model_id: "gpt-5.6-sol", input_tokens: 1680, output_tokens: 240, estimated_input_tokens: 1810, tool_call_count: 0, started_at: iso(48), completed_at: iso(47.9), duration_ms: 5920, error_stage: "stream", error_code: "CLIENT_DISCONNECTED", error_message_safe: "客户端主动断开连接。" },
  { id: "run-e83b4", request_id: "req-20260911-e83b41", turn_id: "turn-8820", user_id: "u-4", employee_no: "100105", user_name: "陈静", session_id: "session-3208", status: "rejected", model_provider: "openai", model_id: "gpt-5.6-sol", input_tokens: 0, output_tokens: 0, estimated_input_tokens: 126440, tool_call_count: 0, started_at: iso(72), completed_at: iso(71.99), duration_ms: 41, error_stage: "context", error_code: "CONTEXT_LIMIT_EXCEEDED", error_message_safe: "本轮上下文超过安全预算，未调用模型。" },
];

export const mockDetail = (id: string): RunDetail => {
  const run = mockRuns.find((item) => item.id === id) ?? mockRuns[0];
  const base = new Date(run.started_at).getTime();
  const event = (sequence_no: number, event_type: string, offset: number, service: string, payload_safe: Record<string, unknown> = {}) => ({ id: `${run.id}-ev-${sequence_no}`, sequence_no, event_type, event_time: new Date(base + offset).toISOString(), service, payload_safe });
  const normal = [
    event(1, "run.received", 0, "mid-layer", { source: "web", caseBound: Boolean(run.case_id) }),
    event(2, "context.built", 85, "mid-layer", { historyMessageCount: 12, checkpointVersion: 3, caseMaterialChars: 8420 }),
    event(3, "context.checked", 146, "agent-engine", { estimatedInputTokens: run.estimated_input_tokens, outputReserve: 4096, accepted: run.status !== "rejected" }),
    event(4, "model.started", 220, "agent-engine", { provider: run.model_provider, model: run.model_id }),
    event(5, "tool.started", 1240, "agent-engine", { toolName: "search_legal_kb", queryLength: 48, contentMode: "metadata" }),
    event(6, run.status === "failed" ? "tool.failed" : "tool.completed", 3180, "rag", run.status === "failed" ? { errorCode: run.error_code, retryable: true } : { evidenceCount: 5, omittedCount: 15 }),
    ...(run.status === "completed" ? [event(7, "model.first_token", 4060, "agent-engine", { latencyMs: 4060 }), event(8, "run.completed", run.duration_ms ?? 12480, "mid-layer", { inputTokens: run.input_tokens, outputTokens: run.output_tokens })] : [event(7, `run.${run.status}`, run.duration_ms ?? 6840, "mid-layer", { errorCode: run.error_code, stage: run.error_stage })]),
  ];
  return { ...run, events: normal, tool_calls: run.tool_call_count ? [{ id: `${run.id}-tool-1`, tool_call_id: "toolcall-c4027", tool_name: "search_legal_kb", status: run.status === "failed" ? "failed" : "completed", arguments_safe: { queryHash: "sha256:7db2…f91a", queryLength: 48, mode: "hybrid", limit: 20 }, result_summary: run.status === "failed" ? {} : { totalCandidates: 20, evidenceCount: 5, omittedCount: 15, estimatedTokens: 1130, sourceTypes: ["case", "statute"] }, source_ids: run.status === "failed" ? [] : ["case-2024-18371", "statute-criminal-law-133", "case-2023-9920"], error_code: run.status === "failed" ? "RAG_TIMEOUT" : null, started_at: new Date(base + 1240).toISOString(), duration_ms: 1940 }] : [] };
};

export const mockMetrics: MetricsSummary = { total_runs: 1284, success_rate: 96.4, failed_runs: 32, cancelled_runs: 14, active_runs: 3, avg_duration_ms: 11340, avg_first_token_ms: 3120, input_tokens: 3849200, output_tokens: 1124700, tool_call_count: 912, tool_success_rate: 98.1, trend: [{ label: "09-05", completed: 142, failed: 5 }, { label: "09-06", completed: 168, failed: 3 }, { label: "09-07", completed: 121, failed: 7 }, { label: "09-08", completed: 190, failed: 4 }, { label: "09-09", completed: 214, failed: 6 }, { label: "09-10", completed: 238, failed: 3 }, { label: "今天", completed: 165, failed: 4 }], errors: [{ code: "RAG_TIMEOUT", count: 12 }, { code: "MODEL_TIMEOUT", count: 8 }, { code: "CONTEXT_LIMIT_EXCEEDED", count: 7 }, { code: "CLIENT_DISCONNECTED", count: 5 }] };
