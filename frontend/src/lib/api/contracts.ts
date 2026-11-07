export type User = {
  id: string;
  employee_no: string;
  name: string;
  email: string | null;
  role: "admin" | "employee";
  status: string;
  must_change_password: boolean;
  password_expires_at: string | null;
  created_at: string;
};
export type TokenResponse = { access_token: string; token_type: string; requires_password_change: boolean };
export type ProvisionedUser = User & { initial_password: string };
export type ResetPasswordResult = {
  user_id: string;
  employee_no: string;
  initial_password: string;
  password_expires_at: string;
};
export type AdminUserInput = {
  employee_no: string;
  name: string;
  email?: string | null;
  role: "admin" | "employee";
};

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
