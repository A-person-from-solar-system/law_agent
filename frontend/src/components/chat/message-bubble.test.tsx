import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MessageBubble } from "./message-bubble";

describe("MessageBubble", () => {
  it("renders markdown without executing raw HTML", () => {
    render(<MessageBubble message={{ id: "1", role: "assistant", content: "**结论** <script>alert(1)</script>", status: "completed", metadata: {}, created_at: new Date().toISOString() }} />);
    expect(screen.getByText("结论")).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
  });

  it("filters internal roles", () => {
    const { container } = render(<MessageBubble message={{ id: "2", role: "tool", content: "secret", status: "completed", metadata: {}, created_at: new Date().toISOString() }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
