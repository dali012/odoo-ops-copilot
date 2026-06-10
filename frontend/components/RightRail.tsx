"use client";

import { useMemo, useState } from "react";
import type { AuditAction, ForecastData, Message, ToolEvidence } from "@/types/chat";
import type { Breakpoint } from "@/hooks/useBreakpoint";
import { ChartPanel } from "./ChartPanel";

type Tab = "forecast" | "evidence" | "activity";

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "None";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function EvidenceCard({ evidence }: { evidence: ToolEvidence }) {
  const columns = Object.keys(evidence.top_rows[0] ?? {}).slice(0, 6);

  return (
    <div
      style={{
        border: "1px solid var(--ds-border)",
        borderRadius: "8px",
        background: "var(--ds-gray-100)",
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--ds-border)" }}>
        <div style={{ color: "var(--ds-gray-1000)", fontSize: "12px", fontWeight: 650 }}>
          {evidence.title}
        </div>
        <div style={{ color: "var(--ds-gray-700)", fontSize: "11px", marginTop: "3px" }}>
          {evidence.rows_returned} rows returned
        </div>
      </div>
      <div style={{ display: "grid", gap: "8px", padding: "10px 12px" }}>
        <div>
          <div style={{ color: "var(--ds-gray-700)", fontSize: "10px", textTransform: "uppercase" }}>
            Data used
          </div>
          <div style={{ color: "var(--ds-gray-900)", fontSize: "12px", lineHeight: 1.45 }}>
            {evidence.data_used}
          </div>
        </div>
        <div>
          <div style={{ color: "var(--ds-gray-700)", fontSize: "10px", textTransform: "uppercase" }}>
            Why
          </div>
          <div style={{ color: "var(--ds-gray-900)", fontSize: "12px", lineHeight: 1.45 }}>
            {evidence.why}
          </div>
        </div>
        {evidence.sql && (
          <details>
            <summary style={{ cursor: "pointer", color: "var(--ds-blue-400)", fontSize: "11px" }}>
              SQL generated
            </summary>
            <pre
              style={{
                margin: "8px 0 0",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
                color: "var(--ds-gray-800)",
                fontFamily: "var(--font-geist-mono)",
                fontSize: "10px",
                lineHeight: 1.5,
              }}
            >
              {evidence.sql}
            </pre>
          </details>
        )}
        {columns.length > 0 && (
          <details>
            <summary style={{ cursor: "pointer", color: "var(--ds-blue-400)", fontSize: "11px" }}>
              Top rows
            </summary>
            <div style={{ overflowX: "auto", marginTop: "8px" }}>
              <table style={{ borderCollapse: "collapse", minWidth: "100%", fontSize: "10px" }}>
                <thead>
                  <tr>
                    {columns.map((column) => (
                      <th
                        key={column}
                        style={{
                          borderBottom: "1px solid var(--ds-border)",
                          color: "var(--ds-gray-1000)",
                          padding: "5px 6px",
                          textAlign: "left",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {evidence.top_rows.map((row, index) => (
                    <tr key={index}>
                      {columns.map((column) => (
                        <td
                          key={column}
                          style={{
                            borderBottom: "1px solid var(--ds-border)",
                            color: "var(--ds-gray-800)",
                            padding: "5px 6px",
                            maxWidth: "160px",
                            overflowWrap: "anywhere",
                          }}
                        >
                          {formatValue(row[column])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function EvidenceTab({ messages }: { messages: Message[] }) {
  const evidence = useMemo(
    () =>
      messages
        .flatMap((message) => message.toolEvents)
        .map((event) => event.evidence)
        .filter((item): item is ToolEvidence => Boolean(item))
        .reverse(),
    [messages],
  );

  if (evidence.length === 0) {
    return (
      <EmptyRailText
        title="No evidence yet"
        body="Tool evidence appears after the agent runs a query or drafts an action."
      />
    );
  }

  return (
    <div style={{ display: "grid", gap: "10px" }}>
      {evidence.map((item, index) => (
        <EvidenceCard key={`${item.title}-${index}`} evidence={item} />
      ))}
    </div>
  );
}

function statusColor(status: AuditAction["status"]): string {
  if (status === "approved") return "var(--ds-green-400)";
  if (status === "failed") return "var(--ds-amber-400)";
  if (status === "rejected") return "var(--ds-gray-700)";
  return "var(--ds-blue-400)";
}

function ActivityTab({ writebacks }: { writebacks: AuditAction[] }) {
  if (writebacks.length === 0) {
    return (
      <EmptyRailText
        title="No decisions yet"
        body="Proposals, approvals, rejections, and Odoo record IDs will appear here."
      />
    );
  }

  return (
    <div style={{ display: "grid", gap: "10px" }}>
      {writebacks.map((action) => (
        <div
          key={action.id}
          style={{
            border: "1px solid var(--ds-border)",
            borderRadius: "8px",
            background: "var(--ds-gray-100)",
            padding: "10px 12px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: "8px" }}>
            <div style={{ color: "var(--ds-gray-1000)", fontSize: "12px", fontWeight: 650 }}>
              {action.title}
            </div>
            <span style={{ color: statusColor(action.status), fontSize: "10px", flexShrink: 0 }}>
              {action.status}
            </span>
          </div>
          <div style={{ color: "var(--ds-gray-700)", fontSize: "11px", marginTop: "5px" }}>
            proposed by {action.created_by || "Agent"}
            {action.decided_by ? ` - decided by ${action.decided_by}` : ""}
          </div>
          <div
            style={{
              color: "var(--ds-gray-800)",
              fontFamily: "var(--font-geist-mono)",
              fontSize: "10px",
              lineHeight: 1.6,
              marginTop: "8px",
              overflowWrap: "anywhere",
            }}
          >
            <div>model: {action.odoo_model || action.preview?.odoo_model || "pending"}</div>
            {action.odoo_record_ids?.length ? (
              <div>records: {action.odoo_record_ids.join(", ")}</div>
            ) : null}
            <div>
              created:{" "}
              {action.created_at ? new Date(action.created_at).toLocaleString() : "unknown"}
            </div>
            {action.decided_at && (
              <div>decided: {new Date(action.decided_at).toLocaleString()}</div>
            )}
            {action.error && (
              <div style={{ color: "var(--ds-amber-400)" }}>error: {action.error}</div>
            )}
            {action.status === "failed" && (
              <div style={{ color: "var(--ds-gray-700)" }}>retry: create a revised proposal</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyRailText({ title, body }: { title: string; body: string }) {
  return (
    <div
      style={{
        height: "100%",
        display: "grid",
        placeItems: "center",
        textAlign: "center",
        padding: "22px",
      }}
    >
      <div>
        <div style={{ color: "var(--ds-gray-1000)", fontSize: "12px", fontWeight: 650 }}>
          {title}
        </div>
        <p
          style={{
            color: "var(--ds-gray-700)",
            fontSize: "12px",
            lineHeight: 1.45,
            margin: "7px 0 0",
          }}
        >
          {body}
        </p>
      </div>
    </div>
  );
}

function RailContent({
  forecastData,
  messages,
  writebacks,
  onNewChat,
}: {
  forecastData: ForecastData | null;
  messages: Message[];
  writebacks: AuditAction[];
  onNewChat?: () => void;
}) {
  const [activeTab, setActiveTab] = useState<Tab>("forecast");
  const tabs: { id: Tab; label: string }[] = [
    { id: "forecast", label: "Forecast" },
    { id: "evidence", label: "Evidence" },
    { id: "activity", label: "Activity" },
  ];

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          padding: "8px",
          borderBottom: "1px solid var(--ds-border)",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: "4px",
            flex: 1,
          }}
        >
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                background: activeTab === tab.id ? "var(--ds-gray-200)" : "transparent",
                border: "1px solid var(--ds-border)",
                borderRadius: "6px",
                color:
                  activeTab === tab.id ? "var(--ds-gray-1000)" : "var(--ds-gray-700)",
                cursor: "pointer",
                fontFamily: "var(--font-geist-sans)",
                fontSize: "11px",
                fontWeight: activeTab === tab.id ? 650 : 500,
                padding: "6px 4px",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {onNewChat && (
          <button
            onClick={onNewChat}
            style={{
              background: "var(--ds-gray-100)",
              border: "1px solid var(--ds-border)",
              borderRadius: "6px",
              color: "var(--ds-gray-900)",
              cursor: "pointer",
              fontFamily: "var(--font-geist-sans)",
              fontSize: "11px",
              padding: "3px 9px",
              flexShrink: 0,
              whiteSpace: "nowrap",
            }}
          >
            New chat
          </button>
        )}
      </div>
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: activeTab === "forecast" ? "hidden" : "auto",
          padding: activeTab === "forecast" ? 0 : "12px",
        }}
      >
        {activeTab === "forecast" && <ChartPanel forecastData={forecastData} embedded />}
        {activeTab === "evidence" && <EvidenceTab messages={messages} />}
        {activeTab === "activity" && <ActivityTab writebacks={writebacks} />}
      </div>
    </>
  );
}

export function RightRail({
  forecastData,
  messages,
  writebacks,
  breakpoint = "wide",
  railOpen = false,
  onCloseRail,
  onNewChat,
}: {
  forecastData: ForecastData | null;
  messages: Message[];
  writebacks: AuditAction[];
  breakpoint?: Breakpoint;
  railOpen?: boolean;
  onCloseRail?: () => void;
  onNewChat?: () => void;
}) {
  const railWidth = breakpoint === "wide" ? "340px" : "260px";

  if (breakpoint === "narrow") {
    return (
      <>
        {railOpen && (
          <div
            onClick={onCloseRail}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 99,
              background: "rgba(0,0,0,0.4)",
            }}
          />
        )}
        <aside
          className="rail-drawer"
          style={{
            position: "fixed",
            top: "40px",
            right: 0,
            bottom: 0,
            width: "300px",
            background: "var(--ds-background-100)",
            borderLeft: "1px solid var(--ds-border)",
            display: "flex",
            flexDirection: "column",
            zIndex: 100,
            transform: railOpen ? "translateX(0)" : "translateX(100%)",
          }}
        >
          <RailContent
            forecastData={forecastData}
            messages={messages}
            writebacks={writebacks}
            onNewChat={onNewChat}
          />
        </aside>
      </>
    );
  }

  return (
    <aside
      style={{
        width: railWidth,
        flexShrink: 0,
        background: "var(--ds-background-100)",
        borderLeft: "1px solid var(--ds-border)",
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
        transition: "width 200ms ease",
      }}
    >
      <RailContent
        forecastData={forecastData}
        messages={messages}
        writebacks={writebacks}
      />
    </aside>
  );
}
