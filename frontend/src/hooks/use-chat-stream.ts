"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SseEvent, ToolActivity } from "@/lib/api/contracts";
import { streamChat } from "@/lib/api/chat";
import { ApiError } from "@/lib/api/client";

export type StreamStatus = "idle" | "connecting" | "generating" | "completed" | "failed" | "cancelled";

export function useChatStream(onSettled: () => void) {
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [text, setText] = useState("");
  const [tools, setTools] = useState<ToolActivity[]>([]);
  const [error, setError] = useState("");
  const controllerRef = useRef<AbortController | null>(null);
  const pendingRef = useRef("");
  const frameRef = useRef<number | null>(null);

  const flush = useCallback(() => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
    if (!pendingRef.current) return;
    const next = pendingRef.current;
    pendingRef.current = "";
    setText((current) => current + next);
  }, []);

  const scheduleFlush = useCallback(() => {
    if (frameRef.current !== null) return;
    frameRef.current = requestAnimationFrame(flush);
  }, [flush]);

  const handleEvent = useCallback((event: SseEvent) => {
    switch (event.event) {
      case "run.started": setStatus("generating"); break;
      case "text.delta": pendingRef.current += String(event.data.delta ?? ""); scheduleFlush(); break;
      case "tool.started": {
        const id = String(event.data.toolCallId ?? Date.now());
        const name = String(event.data.toolName ?? "legal_search");
        setTools((items) => [...items.filter((item) => item.id !== id), { id, name, status: "running" }]);
        break;
      }
      case "tool.completed": {
        const id = String(event.data.toolCallId ?? "");
        setTools((items) => items.map((item) => item.id === id ? { ...item, status: event.data.isError ? "failed" : "completed" } : item));
        break;
      }
      case "run.completed": flush(); setStatus("completed"); break;
      case "run.failed": flush(); setError(String(event.data.message ?? "生成失败，请稍后重试")); setStatus("failed"); break;
      default: break;
    }
  }, [flush, scheduleFlush]);

  const start = useCallback(async (input: { session_id: string; prompt: string; active_case_id: string | null }) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    pendingRef.current = "";
    setText(""); setTools([]); setError(""); setStatus("connecting");
    try {
      await streamChat(input, controller.signal, handleEvent);
    } catch (cause) {
      flush();
      if (controller.signal.aborted) setStatus("cancelled");
      else {
        setStatus("failed");
        setError(cause instanceof ApiError ? cause.message : cause instanceof Error && cause.message === "STREAM_INTERRUPTED" ? "网络连接中断，当前进度已保留" : "暂时无法完成生成，请稍后重试");
      }
    } finally {
      controllerRef.current = null;
      onSettled();
    }
  }, [flush, handleEvent, onSettled]);

  const stop = useCallback(() => { controllerRef.current?.abort(); flush(); setStatus("cancelled"); }, [flush]);
  const reset = useCallback(() => { setStatus("idle"); setText(""); setTools([]); setError(""); pendingRef.current = ""; }, []);

  useEffect(() => () => { controllerRef.current?.abort(); if (frameRef.current !== null) cancelAnimationFrame(frameRef.current); }, []);
  return { status, text, tools, error, start, stop, reset };
}
