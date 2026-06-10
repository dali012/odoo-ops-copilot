"use client";

import { useCallback, useEffect, useReducer, useState } from "react";
import { API_URL } from "@/lib/config";
import { readStream } from "@/lib/stream";
import type {
  Action,
  ChatSessionSnapshot,
  ChatState,
  Message,
  ToolEvent,
  AuditAction,
} from "@/types/chat";

const SESSION_STORAGE_KEY = "odoo-ops-copilot-session-id";

async function apiError(response: Response): Promise<Error> {
  let detail = await response.text();
  try {
    const body = JSON.parse(detail) as { detail?: unknown };
    if (typeof body.detail === "string") {
      detail = body.detail;
    }
  } catch {
    // Keep the raw response text.
  }
  return new Error(`HTTP ${response.status}: ${detail || response.statusText}`);
}

export const initialState: ChatState = {
  sessionId: null,
  messages: [],
  forecastData: null,
  writebacks: [],
  isHydrating: true,
  isStreaming: false,
  bannerMessage: null,
};

export function chatReducer(state: ChatState, action: Action): ChatState {
  switch (action.type) {
    case "HYDRATE_SESSION":
      return {
        ...state,
        sessionId: action.sessionId,
        messages: action.messages,
        forecastData: action.forecastData,
        writebacks: action.writebacks,
        isHydrating: false,
        isStreaming: false,
        bannerMessage: null,
      };

    case "SET_WRITEBACKS":
      return {
        ...state,
        writebacks: action.writebacks,
      };

    case "SET_SESSION":
      return {
        ...state,
        sessionId: action.sessionId,
        isHydrating: false,
      };

    case "RESET_SESSION":
      return {
        ...initialState,
        sessionId: action.sessionId,
        isHydrating: false,
      };

    case "SET_HYDRATING":
      return {
        ...state,
        isHydrating: true,
        bannerMessage: null,
      };

    case "SESSION_ERROR":
      return {
        ...state,
        isHydrating: false,
        bannerMessage:
          action.message ??
          "Could not connect to the backend. Check the API is running and refresh.",
      };

    case "SUBMIT": {
      const userMsg: Message = {
        id: action.userMessageId,
        role: "user",
        text: action.text,
        toolEvents: [],
        status: "done",
      };
      const assistantMsg: Message = {
        id: action.assistantMessageId,
        role: "assistant",
        text: "",
        toolEvents: [],
        status: "streaming",
      };

      return {
        ...state,
        messages: [...state.messages, userMsg, assistantMsg],
        isStreaming: true,
      };
    }

    case "TOOL_START":
      return {
        ...state,
        messages: state.messages.map((msg) =>
          msg.id !== action.messageId
            ? msg
            : {
                ...msg,
                toolEvents: [
                  ...msg.toolEvents,
                  { ...action.toolEvent, status: "running" },
                ],
              },
        ),
      };

    case "TOOL_RESULT": {
      const forecastData =
        action.name === "forecast_demand" && action.patch.forecastData
          ? action.patch.forecastData
          : state.forecastData;
      const writebacks = action.patch.writeback
        ? [
            action.patch.writeback,
            ...state.writebacks.filter(
              (writeback) => writeback.id !== action.patch.writeback?.id,
            ),
          ]
        : state.writebacks;

      return {
        ...state,
        forecastData,
        writebacks,
        messages: state.messages.map((msg) => {
          if (msg.id !== action.messageId) return msg;

          let matched = false;
          return {
            ...msg,
            toolEvents: msg.toolEvents.map((toolEvent): ToolEvent => {
              if (
                !matched &&
                toolEvent.name === action.name &&
                toolEvent.status === "running"
              ) {
                matched = true;
                return { ...toolEvent, ...action.patch, status: "done" };
              }

              return toolEvent;
            }),
          };
        }),
      };
    }

    case "TEXT_DELTA":
      return {
        ...state,
        messages: state.messages.map((msg) =>
          msg.id !== action.messageId
            ? msg
            : { ...msg, text: msg.text + action.text },
        ),
      };

    case "WRITEBACK_STATUS":
      return {
        ...state,
        writebacks: state.writebacks.map((writeback) =>
          writeback.id !== action.actionId
            ? writeback
            : {
                ...writeback,
                ...action.patch,
              },
        ),
        messages: state.messages.map((msg) => ({
          ...msg,
          toolEvents: msg.toolEvents.map((toolEvent) =>
            toolEvent.writeback?.id !== action.actionId
              ? toolEvent
              : {
                  ...toolEvent,
                  writeback: {
                    ...toolEvent.writeback,
                    ...action.patch,
                  },
                },
          ),
        })),
      };

    case "DONE":
      return {
        ...state,
        isStreaming: false,
        messages: state.messages.map((msg) =>
          msg.id !== action.messageId ? msg : { ...msg, status: "done" },
        ),
      };

    case "ERROR":
      return {
        ...state,
        isStreaming: false,
        messages: state.messages.map((msg) =>
          msg.id !== action.messageId
            ? msg
            : { ...msg, text: action.message, status: "error" },
        ),
      };

    default:
      return state;
  }
}

