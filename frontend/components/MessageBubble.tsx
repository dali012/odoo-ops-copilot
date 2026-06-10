import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import type { Message } from "@/types/chat";
import { ToolTrace } from "./ToolTrace";

function AssistantMarkdown({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      components={{
        p: ({ children }) => <p className="assistant-markdown-p">{children}</p>,
        ul: ({ children }) => <ul className="assistant-markdown-list">{children}</ul>,
        ol: ({ children }) => <ol className="assistant-markdown-list">{children}</ol>,
        li: ({ children }) => <li className="assistant-markdown-li">{children}</li>,
        table: ({ children }) => (
          <div className="assistant-markdown-table-wrap">
            <table className="assistant-markdown-table">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="assistant-markdown-thead">{children}</thead>,
        th: ({ children }) => <th className="assistant-markdown-th">{children}</th>,
        td: ({ children }) => <td className="assistant-markdown-td">{children}</td>,
        strong: ({ children }) => (
          <strong className="assistant-markdown-strong">{children}</strong>
        ),
        code: ({ children }) => <code className="assistant-markdown-code">{children}</code>,
        a: ({ children, href }) => (
          <a
            className="assistant-markdown-link"
            href={href}
            rel="noreferrer"
            target="_blank"
          >
            {children}
          </a>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

export function MessageBubble({
  message,
  onWritebackDecision,
  onRetry,
}: {
  message: Message;
  onWritebackDecision: (actionId: string, decision: "approve" | "reject") => void;
  onRetry?: () => void;
}) {
  if (message.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <div
          style={{
            background: "var(--ds-blue-400)",
            color: "#fff",
            borderRadius: "14px 14px 4px 14px",
            padding: "8px 13px",
            fontSize: "13px",
            lineHeight: 1.55,
            maxWidth: "72%",
            wordBreak: "break-word",
          }}
        >
          {message.text}
        </div>
      </div>
    );
  }

  if (message.role === "assistant" && message.status === "error") {
    return (
      <div style={{ display: "flex", flexDirection: "column", maxWidth: "94%" }}>
        <div
          style={{
            background: "var(--ds-gray-100)",
            border: "1px solid rgba(245,166,35,0.3)",
            borderRadius: "4px 14px 14px 14px",
            padding: "10px 13px",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
            <span
              style={{
                color: "var(--ds-amber-400)",
                fontSize: "14px",
                flexShrink: 0,
                marginTop: "1px",
              }}
            >
              ⚠
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  color: "var(--ds-amber-400)",
                  fontSize: "12px",
                  fontWeight: 600,
                  marginBottom: "3px",
                }}
              >
                Stream interrupted
              </div>
              <div
                style={{
                  color: "var(--ds-gray-700)",
                  fontSize: "12px",
                  lineHeight: 1.45,
                }}
              >
                {message.text}
              </div>
            </div>
            {onRetry && (
              <button
                onClick={onRetry}
                style={{
                  background: "transparent",
                  border: "1px solid rgba(245,166,35,0.3)",
                  borderRadius: "6px",
                  color: "var(--ds-amber-400)",
                  cursor: "pointer",
                  fontFamily: "var(--font-geist-sans)",
                  fontSize: "11px",
                  padding: "4px 9px",
                  flexShrink: 0,
                  whiteSpace: "nowrap",
                }}
              >
                ↺ Retry
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", maxWidth: "94%" }}>
      <ToolTrace
        toolEvents={message.toolEvents}
        onWritebackDecision={onWritebackDecision}
      />
      {(message.text || message.status === "streaming") && (
        <div
          style={{
            background: "var(--ds-gray-100)",
            border: "1px solid var(--ds-border)",
            borderRadius: "4px 14px 14px 14px",
            padding: "10px 13px",
            fontSize: "13px",
            lineHeight: 1.65,
            color: "var(--ds-gray-900)",
            overflowWrap: "break-word",
          }}
        >
          <AssistantMarkdown text={message.text} />
          {message.status === "streaming" && (
            <span
              style={{
                display: "inline-block",
                width: "2px",
                height: "13px",
                background: "var(--ds-blue-400)",
                marginLeft: "2px",
                verticalAlign: "middle",
                animation: "blink 1s step-end infinite",
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}
