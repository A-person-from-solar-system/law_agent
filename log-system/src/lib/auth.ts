const TOKEN_KEY = "law-agent-log-admin-token";
export const isDemoMode = () => process.env.NEXT_PUBLIC_DEMO_MODE === "true";
export function getToken() { return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY); }
export function setToken(token: string) { localStorage.setItem(TOKEN_KEY, token); }
export function clearToken() { if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY); }
