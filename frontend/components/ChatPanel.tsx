"use client";

import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import type { Message } from "@/types/chat";
import { HydrationSkeleton } from "./HydrationSkeleton";
import { MessageBubble } from "./MessageBubble";

const SUGGESTIONS = [
  "Forecast Outerwear demand next month",
  "Which SKUs are overstocked?",
  "Slowest-moving products last 90 days",
];

function EmptyState({ onSelect }: { onSelect: (text: string) => void }) {
  return (
    <div style={{ margin: "auto", textAlign: "center", padding: "24px" }}>
      <div
        style={{
          width: "26px",
          height: "26px",
          margin: "0 auto 10px",
          borderRadius: "50%",
          border: "1px solid var(--ds-border-strong)",
          color: "var(--ds-blue-400)",
          display: "grid",
          placeItems: "center",
          fontSize: "13px",
        }}
      >
        AI
      </div>
      <p
        style={{
          fontSize: "12px",
          color: "var(--ds-gray-700)",
          marginBottom: "14px",
        }}
      >
        Ask anything about your operations
      </p>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "6px",
          justifyContent: "center",
        }}
      >
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => onSelect(suggestion)}
            style={{
              padding: "5px 12px",
              background: "var(--ds-gray-100)",
              border: "1px solid var(--ds-border)",
              borderRadius: "20px",
              fontSize: "11px",
              color: "var(--ds-gray-800)",
              cursor: "pointer",
              fontFamily: "var(--font-geist-sans)",
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

type Props = {
  messages: Message[];
  isStreaming: boolean;
  isHydrating: boolean;
  onSubmit: (text: string) => void;
  onWritebackDecision: (actionId: string, decision: "approve" | "reject") => void;
};

export function ChatPanel({
  messages,
  isStreaming,
  isHydrating,
  onSubmit,
  onWritebackDecision,
}: Props) {
  const [input, setInput] = useState("");
  const [hasFocused, setHasFocused] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  // Auto-resize textarea
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [input]);

  // Auto-focus on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Smart auto-scroll: only when near bottom or user just submitted
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    const shouldScroll =
      isNearBottomRef.current || lastMessage?.role === "user";
    if (shouldScroll) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  function handleScroll() {
    const el = scrollContainerRef.current;
    if (!el) return;
    isNearBottomRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  }

  function handleSubmit() {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");
    onSubmit(text);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  function handleSuggestion(text: string) {
    setInput(text);
    inputRef.current?.focus();
  }

  const disabled = isStreaming || isHydrating;
  const showCounter = input.length >= 3200;
  const counterColor =
    input.length >= 3800 ? "var(--ds-amber-400)" : "var(--ds-gray-700)";
  const showHint = hasFocused && input.length > 0;

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        minWidth: 0,
      }}
    >
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "20px",
          display: "flex",
          flexDirection: "column",
          gap: "14px",
        }}
      >
        {isHydrating ? (
          <HydrationSkeleton />
        ) : messages.length === 0 ? (
          <EmptyState onSelect={handleSuggestion} />
        ) : (
          messages.map((message, index) => {
            const prevMsg = index > 0 ? messages[index - 1] : undefined;
            const onRetry =
              message.status === "error" && prevMsg?.role === "user"
                ? () => onSubmit(prevMsg.text)
                : undefined;
            return (
              <MessageBubble
                key={message.id}
                message={message}
                onWritebackDecision={onWritebackDecision}
                onRetry={onRetry}
              />
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      <div
        style={{
          borderTop: "1px solid var(--ds-border)",
          padding: "10px 16px",
          background: "var(--ds-background-100)",
          flexShrink: 0,
        }}
      >
        <textarea
          ref={inputRef}
          value={input}
          rows={1}
          className="no-scrollbar"
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            setHasFocused(true);
          }}
          disabled={disabled}
          placeholder="Ask about inventory, sales, or forecasts..."
          style={{
            display: "block",
            width: "100%",
            minHeight: "36px",
            maxHeight: "130px",
            background: "var(--ds-gray-100)",
            border: "1px solid var(--ds-border)",
            borderRadius: "8px",
            padding: "8px 12px",
            fontSize: "13px",
            color: "var(--ds-gray-900)",
            fontFamily: "var(--font-geist-sans)",
            outline: "none",
            opacity: disabled ? 0.5 : 1,
            resize: "none",
            overflowY: "auto",
            lineHeight: "1.5",
            boxSizing: "border-box",
          }}
        />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginTop: "6px",
            minHeight: "24px",
          }}
        >
          <span
            style={{
              fontSize: "10px",
              color: "var(--ds-gray-700)",
              opacity: showHint ? 1 : 0,
              transition: "opacity 0.15s",
            }}
          >
            Shift+Enter for new line
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {showCounter && (
              <span style={{ fontSize: "10px", color: counterColor }}>
                {input.length} / 4000
              </span>
            )}
            <button
              onClick={handleSubmit}
              disabled={disabled || !input.trim()}
              style={{
                background:
                  disabled || !input.trim()
                    ? "var(--ds-gray-200)"
                    : "var(--ds-gray-1000)",
                color:
                  disabled || !input.trim() ? "var(--ds-gray-700)" : "#000",
                border: "none",
                borderRadius: "8px",
                padding: "6px 16px",
                fontSize: "13px",
                fontWeight: 500,
                cursor: disabled || !input.trim() ? "not-allowed" : "pointer",
                whiteSpace: "nowrap",
                fontFamily: "var(--font-geist-sans)",
                transition: "background 0.15s, color 0.15s",
              }}
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
