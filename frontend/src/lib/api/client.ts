import { clearToken, getToken } from "@/lib/auth/token-store";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "/backend").replace(/\/$/, "");

type ApiErrorBody = {
  error?: { code?: string; message?: string; requestId?: string; details?: unknown };
};

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function toApiError(response: Response) {
  let body: ApiErrorBody = {};
  try { body = (await response.json()) as ApiErrorBody; } catch { /* non-JSON response */ }
  return new ApiError(
    response.status,
    body.error?.code ?? `HTTP_${response.status}`,
    body.error?.message ?? "服务暂时不可用，请稍后重试",
    body.error?.requestId ?? response.headers.get("X-Request-ID") ?? undefined,
    body.error?.details,
  );
}

export async function apiFetch<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (authenticated) {
    const token = getToken();
    if (!token) throw new ApiError(401, "AUTH_REQUIRED", "请先登录");
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    if (response.status === 401) {
      clearToken();
      if (typeof window !== "undefined") window.dispatchEvent(new Event("law-agent:unauthorized"));
    }
    throw await toApiError(response);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export { API_BASE_URL };
