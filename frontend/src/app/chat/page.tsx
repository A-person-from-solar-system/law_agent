"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { LoaderCircle, Scale } from "lucide-react";
import { listSessions } from "@/lib/api/sessions";
import { useRequireAuth } from "@/hooks/use-require-auth";
import { AppSidebar } from "@/components/workspace/app-sidebar";

export default function ChatIndexPage() {
  const ready = useRequireAuth(); const router = useRouter();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: listSessions, enabled: ready });
  useEffect(() => { if (sessions.data?.[0]) router.replace(`/chat/${sessions.data[0].id}`); }, [router, sessions.data]);
  if (!ready || sessions.isLoading || sessions.data?.length) return <div className="full-loader"><LoaderCircle className="spin" /><span>正在进入法律工作台</span></div>;
  return <main className="app-shell"><AppSidebar /><section className="workspace empty-workspace"><div className="welcome-card"><div className="seal"><Scale size={27} /></div><p className="eyebrow">LEGAL INTELLIGENCE</p><h2>建立您的第一场法律咨询</h2><p>点击左侧“发起新咨询”，随后可以使用 @ 绑定案件并开始分析。</p></div></section></main>;
}
