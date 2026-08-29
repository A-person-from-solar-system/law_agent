"use client";

import { useParams } from "next/navigation";
import { ChatWorkspace } from "@/components/chat/chat-workspace";

export default function SessionChatPage() {
  const params = useParams<{ sessionId: string }>();
  return <ChatWorkspace sessionId={params.sessionId} />;
}
