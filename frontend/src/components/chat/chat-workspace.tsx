"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ChevronUp, FileText, LoaderCircle, Pencil, Scale } from "lucide-react";
import { AppSidebar } from "@/components/workspace/app-sidebar";
import { ChatComposer } from "./chat-composer";
import { MessageBubble } from "./message-bubble";
import { StreamingMessage } from "./streaming-message";
import { Button } from "@/components/ui/button";
import { listCases } from "@/lib/api/cases";
import { getSession, listMessages, updateSession } from "@/lib/api/sessions";
import type { ChatMessage, MessagePage, UserCase } from "@/lib/api/contracts";
import { useChatStream } from "@/hooks/use-chat-stream";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { ApiError } from "@/lib/api/client";

const prompts = ["梳理本案争议焦点", "分析合同违约责任", "检索相关法律依据"];

export function ChatWorkspace({ sessionId }: { sessionId: string }) {
  const ready = useRequireAuth();
  const client = useQueryClient();
  const session = useQuery({ queryKey: ["session", sessionId], queryFn: () => getSession(sessionId), enabled: ready && Boolean(sessionId) });
  const cases = useQuery({ queryKey: ["cases"], queryFn: listCases, enabled: ready });
  const messages = useInfiniteQuery<MessagePage>({
    queryKey: ["messages", sessionId],
    queryFn: ({ pageParam }) => listMessages(sessionId, pageParam as number | undefined),
    initialPageParam: undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: ready && Boolean(sessionId),
  });
  const localMessageId = useId();
  const [localUser, setLocalUser] = useState<ChatMessage | null>(null);
  const [lastPrompt, setLastPrompt] = useState("");
  const [notice, setNotice] = useState("");
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [nearBottom, setNearBottom] = useState(true);
  const beforeLoadHeight = useRef(0);

  const selectedCase = cases.data?.find((item) => item.id === session.data?.active_case_id) ?? null;

  const settled = useCallback(() => {
    void client.invalidateQueries({ queryKey: ["messages", sessionId] });
    void client.invalidateQueries({ queryKey: ["sessions"] });
    window.setTimeout(() => setLocalUser(null), 350);
  }, [client, sessionId]);
  const stream = useChatStream(settled);

  const history = useMemo(() => {
    const items = [...(messages.data?.pages ?? [])].reverse().flatMap((page) => page.items);
    return items.filter((item) => item.role === "user" || item.role === "assistant");
  }, [messages.data]);

  useEffect(() => {
    if (!nearBottom) return;
    const node = scrollerRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [history.length, localUser, stream.text, stream.tools.length, nearBottom]);

  useEffect(() => {
    const node = scrollerRef.current;
    if (!node || !beforeLoadHeight.current) return;
    node.scrollTop += node.scrollHeight - beforeLoadHeight.current;
    beforeLoadHeight.current = 0;
  }, [messages.data?.pages.length]);

  const rename = useMutation({ mutationFn: (title: string) => updateSession(sessionId, { title }), onSuccess: (item) => { client.setQueryData(["session", sessionId], item); void client.invalidateQueries({ queryKey: ["sessions"] }); } });

  async function changeCase(item: UserCase | null) {
    setNotice("");
    try {
      const updated = await updateSession(sessionId, { active_case_id: item?.id ?? null });
      client.setQueryData(["session", sessionId], updated); void client.invalidateQueries({ queryKey: ["sessions"] });
    } catch (cause) { setNotice(cause instanceof ApiError ? cause.message : "案件绑定失败，请重试"); throw cause; }
  }

  function send(prompt: string) {
    setLastPrompt(prompt); setNotice("");
    setLocalUser({ id: `local:${localMessageId}`, role: "user", content: prompt, status: "completed", metadata: {}, created_at: "" });
    void stream.start({ session_id: sessionId, prompt, active_case_id: selectedCase?.id ?? null });
  }
  function retry() { if (lastPrompt) void stream.start({ session_id: sessionId, prompt: lastPrompt, active_case_id: selectedCase?.id ?? null }); }
  function editTitle() { const title = window.prompt("修改会话标题", session.data?.title ?? ""); if (title?.trim()) rename.mutate(title.trim()); }
  function handleScroll() { const node = scrollerRef.current; if (!node) return; setNearBottom(node.scrollHeight - node.scrollTop - node.clientHeight < 90); }
  async function loadOlder() { const node = scrollerRef.current; if (node) beforeLoadHeight.current = node.scrollHeight; await messages.fetchNextPage(); }

  if (!ready) return <div className="full-loader"><LoaderCircle className="spin" /><span>正在验证登录状态</span></div>;
  return (
    <main className="app-shell">
      <AppSidebar activeSessionId={sessionId} />
      <section className="workspace">
        <header className="workspace-header">
          <div className="header-title"><span className="eyebrow">法律咨询工作台</span><h1>{session.data?.title ?? "法律咨询"}<button onClick={editTitle} aria-label="修改会话标题"><Pencil size={13} /></button></h1></div>
          {selectedCase ? <div className="case-badge"><span>关联案件</span><FileText size={14} />{selectedCase.name}</div> : <div className="case-badge case-badge-empty"><span>未关联案件</span>在输入框键入 @ 选择</div>}
        </header>
        <div className="conversation chat-conversation" ref={scrollerRef} onScroll={handleScroll}>
          <div className="message-column">
            {messages.hasNextPage && <Button className="load-older" variant="ghost" size="sm" onClick={() => void loadOlder()} disabled={messages.isFetchingNextPage}>{messages.isFetchingNextPage ? <LoaderCircle className="spin" size={14} /> : <ChevronUp size={14} />}加载更早消息</Button>}
            {messages.isLoading && <div className="message-loading"><LoaderCircle className="spin" />正在加载历史消息</div>}
            {!messages.isLoading && history.length === 0 && !localUser && stream.status === "idle" && <div className="welcome-card"><div className="seal"><Scale size={27} /></div><p className="eyebrow">LEGAL INTELLIGENCE</p><h2>让法律判断，有据可循</h2><p>基于案件事实与现行法律规范，辅助梳理争议焦点、责任边界与处置路径。</p><div className="suggestions">{prompts.map((prompt) => <button key={prompt} onClick={() => send(prompt)}>{prompt}<span>↗</span></button>)}</div></div>}
            {history.map((message) => <MessageBubble key={message.id} message={message} />)}
            {localUser && <MessageBubble message={localUser} />}
            <StreamingMessage status={stream.status} text={stream.text} tools={stream.tools} error={stream.error} onStop={stream.stop} onRetry={retry} />
            {notice && <div className="inline-notice" role="alert">{notice}</div>}
          </div>
          {!nearBottom && <button className="scroll-bottom" onClick={() => { const node = scrollerRef.current; if (node) node.scrollTo({ top: node.scrollHeight, behavior: "smooth" }); }}><ArrowDown size={16} />回到底部</button>}
        </div>
        <ChatComposer sessionId={sessionId} cases={cases.data ?? []} selectedCase={selectedCase} status={stream.status} onCaseChange={changeCase} onSend={send} onStop={stream.stop} />
      </section>
    </main>
  );
}
