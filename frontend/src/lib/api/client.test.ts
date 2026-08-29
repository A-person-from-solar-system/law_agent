import { describe, expect, it } from "vitest";
import { toApiError } from "./client";

describe("API errors", () => {
  it("normalizes backend error contracts", async () => {
    const response = new Response(JSON.stringify({ error: { code: "SESSION_NOT_FOUND", message: "会话不存在", requestId: "req-1" } }), { status: 404, headers: { "Content-Type": "application/json" } });
    const error = await toApiError(response);
    expect(error).toMatchObject({ status: 404, code: "SESSION_NOT_FOUND", message: "会话不存在", requestId: "req-1" });
  });
});