export function useChat() {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const [retryTrigger, setRetryTrigger] = useState(0);

  const createSession = useCallback(async () => {
    const response = await fetch(`${API_URL}/chat/sessions`, { method: "POST" });
    if (!response.ok) {
      throw await apiError(response);
    }
    const data = (await response.json()) as { session_id: string };
    localStorage.setItem(SESSION_STORAGE_KEY, data.session_id);
    return data.session_id;
  }, []);

  const loadWritebacks = useCallback(async (sessionId: string): Promise<AuditAction[]> => {
    const response = await fetch(`${API_URL}/chat/sessions/${sessionId}/writebacks`);
    if (!response.ok) {
      throw await apiError(response);
    }
    const data = (await response.json()) as { actions: AuditAction[] };
    return data.actions;
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadSession() {
      try {
        const savedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
        if (savedSessionId) {
          const response = await fetch(`${API_URL}/chat/sessions/${savedSessionId}`);
          if (response.ok) {
            const snapshot = (await response.json()) as ChatSessionSnapshot;
            const writebacks = await loadWritebacks(snapshot.session_id);
            if (!cancelled) {
              dispatch({
                type: "HYDRATE_SESSION",
                sessionId: snapshot.session_id,
                messages: snapshot.messages,
                forecastData: snapshot.forecastData,
                writebacks,
              });
            }
            return;
          }
          localStorage.removeItem(SESSION_STORAGE_KEY);
        }

        const sessionId = await createSession();
        if (!cancelled) {
          dispatch({ type: "RESET_SESSION", sessionId });
        }
      } catch {
        if (!cancelled) {
          dispatch({ type: "SESSION_ERROR" });
        }
      }
    }

    loadSession();

    return () => {
      cancelled = true;
    };
  }, [createSession, loadWritebacks, retryTrigger]);

  const submit = useCallback(
    async (text: string) => {
      const userMessageId = crypto.randomUUID();
      const assistantMessageId = crypto.randomUUID();
      dispatch({ type: "SUBMIT", text, userMessageId, assistantMessageId });

      try {
        let sessionId = state.sessionId;
        if (!sessionId) {
          sessionId = await createSession();
          dispatch({ type: "SET_SESSION", sessionId });
        }

        const response = await fetch(`${API_URL}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, session_id: sessionId }),
        });

        if (!response.ok) {
          throw await apiError(response);
        }

        await readStream(response, dispatch, assistantMessageId);
      } catch (err) {
        dispatch({
          type: "ERROR",
          message: err instanceof Error ? err.message : String(err),
          messageId: assistantMessageId,
        });
      }
    },
    [createSession, state.sessionId],
  );

  const newChat = useCallback(async () => {
    const sessionId = await createSession();
    dispatch({ type: "RESET_SESSION", sessionId });
  }, [createSession]);

  const updateWriteback = useCallback(
    async (actionId: string, decision: "approve" | "reject") => {
      dispatch({
        type: "WRITEBACK_STATUS",
        actionId,
        patch: { isSubmitting: true, error: undefined },
      });

      try {
        const response = await fetch(`${API_URL}/writebacks/${actionId}/${decision}`, {
          method: "POST",
        });
        if (!response.ok) {
          throw await apiError(response);
        }
        const data = (await response.json()) as {
          id: string;
          status: "pending" | "approved" | "rejected" | "failed";
          odoo_model?: string;
          odoo_record_ids?: number[];
          error?: string;
        } & Partial<AuditAction>;
        dispatch({
          type: "WRITEBACK_STATUS",
          actionId,
          patch: {
            ...data,
            status: data.status,
            isSubmitting: false,
          },
        });
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : String(err);
        const requestDidNotReachServer =
          err instanceof TypeError || /Failed to fetch/i.test(errorMessage);

        dispatch({
          type: "WRITEBACK_STATUS",
          actionId,
          patch: {
            status: requestDidNotReachServer ? "pending" : "failed",
            error: requestDidNotReachServer
              ? "Approval request could not reach the API. Check the backend and retry."
              : errorMessage,
            isSubmitting: false,
          },
        });
      }
    },
    [],
  );

  const reloadSession = useCallback(() => {
    dispatch({ type: "SET_HYDRATING" });
    setRetryTrigger((n) => n + 1);
  }, []);

  return { ...state, submit, newChat, updateWriteback, reloadSession };
}
