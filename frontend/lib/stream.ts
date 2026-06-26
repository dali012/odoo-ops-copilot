import type { Dispatch } from "react";
import type { Action, ToolEvent } from "@/types/chat";
import { parseForecastSeries } from "./forecast";

type StreamEvent = Record<string, unknown> & { type?: unknown };

export async function readStream(
  response: Response,
  dispatch: Dispatch<Action>,
  messageId: string,
): Promise<void> {
  if (!response.body) return;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;

        let event: StreamEvent;
        try {
          event = JSON.parse(line.slice(6)) as StreamEvent;
        } catch {
          continue;
        }

        switch (event.type) {
          case "tool_start": {
            const toolEvent: Omit<ToolEvent, "status"> = {
              id: crypto.randomUUID(),
              name: event.name as ToolEvent["name"],
              input: (event.input as Record<string, unknown>) ?? {},
              attempt:
                typeof event.attempt === "number" ? event.attempt : undefined,
              isRetry: event.is_retry === true,
            };
            dispatch({ type: "TOOL_START", toolEvent, messageId });
            break;
          }

          case "tool_result": {
            const patch: Partial<ToolEvent> = {};
            if (event.evidence) {
              patch.evidence = event.evidence as ToolEvent["evidence"];
            }
            if (typeof event.error === "string") {
              patch.error = event.error;
            }
            if (typeof event.attempt === "number") {
              patch.attempt = event.attempt;
            }
            if (event.is_retry === true) {
              patch.isRetry = true;
            }
            if (event.recovered === true) {
              patch.recovered = true;
            }
            if (event.name === "sql_analytics") {
              patch.sql = event.sql as string | undefined;
              patch.rowCount = event.row_count as number | undefined;
              patch.rows = event.rows as Record<string, unknown>[] | undefined;
            } else if (event.name === "forecast_demand") {
              patch.forecastData = {
                category:
                  typeof event.category === "string" ? event.category : "",
                history: parseForecastSeries(event.history),
                forecast: parseForecastSeries(event.forecast),
              };
            } else if (event.writeback) {
              patch.writeback = event.writeback as ToolEvent["writeback"];
            } else if (event.name === "simulate_discount_impact" && event.simulation) {
              patch.simulation = event.simulation as Record<string, unknown>;
            }
            dispatch({
              type: "TOOL_RESULT",
              name: event.name as ToolEvent["name"],
              patch,
              messageId,
            });
            break;
          }

          case "text_delta":
            dispatch({
              type: "TEXT_DELTA",
              text: event.text as string,
              messageId,
            });
            break;

          case "done":
            dispatch({ type: "DONE", messageId });
            return;

          case "error":
            dispatch({
              type: "ERROR",
              message: event.message as string,
              messageId,
            });
            return;
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
