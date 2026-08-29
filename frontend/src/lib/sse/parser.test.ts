import { describe, expect, it } from "vitest";
import { parseSseBlock, parseSseStream } from "./parser";

function chunkedStream(chunks: Uint8Array[]) {
  return new ReadableStream<Uint8Array>({ start(controller) { chunks.forEach((chunk) => controller.enqueue(chunk)); controller.close(); } });
}

describe("SSE parser", () => {
  it("parses named events and multiline data", () => {
    const event = parseSseBlock('event: text.delta\ndata: {"delta":\ndata: "法"}');
    expect(event).toEqual({ event: "text.delta", data: { delta: "法" } });
  });

  it("ignores heartbeat comments", () => {
    expect(parseSseBlock(": ping")).toBeNull();
  });

  it("handles event and UTF-8 boundaries across arbitrary chunks", async () => {
    const bytes = new TextEncoder().encode('event: text.delta\r\ndata: {"delta":"中华人民共和国"}\r\n\r\nevent: run.completed\ndata: {"requestId":"1"}\n\n');
    const stream = chunkedStream([bytes.slice(0, 13), bytes.slice(13, 29), bytes.slice(29, 43), bytes.slice(43)]);
    const events = [];
    for await (const event of parseSseStream(stream)) events.push(event);
    expect(events).toHaveLength(2);
    expect(events[0].data.delta).toBe("中华人民共和国");
    expect(events[1].event).toBe("run.completed");
  });

  it("rejects invalid JSON", () => {
    expect(() => parseSseBlock("event: text.delta\ndata: nope")).toThrow();
  });
});
