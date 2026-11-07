import { AlertCircle, Bot, UserRound } from "lucide-react";
import type { ChatMessage } from "@/lib/api/contracts";
import { LegalMarkdown } from "@/components/legal/legal-markdown";

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (!['user', 'assistant'].includes(message.role)) return null;
  const assistant = message.role === "assistant";
  return (
    <article className={`message-row ${assistant ? "message-assistant" : "message-user"}`}>
      <div className="message-avatar">{assistant ? <Bot size={17} /> : <UserRound size={17} />}</div>
      <div className="message-content">
        <div className="message-meta"><strong>{assistant ? "法律知识问答智能体软件V1.0" : "您"}</strong><span>{message.status === "completed" ? "" : message.status === "cancelled" ? "已停止" : "生成失败"}</span></div>
        {message.content ? assistant ? <LegalMarkdown>{String(message.content)}</LegalMarkdown> : <p>{String(message.content)}</p> : <div className="message-empty"><AlertCircle size={15} /> 本次回答未能完成</div>}
      </div>
    </article>
  );
}
