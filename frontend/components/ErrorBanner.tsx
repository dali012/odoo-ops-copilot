"use client";

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      style={{
        background: "rgba(245,166,35,0.08)",
        borderBottom: "1px solid rgba(245,166,35,0.2)",
        padding: "7px 16px",
        display: "flex",
        alignItems: "center",
        gap: "8px",
        flexShrink: 0,
      }}
    >
      <span style={{ color: "var(--ds-amber-400)", fontSize: "13px" }}>⚠</span>
      <span style={{ color: "var(--ds-amber-400)", fontSize: "12px", flex: 1 }}>
        {message}
      </span>
      <button
        onClick={onRetry}
        style={{
          background: "transparent",
          border: "1px solid rgba(245,166,35,0.3)",
          borderRadius: "5px",
          color: "var(--ds-amber-400)",
          cursor: "pointer",
          fontFamily: "var(--font-geist-sans)",
          fontSize: "11px",
          padding: "3px 10px",
        }}
      >
        Retry
      </button>
    </div>
  );
}
