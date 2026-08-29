export type User = { id: string; email: string; status: string };
export type TokenResponse = { access_token: string; token_type: string };

export type Session = {
  id: string;
  title: string;
  active_case_id: string | null;
  status: "active" | "archived" | string;
  checkpoint_index: number;
  checkpoint_version: number;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  status: "completed" | "failed" | "cancelled" | string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type MessagePage = { items: ChatMessage[]; next_cursor: number | null };

export type UserCase = {
  id: string;
  name: string;
  summary: string;
  content: string;
  structured_facts: Record<string, unknown>;
  status: "active" | "archived" | string;
  created_at: string;
  updated_at: string;
};

export type CaseInput = Pick<UserCase, "name" | "summary" | "content" | "structured_facts">;

export type SseEventName =
  | "run.started"
  | "text.delta"
  | "tool.started"
  | "tool.completed"
  | "usage"
  | "run.completed"
  | "run.failed"
  | "checkpoint.pending";

export type SseEvent = { event: SseEventName | string; data: Record<string, unknown> };
export type ToolActivity = { id: string; name: string; status: "running" | "completed" | "failed" };
