export type ToolName =
  | "odoo_query"
  | "sql_analytics"
  | "forecast_demand"
  | "simulate_discount_impact"
  | "propose_discount_rule"
  | "propose_restock_rule"
  | "propose_purchase_order"
  | "propose_invoice_reminder"
  | "propose_price_update"
  | "propose_pos_pricelist"
  | "propose_email_campaign"
  | "propose_transfer_stock";

export type ForecastData = {
  category: string;
  history: { month: string; units: number }[];
  forecast: { month: string; units: number }[];
};

export type ToolEvent = {
  id: string;
  name: ToolName;
  status: "running" | "done";
  input: Record<string, unknown>;
  sql?: string;
  rowCount?: number;
  rows?: Record<string, unknown>[];
  forecastData?: ForecastData;
  simulation?: Record<string, unknown>;
  evidence?: ToolEvidence;
  writeback?: WritebackProposal;
  error?: string;
};

export type PreviewChange = {
  field: string;
  label?: string;
  old_value: unknown;
  new_value: unknown;
};

export type PreviewRecord = {
  label: string;
  operation: string;
  odoo_id?: number | null;
  changes: PreviewChange[];
  metadata?: Record<string, unknown>;
};

export type WritebackPreview = {
  odoo_model: string;
  operation: string;
  records: PreviewRecord[];
  expected_impact: string[];
  risk_notes: string[];
  metadata?: Record<string, unknown>;
};

export type ToolEvidence = {
  title: string;
  data_used: string;
  sql?: string;
  rows_returned: number;
  top_rows: Record<string, unknown>[];
  why: string;
};

export type WritebackProposal = {
  id: string;
  session_id: string;
  action_type:
    | "discount_rule"
    | "restock_rule"
    | "purchase_order"
    | "invoice_reminder"
    | "price_update"
    | "pos_pricelist"
    | "email_campaign"
    | "transfer_stock";
  title: string;
  summary: string;
  payload: Record<string, unknown>;
  preview?: WritebackPreview;
  status: "pending" | "approved" | "rejected" | "failed";
  odoo_model?: string;
  odoo_record_ids?: number[];
  error?: string;
  created_at?: string;
  decided_at?: string;
  created_by?: string;
  decided_by?: string;
  isSubmitting?: boolean;
};

export type AuditAction = WritebackProposal;

export type Message = {
  id: string;
  role: "user" | "assistant";
  text: string;
  toolEvents: ToolEvent[];
  status: "streaming" | "done" | "error";
};

export type ChatState = {
  sessionId: string | null;
  messages: Message[];
  forecastData: ForecastData | null;
  writebacks: AuditAction[];
  isHydrating: boolean;
  isStreaming: boolean;
  bannerMessage: string | null;
};

export type ChatSessionSnapshot = {
  session_id: string;
  messages: Message[];
  forecastData: ForecastData | null;
};

export type Action =
  | {
      type: "HYDRATE_SESSION";
      sessionId: string;
      messages: Message[];
      forecastData: ForecastData | null;
      writebacks: AuditAction[];
    }
  | { type: "SET_WRITEBACKS"; writebacks: AuditAction[] }
  | { type: "SET_SESSION"; sessionId: string }
  | { type: "RESET_SESSION"; sessionId: string }
  | { type: "SESSION_ERROR"; message?: string }
  | { type: "SET_HYDRATING" }
  | {
      type: "SUBMIT";
      text: string;
      userMessageId: string;
      assistantMessageId: string;
    }
  | {
      type: "TOOL_START";
      toolEvent: Omit<ToolEvent, "status">;
      messageId: string;
    }
  | {
      type: "TOOL_RESULT";
      name: ToolName;
      patch: Partial<ToolEvent>;
      messageId: string;
    }
  | { type: "TEXT_DELTA"; text: string; messageId: string }
  | {
      type: "WRITEBACK_STATUS";
      actionId: string;
      patch: Partial<WritebackProposal>;
    }
  | { type: "DONE"; messageId: string }
  | { type: "ERROR"; message: string; messageId: string };
