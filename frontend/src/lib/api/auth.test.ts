import { beforeEach, describe, expect, it, vi } from "vitest";
import { changePassword, login } from "./auth";
import { setToken } from "@/lib/auth/token-store";

describe("employee authentication API", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("logs in with employee_no instead of email", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ access_token: "token", token_type: "bearer", requires_password_change: true }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await login("100001", "Temporary123");
    expect(result.requires_password_change).toBe(true);
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ employee_no: "100001", password: "Temporary123" });
  });

  it("submits the current and new password with the employee token", async () => {
    setToken("employee-token");
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await changePassword("Temporary123", "PermanentPassword123");
    const headers = fetchMock.mock.calls[0][1]?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer employee-token");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ current_password: "Temporary123", new_password: "PermanentPassword123" });
  });
});
