import { apiFetch } from "./client";
import type { AdminUserInput, ProvisionedUser, ResetPasswordResult, User } from "./contracts";

export const listAdminUsers = () => apiFetch<User[]>("/api/admin/users");

export const createAdminUser = (input: AdminUserInput) =>
  apiFetch<ProvisionedUser>("/api/admin/users", {
    method: "POST",
    body: JSON.stringify(input),
  });

export const resetAdminUserPassword = (userId: string) =>
  apiFetch<ResetPasswordResult>(`/api/admin/users/${userId}/reset-password`, { method: "POST" });

export const updateAdminUserStatus = (userId: string, status: "active" | "disabled") =>
  apiFetch<User>(`/api/admin/users/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
