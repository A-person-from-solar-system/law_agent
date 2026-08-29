"use client";

import { CornerDownLeft, Send, Square, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { UserCase } from "@/lib/api/contracts";
import type { StreamStatus } from "@/hooks/use-chat-stream";

export function ChatComposer({ sessionId, cases, selectedCase, status, onCaseChange, onSend, onStop }: { sessionId: string; cases: UserCase[]; selectedCase: UserCase | null; status: StreamStatus; onCaseChange: (item: UserCase | null) => Promise<void>; onSend: (prompt: string) => void; onStop: () => void }) {
  const draftKey = `law-agent-draft:${sessionId}`;
  const [value, setValue] = useState(() => typeof window === "undefined" ? "" : window.sessionStorage.getItem(draftKey) ?? "");
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [caseBusy, setCaseBusy] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const busy = status === "connecting" || status === "generating";

  useEffect(() => { window.sessionStorage.setItem(draftKey, value); }, [draftKey, value]);
  const matches = useMemo(() => cases.filter((item) => item.status === "active" && item.name.toLowerCase().includes(mentionQuery.toLowerCase())).slice(0, 8), [cases, mentionQuery]);

  function updateValue(next: string) {
    setValue(next);
    const cursor = textareaRef.current?.selectionStart ?? next.length;
    const prefix = next.slice(0, cursor);
    const match = prefix.match(/(?:^|\s)@([^\s@]*)$/);
    setMentionOpen(Boolean(match)); setMentionQuery(match?.[1] ?? ""); setActiveIndex(0);
  }
  async function chooseCase(item: UserCase) {
    setCaseBusy(true);
    try {
      await onCaseChange(item);
      setValue((current) => current.replace(/(?:^|\s)@[^\s@]*$/, (found) => found.startsWith(" ") ? " " : ""));
      setMentionOpen(false); textareaRef.current?.focus();
    } finally { setCaseBusy(false); }
  }
  function submit() {
    const prompt = value.trim();
    if (!prompt || busy) return;
    onSend(prompt); setValue(""); window.sessionStorage.removeItem(draftKey); setMentionOpen(false);
  }
  function keyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (mentionOpen && matches.length) {
      if (event.key === "ArrowDown") { event.preventDefault(); setActiveIndex((index) => (index + 1) % matches.length); return; }
      if (event.key === "ArrowUp") { event.preventDefault(); setActiveIndex((index) => (index - 1 + matches.length) % matches.length); return; }
      if (event.key === "Enter") { event.preventDefault(); void chooseCase(matches[activeIndex]); return; }
      if (event.key === "Escape") { event.preventDefault(); setMentionOpen(false); return; }
    }
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); }
  }

  return (
    <footer className="composer-wrap">
      <div className="composer-inner">
        {selectedCase && <div className="case-chip"><span>@</span>{selectedCase.name}<button onClick={() => void onCaseChange(null)} aria-label="移除案件"><X size={13} /></button></div>}
        <div className="composer-box" role="combobox" aria-expanded={mentionOpen} aria-controls="case-mention-listbox">
          {mentionOpen && <div id="case-mention-listbox" className="mention-popover" role="listbox" aria-label="选择案件"><div className="mention-title">引用案件 <small>输入名称筛选</small></div>{matches.map((item, index) => <button role="option" aria-selected={index === activeIndex} className={index === activeIndex ? "mention-active" : ""} key={item.id} onMouseDown={(event) => event.preventDefault()} onClick={() => void chooseCase(item)} disabled={caseBusy}><span>{item.name}</span><small>{item.summary || "暂无案件概要"}</small></button>)}{!matches.length && <p>没有匹配的有效案件</p>}</div>}
          <textarea ref={textareaRef} value={value} onChange={(event) => updateValue(event.target.value)} onKeyDown={keyDown} aria-label="法律问题" aria-autocomplete="list" placeholder="输入法律问题，使用 @ 引用案件…" rows={2} />
          <div className="composer-actions"><span><CornerDownLeft size={13} /> Enter 发送 · Shift + Enter 换行</span>{busy ? <button className="stop-button" onClick={onStop}><Square size={15} />停止</button> : <button className="send-button" onClick={submit} disabled={!value.trim()} aria-label="发送消息"><Send size={18} /></button>}</div>
        </div>
      </div>
      <p>AI 生成内容仅供辅助参考，请结合有效法律文本和专业意见复核</p>
    </footer>
  );
}
