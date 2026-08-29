import { apiFetch } from "./client";
import type { TokenResponse, User } from "./contracts";

export const login = (email: string, password: string) =>
  apiFetch<TokenResponse>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, false);

export const register = (email: string, password: string) =>
  apiFetch<User>("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }, false);

export const getMe = () => apiFetch<User>("/api/auth/me");
