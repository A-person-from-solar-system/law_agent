const TOKEN_KEY = "law-agent-access-token";

export function getToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  Object.keys(window.sessionStorage)
    .filter((key) => key.startsWith("law-agent-draft:"))
    .forEach((key) => window.sessionStorage.removeItem(key));
}
