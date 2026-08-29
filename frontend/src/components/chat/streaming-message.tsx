import { AlertCircle, Bot, CheckCircle2, LoaderCircle, RotateCcw, Square } from "lucide-react";
import type { ToolActivity } from "@/lib/api/contracts";
import type { StreamStatus } from "@/hooks/use-chat-stream";
import { Button } from "@/components/ui/button";
import { LegalMarkdown } from "@/components/legal/legal-markdown";

export function StreamingMessage({ status, text, tools, error, onStop, onRetry }: { status: StreamStatus; text: string; tools: ToolActivity[]; error: string; onStop: () => void; onRetry: () => void }) {
  if (status === "idle") return null;
  return (
    <article className="message-row message-assistant streaming-row" aria-live={['completed', 'failed', 'cancelled'].includes(status) ? "polite" : "off"}>
      <div className="message-avatar"><Bot size={17} /></div>
      <div className="message-content">
        <div className="message-meta"><strong>衡法智策</strong><span>{status === "connecting" ? "正在连接" : status === "generating" ? "正在生成" : status === "cancelled" ? "已停止" : ""}</span></div>
        {tools.length > 0 && <div className="tool-stack">{tools.map((tool) => <div className={`tool-item tool-${tool.status}`} key={tool.id}>{tool.status === "running" ? <LoaderCircle className="spin" size={15} /> : tool.status === "completed" ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}<span>{tool.status === "running" ? "正在检索相关法律资料" : tool.status === "completed" ? "已完成法律资料检索" : "法律资料检索未完成"}</span><small>{tool.name}</small></div>)}</div>}
        {!text && status === "connecting" && <div className="thinking"><span /><span /><span /></div>}
        {text && <LegalMarkdown>{text}</LegalMarkdown>}
        {status === "generating" && <Button variant="secondary" size="sm" onClick={onStop}><Square size={13} />停止生成</Button>}
        {status === "failed" && <div className="stream-error"><AlertCircle size={16} /><span>{error}</span><Button variant="secondary" size="sm" onClick={onRetry}><RotateCcw size={13} />重新生成</Button></div>}
        {status === "cancelled" && <div className="stream-notice"><Square size={13} />已发送停止请求，当前可见内容已保留</div>}
      </div>
    </article>
  );
}
