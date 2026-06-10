"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/config";
import type { Breakpoint } from "@/hooks/useBreakpoint";

type HealthStatus = "loading" | "ok" | "error";
type HealthResponse = {
  ok: boolean;
  postgres?: "ok" | "error";
  odoo?: "ok" | "error";
};

function StatusBadge({
  label,
  status,
}: {
  label: string;
  status: HealthStatus;
}) {
  const color =
    status === "ok"
      ? "var(--ds-green-400)"
      : status === "error"
        ? "var(--ds-amber-400)"
        : "var(--ds-gray-700)";
  const bg =
    status === "ok"
      ? "rgba(80,227,194,0.06)"
      : status === "error"
        ? "rgba(245,166,35,0.06)"
        : "transparent";
  const border =
    status === "ok"
      ? "rgba(80,227,194,0.25)"
      : status === "error"
        ? "rgba(245,166,35,0.25)"
        : "var(--ds-border)";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "5px",
        padding: "2px 9px",
        borderRadius: "6px",
        fontSize: "11px",
        color,
        background: bg,
        border: `1px solid ${border}`,
      }}
    >
      <div
        style={{
          width: "5px",
          height: "5px",
          borderRadius: "50%",
          background: color,
          animation:
            status === "loading"
              ? "pulse-led 1.2s ease-in-out infinite"
              : "none",
        }}
      />
      {label}
    </div>
  );
}

export function StatusBar({
  onNewChat,
  disableNewChat = false,
  breakpoint = "wide",
  railOpen = false,
  onToggleRail,
}: {
  onNewChat?: () => void;
  disableNewChat?: boolean;
  breakpoint?: Breakpoint;
  railOpen?: boolean;
  onToggleRail?: () => void;
}) {
  const [odooStatus, setOdooStatus] = useState<HealthStatus>("loading");
  const [postgresStatus, setPostgresStatus] = useState<HealthStatus>("loading");

  useEffect(() => {
    const controller = new AbortController();

    function poll() {
      fetch(`${API_URL}/health`, { signal: controller.signal })
        .then(async (response) => {
          const health = (await response.json()) as HealthResponse;
          setOdooStatus(health.odoo === "ok" ? "ok" : "error");
          setPostgresStatus(health.postgres === "ok" ? "ok" : "error");
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") {
            return;
          }
          setOdooStatus("error");
          setPostgresStatus("error");
        });
    }

    poll();
    const intervalId = setInterval(poll, 30_000);

    return () => {
      controller.abort();
      clearInterval(intervalId);
    };
  }, []);

  return (
    <div
      style={{
        background: "var(--ds-background-100)",
        borderBottom: "1px solid var(--ds-border)",
        padding: "0 16px",
        height: "40px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <div
          style={{
            width: "7px",
            height: "7px",
            background: "var(--ds-blue-400)",
            borderRadius: "50%",
          }}
        />
        <span
          style={{
            fontSize: "13px",
            fontWeight: 600,
            color: "var(--ds-gray-1000)",
          }}
        >
          Odoo Ops Copilot
        </span>
      </div>
      <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
        <StatusBadge label="Odoo" status={odooStatus} />
        {breakpoint !== "narrow" && (
          <StatusBadge label="Postgres" status={postgresStatus} />
        )}
        {breakpoint === "narrow" ? (
          onToggleRail && (
            <button
              onClick={onToggleRail}
              aria-label={railOpen ? "Close panel" : "Open panel"}
              style={{
                background: railOpen ? "var(--ds-gray-200)" : "var(--ds-gray-100)",
                border: "1px solid var(--ds-border)",
                borderRadius: "6px",
                color: "var(--ds-gray-900)",
                cursor: "pointer",
                fontFamily: "var(--font-geist-sans)",
                fontSize: "13px",
                padding: "3px 9px",
                lineHeight: 1,
              }}
            >
              {railOpen ? "✕" : "⊞"}
            </button>
          )
        ) : (
          onNewChat && (
            <button
              onClick={onNewChat}
              disabled={disableNewChat}
              style={{
                background: "var(--ds-gray-100)",
                border: "1px solid var(--ds-border)",
                borderRadius: "6px",
                color: disableNewChat
                  ? "var(--ds-gray-700)"
                  : "var(--ds-gray-900)",
                cursor: disableNewChat ? "not-allowed" : "pointer",
                fontFamily: "var(--font-geist-sans)",
                fontSize: "11px",
                padding: "3px 9px",
              }}
            >
              New chat
            </button>
          )
        )}
      </div>
    </div>
  );
}
