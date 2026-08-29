"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenText, BriefcaseBusiness, LogOut, Menu, MessageSquareText, Plus, Scale, Trash2, X } from "lucide-react";
import { useState } from "react";
import { createSession, deleteSession, listSessions } from "@/lib/api/sessions";
import { getMe } from "@/lib/api/auth";
import { clearToken } from "@/lib/auth/token-store";
import { formatRelativeTime } from "@/lib/utils";

export function AppSidebar({ activeSessionId, section = "chat" }: { activeSessionId?: string; section?: "chat" | "cases" }) {
  const router = useRouter();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: listSessions });
  const me = useQuery({ queryKey: ["me"], queryFn: getMe });
  const create = useMutation({ mutationFn: () => createSession(), onSuccess: async (item) => { await client.invalidateQueries({ queryKey: ["sessions"] }); router.push(`/chat/${item.id}`); setOpen(false); } });
  const remove = useMutation({ mutationFn: deleteSession, onSuccess: async (_, id) => { await client.invalidateQueries({ queryKey: ["sessions"] }); if (id === activeSessionId) router.push("/chat"); } });
  function logout() { clearToken(); client.clear(); router.replace("/login"); }
  function confirmDelete(event: React.MouseEvent, id: string) { event.preventDefault(); event.stopPropagation(); if (window.confirm("确定删除这个会话吗？历史记录将不再显示。")) remove.mutate(id); }

  return (
    <>
      <button className="mobile-menu" onClick={() => setOpen(true)} aria-label="打开导航"><Menu size={20} /></button>
      {open && <button className="sidebar-backdrop" onClick={() => setOpen(false)} aria-label="关闭导航" />}
      <aside className={`sidebar app-sidebar ${open ? "sidebar-open" : ""}`}>
        <button className="sidebar-close" onClick={() => setOpen(false)} aria-label="关闭导航"><X size={20} /></button>
        <Link className="brand" href="/chat"><span className="brand-mark"><Scale size={19} /></span><div><strong>衡法智策</strong><small>政企法律智能助手</small></div></Link>
        <button className="new-chat" onClick={() => create.mutate()} disabled={create.isPending}><Plus size={17} /> 发起新咨询</button>
        <div className="nav-label">最近会话</div>
        <nav className="session-list" aria-label="会话列表">
          {sessions.isLoading && <div className="sidebar-skeleton"><span /><span /><span /></div>}
          {sessions.data?.map((item) => <Link key={item.id} href={`/chat/${item.id}`} onClick={() => setOpen(false)} className={`session-row ${item.id === activeSessionId ? "session-row-active" : ""}`}><span><MessageSquareText size={14} />{item.title}</span><small>{formatRelativeTime(item.updated_at)}</small><button className="session-delete" onClick={(event) => confirmDelete(event, item.id)} aria-label={`删除会话 ${item.title}`}><Trash2 size={13} /></button></Link>)}
          {!sessions.isLoading && !sessions.data?.length && <p className="sidebar-empty">还没有会话，开始第一次法律咨询吧。</p>}
        </nav>
        <div className="sidebar-bottom">
          <Link className={`sidebar-link ${section === "cases" ? "sidebar-link-active" : ""}`} href="/cases"><BriefcaseBusiness size={17} />案件库</Link>
          <div className="sidebar-link sidebar-link-muted"><BookOpenText size={17} />法律资源 <small>由 Agent 调用</small></div>
          <div className="account-row"><div className="account-avatar">{me.data?.name.slice(0, 1) ?? "员"}</div><div><strong>{me.data?.name ?? "当前员工"}</strong><small>{me.data ? `${me.data.employee_no} · ${me.data.role === "admin" ? "管理员" : "员工"}` : "企业账户"}</small></div><button onClick={logout} aria-label="退出登录"><LogOut size={16} /></button></div>
        </div>
      </aside>
    </>
  );
}
