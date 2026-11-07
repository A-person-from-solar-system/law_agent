"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Activity, BarChart3, BookOpen, LogOut, Menu, ScrollText, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { clearToken, isDemoMode } from "@/lib/auth";
import type { User } from "@/lib/contracts";

export function AppShell({ user, children }: { user: User; children: React.ReactNode }) {
  const pathname = usePathname(); const router = useRouter(); const [open, setOpen] = useState(false);
  const logout = () => { clearToken(); router.replace("/login"); };
  return <div className="app-layout"><button className="mobile-nav" onClick={() => setOpen(true)} aria-label="打开导航"><Menu /></button>{open && <button className="nav-backdrop" onClick={() => setOpen(false)} aria-label="关闭导航" />}<aside className={`side-nav ${open ? "open" : ""}`}><button className="nav-close" onClick={() => setOpen(false)}><X /></button><div className="nav-brand"><span><Activity size={20} /></span><div><strong>法律 AGENT</strong><small>运行审计中心</small></div></div><div className="nav-context"><span className={`live-dot ${isDemoMode() ? "amber" : ""}`} /><div><strong>{isDemoMode() ? "演示数据" : "审计服务正常"}</strong><small>{isDemoMode() ? "未连接生产日志" : "最近更新：刚刚"}</small></div></div><nav><p>监控与审计</p><Link className={pathname.startsWith("/runs") ? "active" : ""} href="/runs"><ScrollText />运行日志</Link><Link className={pathname.startsWith("/metrics") ? "active" : ""} href="/metrics"><BarChart3 />指标概览</Link><p>相关系统</p><a href="http://localhost:3000" target="_blank" rel="noreferrer"><BookOpen />法律工作台</a></nav><div className="privacy-note"><ShieldCheck /><p><strong>安全内容模式</strong><span>METADATA</span></p><small>仅展示脱敏参数摘要、来源 ID 与运行统计。</small></div><div className="nav-user"><div>{user.name.slice(0, 1)}</div><p><strong>{user.name}</strong><small>{user.employee_no} · 管理员</small></p><button onClick={logout} title="退出登录"><LogOut /></button></div></aside><main className="main-area">{children}</main></div>;
}
