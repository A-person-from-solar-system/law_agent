"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Activity, Fingerprint, IdCard, LockKeyhole, ShieldCheck } from "lucide-react";
import { ApiError, login } from "@/lib/api";
import { isDemoMode, setToken } from "@/lib/auth";

export function LoginView() {
  const router = useRouter(); const search = useSearchParams();
  const [employeeNo, setEmployeeNo] = useState(isDemoMode() ? "000001" : ""); const [password, setPassword] = useState(isDemoMode() ? "Admin123456" : "");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  async function submit(event: React.FormEvent) { event.preventDefault(); setError(""); if (!/^\d{6,10}$/.test(employeeNo)) return setError("请输入 6 至 10 位员工号"); setBusy(true); try { const result = await login(employeeNo, password); if (result.requires_password_change) return setError("请先在业务系统完成首次密码修改，再登录日志系统。"); setToken(result.access_token); router.replace(search.get("next") || "/runs"); } catch (cause) { setError(cause instanceof ApiError ? cause.message : "登录失败，请稍后重试"); } finally { setBusy(false); } }
  return <main className="login-page"><section className="login-visual"><div className="login-brand"><span><Activity size={20} /></span><div><strong>法律 AGENT</strong><small>运行审计中心</small></div></div><div className="login-copy"><span className="kicker light">OBSERVABILITY & AUDIT</span><h1>让每一次调用<br />都有迹可循</h1><p>通过请求编号关联用户、会话、模型与工具调用，在保护案件隐私的前提下快速定位运行问题。</p><div className="trust-row"><span><ShieldCheck size={16} />管理员专用</span><span><Fingerprint size={16} />全链路追踪</span></div></div><p className="login-foot">仅展示经过脱敏的运行元数据 · 不记录模型隐藏推理</p></section><section className="login-panel"><form className="login-card" onSubmit={submit}><span className="kicker">ADMIN SIGN IN</span><h2>登录运行审计中心</h2><p>使用法律工作台的管理员员工账号</p><label><span>员工号</span><div className="input-shell"><IdCard size={18} /><input value={employeeNo} onChange={(e) => setEmployeeNo(e.target.value.replace(/\D/g, "").slice(0, 10))} placeholder="请输入 6～10 位员工号" autoComplete="username" /></div></label><label><span>密码</span><div className="input-shell"><LockKeyhole size={18} /><input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="请输入当前密码" autoComplete="current-password" /></div></label>{error && <div className="alert" role="alert">{error}</div>}<button className="primary-button" disabled={busy}>{busy ? "正在验证…" : "进入审计中心"}<span>→</span></button>{isDemoMode() && <div className="demo-note"><strong>演示模式</strong><span>已预填演示管理员账号；不会向中台发送登录信息。</span></div>}<small className="security-note"><ShieldCheck size={14} />前端权限判断仅控制界面，中台仍会验证管理员角色。</small></form></section></main>;
}
