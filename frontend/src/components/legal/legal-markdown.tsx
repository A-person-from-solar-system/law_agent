"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy } from "lucide-react";
import { useState } from "react";

export function LegalMarkdown({ children }: { children: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(children);
    setCopied(true); window.setTimeout(() => setCopied(false), 1500);
  }
  return (
    <div className="legal-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children: label }) => <a href={href} target="_blank" rel="noopener noreferrer">{label}</a>,
          table: ({ children: tableChildren }) => <div className="table-scroll"><table>{tableChildren}</table></div>,
        }}
      >{children}</ReactMarkdown>
      <button className="copy-answer" onClick={copy} aria-label="复制回答"><Copy size={14} />{copied ? "已复制" : "复制"}</button>
    </div>
  );
}
