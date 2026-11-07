"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, LoaderCircle, Plus, RefreshCcw, Search, ShieldCheck, UserCog, UserRoundCheck, UserRoundX } from "lucide-react";
import { AppSidebar } from "@/components/workspace/app-sidebar";
import { Button } from "@/components/ui/button";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { createAdminUser, listAdminUsers, resetAdminUserPassword, updateAdminUserStatus } from "@/lib/api/admin-users";
import { getMe } from "@/lib/api/auth";
import type { AdminUserInput, ProvisionedUser, ResetPasswordResult, User } from "@/lib/api/contracts";
import { ApiError } from "@/lib/api/client";
import { formatRelativeTime } from "@/lib/utils";
import { UserFormDialog } from "./user-form-dialog";

type PasswordNotice = { employeeNo: string; password: string; expiresAt: string };

export function UsersWorkspace() {
  const ready = useRequireAuth(); const client = useQueryClient();
  const [query, setQuery] = useState(""); const [dialogOpen, setDialogOpen] = useState(false); const [notice, setNotice] = useState<PasswordNotice | null>(null); const [error, setError] = useState("");
  const me = useQuery({ queryKey: ["me"], queryFn: getMe, enabled: ready });
  const users = useQuery({ queryKey: ["admin-users"], queryFn: listAdminUsers, enabled: ready && me.data?.role === "admin" });
  const refresh = () => client.invalidateQueries({ queryKey: ["admin-users"] });
  const create = useMutation({ mutationFn: createAdminUser, onSuccess: async (item: ProvisionedUser) => { await refresh(); setDialogOpen(false); setNotice({ employeeNo: item.employee_no, password: item.initial_password, expiresAt: item.password_expires_at ?? "" }); }, onError: (cause) => setError(cause instanceof ApiError ? cause.message : "创建用户失败") });
  const reset = useMutation({ mutationFn: resetAdminUserPassword, onSuccess: async (item: ResetPasswordResult) => { await refresh(); setNotice({ employeeNo: item.employee_no, password: item.initial_password, expiresAt: item.password_expires_at }); }, onError: (cause) => setError(cause instanceof ApiError ? cause.message : "重置密码失败") });
  const status = useMutation({ mutationFn: ({ id, next }: { id: string; next: "active" | "disabled" }) => updateAdminUserStatus(id, next), onSuccess: refresh, onError: (cause) => setError(cause instanceof ApiError ? cause.message : "状态更新失败") });
  const filtered = useMemo(() => (users.data ?? []).filter((item) => `${item.employee_no} ${item.name} ${item.email ?? ""}`.toLowerCase().includes(query.toLowerCase())), [users.data, query]);
  async function copyPassword() { if (!notice) return; await navigator.clipboard.writeText(notice.password); }
  function toggleUser(item: User) { const next = item.status === "active" ? "disabled" : "active"; if (window.confirm(`确定${next === "active" ? "启用" : "禁用"}“${item.name}”吗？`)) status.mutate({ id: item.id, next }); }
  if (!ready) return <div className="full-loader"><LoaderCircle className="spin" /><span>正在验证登录状态</span></div>;
  if (me.isLoading) return <div className="full-loader"><LoaderCircle className="spin" /><span>正在加载账户权限</span></div>;
  if (me.data?.role !== "admin") return <main className="app-shell"><AppSidebar section="admin" /><section className="cases-main"><div className="empty-cases"><div className="case-icon"><ShieldCheck size={25} /></div><h2>需要管理员权限</h2><p>当前账户不能访问用户管理。</p></div></section></main>;
  return <main className="app-shell"><AppSidebar section="admin" /><section className="cases-main"><header className="cases-header"><div><span className="eyebrow">USER MANAGEMENT</span><h1>用户管理</h1><p>添加员工账号，重置一次性密码，控制账户启停状态。</p></div><Button onClick={() => { setError(""); setDialogOpen(true); }}><Plus size={17} />添加用户</Button></header>{notice && <div className="admin-secret-panel" role="status"><div><span>一次性初始密码</span><strong>{notice.password}</strong><small>员工号 {notice.employeeNo}{notice.expiresAt ? ` · 有效期至 ${new Date(notice.expiresAt).toLocaleString()}` : ""}</small></div><Button variant="secondary" size="sm" onClick={() => void copyPassword()}><Copy size={14} />复制</Button><button onClick={() => setNotice(null)} aria-label="关闭初始密码提示">×</button></div>}{error && <div className="form-error" role="alert">{error}</div>}<div className="cases-toolbar"><label className="case-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="按员工号、姓名或邮箱搜索" /></label><Button variant="secondary" size="sm" onClick={() => void refresh()} disabled={users.isFetching}><RefreshCcw className={users.isFetching ? "spin" : ""} size={14} />刷新</Button></div>{users.isLoading ? <div className="content-loader"><LoaderCircle className="spin" />正在加载用户</div> : filtered.length ? <div className="admin-user-table">{filtered.map((item) => <article className="admin-user-row" key={item.id}><div className="admin-user-main"><div className="case-icon"><UserCog size={19} /></div><div><h2>{item.name}</h2><p>{item.employee_no} · {item.role === "admin" ? "管理员" : "员工"} · {item.email || "未设置邮箱"}</p><small>创建于 {formatRelativeTime(item.created_at)}{item.must_change_password ? " · 待首次改密" : ""}</small></div></div><span className={`case-status status-${item.status === "active" ? "active" : "archived"}`}>{item.status === "active" ? "启用" : "禁用"}</span><div className="admin-user-actions"><Button variant="secondary" size="sm" onClick={() => reset.mutate(item.id)} disabled={reset.isPending}><RefreshCcw size={14} />重置密码</Button><button className={item.status === "active" ? "danger-link" : ""} onClick={() => toggleUser(item)} disabled={status.isPending}>{item.status === "active" ? <UserRoundX size={14} /> : <UserRoundCheck size={14} />}{item.status === "active" ? "禁用" : "启用"}</button></div></article>)}</div> : <div className="empty-cases"><div className="case-icon"><UserCog size={25} /></div><h2>{query ? "没有匹配的用户" : "还没有用户记录"}</h2><p>{query ? "尝试调整关键词。" : "添加第一个员工账号后，对方即可使用初始密码登录。"}</p>{!query && <Button onClick={() => setDialogOpen(true)}><Plus size={16} />添加用户</Button>}</div>}</section>{dialogOpen && <UserFormDialog open busy={create.isPending} onOpenChange={setDialogOpen} onSubmit={(input: AdminUserInput) => create.mutateAsync(input).then(() => undefined)} />}</main>;
}
