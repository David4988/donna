import { useEffect, useRef } from "react";
import type { ChatMessage } from "../state/reducer";

export function Conversation({ messages }: { messages: ChatMessage[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ block: "end" }), [messages.length]);
  return (
    <section className="conversation" data-testid="conversation">
      {messages.length === 0 && <p className="muted">Say hello to DONNA.</p>}
      {messages.map((m) => (
        <div key={m.id} className={`msg msg-${m.role}`}>
          <span className="who">{m.role === "user" ? "You" : m.role === "assistant" ? "DONNA" : ""}</span>
          <span>{m.text}</span>
        </div>
      ))}
      <div ref={end} />
    </section>
  );
}
