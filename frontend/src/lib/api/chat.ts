import { API_BASE_URL, toApiError } from "./client";
import type { SseEvent } from "./contracts";
import { getToken } from "@/lib/auth/token-store";
import { parseSseStream } from "@/lib/sse/parser";

export async function streamChat(
  input: { session_id: string; prompt: string; active_case_id: string | null },
  signal: AbortSignal,
  onEvent: (event: SseEvent) => void,
) {
  const token = getToken();
  const requestId = typeof crypto !== "undefined" && "randomUUID" in crypto ? `web-${crypto.randomUUID()}` : `web-${Date.now()}`;
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    signal,
    headers: {
      Authorization: `Bearer ${token ?? ""}`,
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      "X-Request-ID": requestId,
    },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw await toApiError(response);
  if (!response.body) throw new Error("EMPTY_STREAM");
  let completed = false;
  for await (const event of parseSseStream(response.body)) {
    onEvent(event);
    if (event.event === "run.completed") completed = true;
    if (event.event === "run.failed") completed = true;
  }
  if (!completed && !signal.aborted) throw new Error("STREAM_INTERRUPTED");
}
