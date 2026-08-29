"use client";

import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { CaseInput, UserCase } from "@/lib/api/contracts";

export function CaseFormDialog({ open, item, onOpenChange, onSubmit, busy }: { open: boolean; item: UserCase | null; onOpenChange: (open: boolean) => void; onSubmit: (input: CaseInput) => Promise<void>; busy: boolean }) {
  const [name, setName] = useState(item?.name ?? ""); const [summary, setSummary] = useState(item?.summary ?? ""); const [content, setContent] = useState(item?.content ?? ""); const [facts, setFacts] = useState(JSON.stringify(item?.structured_facts ?? {}, null, 2)); const [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError("");
    if (!name.trim()) return setError("请输入案件名称");
    let structured: unknown;
    try { structured = JSON.parse(facts || "{}"); } catch { return setError("结构化事实必须是合法 JSON"); }
    if (!structured || typeof structured !== "object" || Array.isArray(structured)) return setError("结构化事实必须是 JSON 对象");
    await onSubmit({ name: name.trim(), summary: summary.trim(), content: content.trim(), structured_facts: structured as Record<string, unknown> });
  }
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="case-dialog"><DialogTitle>{item ? "编辑案件" : "录入新案件"}</DialogTitle><DialogDescription>案件内容仅用于您明确绑定后的法律分析，请避免录入无关敏感信息。</DialogDescription><form className="case-form" onSubmit={submit}><label className="field"><span>案件名称 *</span><div><input value={name} onChange={(e) => setName(e.target.value)} maxLength={500} placeholder="例如：华辰设备采购案" /></div></label><label className="field"><span>案件概要</span><textarea value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={20000} placeholder="简要说明当事人、案由与核心争议" rows={3} /></label><label className="field"><span>详细案情</span><textarea value={content} onChange={(e) => setContent(e.target.value)} maxLength={200000} placeholder="填写事实经过、合同约定、履行情况等" rows={7} /></label><label className="field"><span>结构化事实（JSON）</span><textarea className="code-input" value={facts} onChange={(e) => setFacts(e.target.value)} rows={5} spellCheck={false} /></label>{error && <div className="form-error" role="alert">{error}</div>}<div className="dialog-actions"><Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>取消</Button><Button disabled={busy} type="submit">{busy && <LoaderCircle className="spin" size={16} />}{item ? "保存修改" : "创建案件"}</Button></div></form></DialogContent></Dialog>;
}
