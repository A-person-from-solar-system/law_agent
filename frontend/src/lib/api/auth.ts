import { apiFetch } from "./client";
import type { TokenResponse, User } from "./contracts";

export const login = (employeeNo: string, password: string) =>
  apiFetch<TokenResponse>("/api/auth/login", { method: "POST", body: JSON.stringify({ employee_no: employeeNo, password }) }, false);

export const changePassword = (currentPassword: string, newPassword: string) =>
  apiFetch<void>("/api/auth/change-password", { method: "POST", body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) });

export const getMe = () => apiFetch<User>("/api/auth/me");
