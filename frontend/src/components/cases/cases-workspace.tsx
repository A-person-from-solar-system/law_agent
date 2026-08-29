"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, BriefcaseBusiness, FileText, LoaderCircle, MoreHorizontal, Plus, Search, Trash2 } from "lucide-react";
import { AppSidebar } from "@/components/workspace/app-sidebar";
import { Button } from "@/components/ui/button";
import { CaseFormDialog } from "./case-form-dialog";
import { createCase, deleteCase, listCases, updateCase } from "@/lib/api/cases";
import type { CaseInput, UserCase } from "@/lib/api/contracts";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { formatRelativeTime } from "@/lib/utils";

export function CasesWorkspace() {
  const ready = useRequireAuth(); const client = useQueryClient();
  const [query, setQuery] = useState(""); const [showArchived, setShowArchived] = useState(false); const [dialogOpen, setDialogOpen] = useState(false); const [editing, setEditing] = useState<UserCase | null>(null);
  const cases = useQuery({ queryKey: ["cases"], queryFn: listCases, enabled: ready });
  const refresh = () => client.invalidateQueries({ queryKey: ["cases"] });
  const save = useMutation({ mutationFn: ({ item, input }: { item: UserCase | null; input: CaseInput }) => item ? updateCase(item.id, input) : createCase(input), onSuccess: async () => { await refresh(); setDialogOpen(false); setEditing(null); } });
  const archive = useMutation({ mutationFn: ({ id, status }: { id: string; status: string }) => updateCase(id, { status }), onSuccess: refresh });
  const remove = useMutation({ mutationFn: deleteCase, onSuccess: refresh });
  const filtered = useMemo(() => (cases.data ?? []).filter((item) => (showArchived || item.status === "active") && `${item.name} ${item.summary}`.toLowerCase().includes(query.toLowerCase())), [cases.data, query, showArchived]);
  function createNew() { setEditing(null); setDialogOpen(true); }
  function edit(item: UserCase) { setEditing(item); setDialogOpen(true); }
  function removeItem(item: UserCase) { if (window.confirm(`确定删除“${item.name}”吗？删除后将无法在对话中引用。`)) remove.mutate(item.id); }
  if (!ready) return <div className="full-loader"><LoaderCircle className="spin" /><span>正在验证登录状态</span></div>;
  return <main className="app-shell"><AppSidebar section="cases" /><section className="cases-main"><header className="cases-header"><div><span className="eyebrow">CASE MANAGEMENT</span><h1>案件库</h1><p>集中维护案件事实，在对话中通过 @ 精准引用。</p></div><Button onClick={createNew}><Plus size={17} />录入新案件</Button></header><div className="cases-toolbar"><label className="case-search"><Search size={17} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="按案件名称或概要搜索" /></label><label className="archive-toggle"><input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />显示已归档案件</label></div>{cases.isLoading ? <div className="content-loader"><LoaderCircle className="spin" />正在加载案件</div> : filtered.length ? <div className="case-grid">{filtered.map((item) => <article className="case-card" key={item.id}><div className="case-card-top"><span className={`case-status status-${item.status}`}>{item.status === "active" ? "进行中" : "已归档"}</span><button className="icon-subtle" aria-label="案件操作"><MoreHorizontal size={18} /></button></div><div className="case-icon"><BriefcaseBusiness size={20} /></div><h2>{item.name}</h2><p>{item.summary || "尚未填写案件概要"}</p><div className="case-facts"><span><FileText size={13} />{Object.keys(item.structured_facts).length} 项结构化事实</span><span>更新于 {formatRelativeTime(item.updated_at)}</span></div><div className="case-actions"><Button variant="secondary" size="sm" onClick={() => edit(item)}>查看与编辑</Button><button onClick={() => archive.mutate({ id: item.id, status: item.status === "active" ? "archived" : "active" })}><Archive size={14} />{item.status === "active" ? "归档" : "恢复"}</button><button className="danger-link" onClick={() => removeItem(item)}><Trash2 size={14} />删除</button></div></article>)}</div> : <div className="empty-cases"><div className="case-icon"><BriefcaseBusiness size={25} /></div><h2>{query ? "没有匹配的案件" : "建立您的案件库"}</h2><p>{query ? "尝试调整关键词或显示已归档案件。" : "录入案情后，可在法律咨询中使用 @ 快速引用。"}</p>{!query && <Button onClick={createNew}><Plus size={16} />录入第一个案件</Button>}</div>}</section>{dialogOpen && <CaseFormDialog open item={editing} busy={save.isPending} onOpenChange={setDialogOpen} onSubmit={(input) => save.mutateAsync({ item: editing, input }).then(() => undefined)} />}</main>;
}
