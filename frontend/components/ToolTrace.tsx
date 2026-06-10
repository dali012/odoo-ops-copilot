import type { ToolEvent, WritebackProposal } from "@/types/chat";

const SQL_KEYWORDS =
  /\b(SELECT|FROM|JOIN|WHERE|GROUP|BY|ORDER|HAVING|LIMIT|AND|OR|AS|ON|IN|SUM|COUNT|AVG|LEFT|RIGHT|INNER)\b/gi;
const SQL_KEYWORD = /^(SELECT|FROM|JOIN|WHERE|GROUP|BY|ORDER|HAVING|LIMIT|AND|OR|AS|ON|IN|SUM|COUNT|AVG|LEFT|RIGHT|INNER)$/i;

function SqlBlock({ sql }: { sql: string }) {
  const parts = sql.split(SQL_KEYWORDS);

  return (
    <div
      style={{
        background: "var(--ds-background-100)",
        border: "1px solid var(--ds-border)",
        borderRadius: "6px",
        padding: "7px 10px",
        fontFamily: "var(--font-geist-mono)",
        fontSize: "10px",
        color: "var(--ds-gray-700)",
        lineHeight: 1.6,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        marginTop: "5px",
      }}
    >
      {parts.map((part, index) =>
        SQL_KEYWORD.test(part) ? (
          <span key={`${part}-${index}`} style={{ color: "var(--ds-blue-400)" }}>
            {part}
          </span>
        ) : (
          <span key={`${part}-${index}`}>{part}</span>
        ),
      )}
    </div>
  );
}

function Spinner() {
  return (
    <span
      style={{
        display: "inline-block",
        width: "10px",
        height: "10px",
        border: "1.5px solid transparent",
        borderTopColor: "currentColor",
        borderRadius: "50%",
        animation: "spin 0.6s linear infinite",
        marginRight: "5px",
        verticalAlign: "middle",
        flexShrink: 0,
      }}
    />
  );
}

function WritebackCard({
  proposal,
  onDecision,
}: {
  proposal: WritebackProposal;
  onDecision: (actionId: string, decision: "approve" | "reject") => void;
}) {
  const isPending = proposal.status === "pending";
  const statusLabel = proposal.isSubmitting ? "applying..." : proposal.status;
  const preview = proposal.preview;

  return (
    <div
      style={{
        background: "var(--ds-background-100)",
        border: "1px solid var(--ds-border-strong)",
        borderRadius: "8px",
        marginTop: "8px",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          borderBottom: "1px solid var(--ds-border)",
          padding: "8px 10px",
        }}
      >
        <div
          style={{
            color: "var(--ds-gray-1000)",
            fontSize: "12px",
            fontWeight: 650,
          }}
        >
          {proposal.title}
        </div>
        <div
          style={{
            color: "var(--ds-gray-700)",
            fontSize: "11px",
            lineHeight: 1.45,
            marginTop: "3px",
          }}
        >
          {proposal.summary}
        </div>
      </div>
      <div
        style={{
          display: "grid",
          gap: "7px",
          padding: "8px 10px",
          fontFamily: "var(--font-geist-mono)",
          fontSize: "10px",
          color: "var(--ds-gray-800)",
        }}
      >
        <div>type: {proposal.action_type}</div>
        {proposal.odoo_model && <div>odoo_model: {proposal.odoo_model}</div>}
        {proposal.odoo_record_ids?.length ? (
          <div>record_ids: {proposal.odoo_record_ids.join(", ")}</div>
        ) : null}
        {preview && (
          <div
            style={{
              borderTop: "1px solid var(--ds-border)",
              display: "grid",
              gap: "7px",
              paddingTop: "7px",
            }}
          >
            <div>preview: {preview.operation} on {preview.odoo_model}</div>
            {preview.records.slice(0, 4).map((record, index) => (
              <div key={`${record.label}-${index}`} style={{ display: "grid", gap: "3px" }}>
                <div style={{ color: "var(--ds-gray-1000)" }}>
                  {record.operation}: {record.label}
                </div>
                {record.changes.slice(0, 4).map((change) => (
                  <div key={`${record.label}-${change.field}`} style={{ paddingLeft: "10px" }}>
                    {(change.label || change.field)}: {String(change.old_value ?? "None")} -&gt;{" "}
                    {String(change.new_value ?? "None")}
                  </div>
                ))}
              </div>
            ))}
            {preview.expected_impact.length > 0 && (
              <div style={{ color: "var(--ds-green-400)" }}>
                impact: {preview.expected_impact[0]}
              </div>
            )}
            {preview.risk_notes.length > 0 && (
              <div style={{ color: "var(--ds-amber-400)" }}>
                risk: {preview.risk_notes[0]}
              </div>
            )}
          </div>
        )}
      </div>
      {proposal.error && (
        <div style={{ padding: "0 10px 8px" }}>
          <p
            style={{
              color: "var(--ds-amber-400)",
              fontSize: "11px",
              margin: 0,
              lineHeight: 1.45,
            }}
          >
            {proposal.error}
          </p>
        </div>
      )}
      <div
        style={{
          borderTop: "1px solid var(--ds-border)",
          display: "flex",
          gap: "8px",
          justifyContent: "space-between",
          padding: "8px 10px",
        }}
      >
        <span
          style={{
            color:
              proposal.status === "approved"
                ? "var(--ds-green-400)"
                : proposal.status === "failed"
                  ? "var(--ds-amber-400)"
                  : "var(--ds-gray-700)",
            fontSize: "11px",
          }}
        >
          {statusLabel}
        </span>
        {isPending && (
          <div style={{ display: "flex", gap: "6px" }}>
            <button
              onClick={() => onDecision(proposal.id, "reject")}
              disabled={proposal.isSubmitting}
              style={{
                background: "transparent",
                border: "1px solid var(--ds-border)",
                borderRadius: "6px",
                color: "var(--ds-gray-800)",
                cursor: proposal.isSubmitting ? "not-allowed" : "pointer",
                opacity: proposal.isSubmitting ? 0.55 : 1,
                fontFamily: "var(--font-geist-sans)",
                fontSize: "11px",
                padding: "4px 9px",
              }}
            >
              {proposal.isSubmitting ? (
                <><Spinner />Rejecting…</>
              ) : (
                "Reject"
              )}
            </button>
            <button
              onClick={() => onDecision(proposal.id, "approve")}
              disabled={proposal.isSubmitting}
              style={{
                background: "var(--ds-gray-1000)",
                border: "none",
                borderRadius: "6px",
                color: "#000",
                cursor: proposal.isSubmitting ? "not-allowed" : "pointer",
                opacity: proposal.isSubmitting ? 0.55 : 1,
                fontFamily: "var(--font-geist-sans)",
                fontSize: "11px",
                fontWeight: 600,
                padding: "4px 9px",
              }}
            >
              {proposal.isSubmitting ? (
                <><Spinner />Approving…</>
              ) : (
                "Approve"
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ToolRow({
  event,
  onWritebackDecision,
}: {
  event: ToolEvent;
  onWritebackDecision: (actionId: string, decision: "approve" | "reject") => void;
}) {
  const isRunning = event.status === "running";
  const ledColor = isRunning ? "var(--ds-amber-400)" : "var(--ds-green-400)";
  const statusLabel = isRunning
    ? "running..."
    : event.rowCount !== undefined
      ? `done - ${event.rowCount} rows`
      : "done";

  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: "9px" }}>
      <div
        style={{
          width: "6px",
          height: "6px",
          borderRadius: "50%",
          background: ledColor,
          flexShrink: 0,
          marginTop: "4px",
          animation: isRunning ? "pulse-led 1s ease-in-out infinite" : "none",
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              fontFamily: "var(--font-geist-mono)",
              fontSize: "11px",
              color: isRunning ? "var(--ds-gray-900)" : "var(--ds-gray-800)",
            }}
          >
            {event.name}
          </span>
          <span
            style={{
              fontSize: "10px",
              color: isRunning ? "var(--ds-amber-400)" : "var(--ds-green-400)",
            }}
          >
            {statusLabel}
          </span>
        </div>

        {event.name === "sql_analytics" && event.sql && (
          <SqlBlock sql={event.sql} />
        )}

        {event.name === "forecast_demand" && (
          <div
            style={{
              fontFamily: "var(--font-geist-mono)",
              fontSize: "10px",
              color: "var(--ds-gray-700)",
              marginTop: "3px",
            }}
          >
            category: &quot;{String(event.input.category)}&quot;
            {event.input.months_ahead !== undefined &&
              ` - months_ahead: ${event.input.months_ahead}`}
          </div>
        )}

        {event.name === "odoo_query" && (
          <div
            style={{
              fontFamily: "var(--font-geist-mono)",
              fontSize: "10px",
              color: "var(--ds-gray-700)",
              marginTop: "3px",
            }}
          >
            model: &quot;{String(event.input.model)}&quot;
          </div>
        )}

        {event.writeback && (
          <WritebackCard
            proposal={event.writeback}
            onDecision={onWritebackDecision}
          />
        )}

        {event.evidence && (
          <div
            style={{
              color: "var(--ds-blue-400)",
              fontSize: "10px",
              marginTop: "5px",
            }}
          >
            View evidence in the Evidence tab
          </div>
        )}
      </div>
    </div>
  );
}

export function ToolTrace({
  toolEvents,
  onWritebackDecision,
}: {
  toolEvents: ToolEvent[];
  onWritebackDecision: (actionId: string, decision: "approve" | "reject") => void;
}) {
  if (toolEvents.length === 0) return null;

  return (
    <div
      style={{
        background: "var(--ds-gray-100)",
        border: "1px solid var(--ds-border)",
        borderRadius: "8px",
        overflow: "hidden",
        marginBottom: "8px",
      }}
    >
      <div
        style={{
          padding: "5px 12px",
          borderBottom: "1px solid var(--ds-border)",
          fontFamily: "var(--font-geist-mono)",
          fontSize: "10px",
          color: "var(--ds-gray-700)",
          textTransform: "uppercase",
        }}
      >
        Tool calls
      </div>
      <div
        style={{
          padding: "8px 12px",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        {toolEvents.map((event) => (
          <ToolRow
            key={event.id}
            event={event}
            onWritebackDecision={onWritebackDecision}
          />
        ))}
      </div>
    </div>
  );
}
