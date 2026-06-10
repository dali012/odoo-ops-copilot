import { chatReducer, initialState } from "@/hooks/useChat";
import type { Action } from "@/types/chat";

const submitAction: Action = {
  type: "SUBMIT",
  text: "Hello",
  userMessageId: "user-1",
  assistantMessageId: "asst-1",
};

describe("chatReducer", () => {
  it("HYDRATE_SESSION restores persisted messages and forecast data", () => {
    const state = chatReducer(initialState, {
      type: "HYDRATE_SESSION",
      sessionId: "session-1",
      messages: [
        {
          id: "db-1",
          role: "user",
          text: "Forecast Outerwear",
          toolEvents: [],
          status: "done",
        },
      ],
      forecastData: {
        category: "Outerwear",
        history: [],
        forecast: [{ month: "2026-06-01", units: 18.3 }],
      },
      writebacks: [],
    });

    expect(state.sessionId).toBe("session-1");
    expect(state.isHydrating).toBe(false);
    expect(state.messages).toHaveLength(1);
    expect(state.forecastData?.forecast[0].units).toBe(18.3);
  });

  it("RESET_SESSION clears messages and keeps the new session ID", () => {
    const hydrated = chatReducer(initialState, {
      type: "HYDRATE_SESSION",
      sessionId: "old-session",
      messages: [
        {
          id: "db-1",
          role: "assistant",
          text: "Prior answer",
          toolEvents: [],
          status: "done",
        },
      ],
      forecastData: {
        category: "Outerwear",
        history: [],
        forecast: [{ month: "2026-06-01", units: 18.3 }],
      },
      writebacks: [],
    });
    const state = chatReducer(hydrated, {
      type: "RESET_SESSION",
      sessionId: "new-session",
    });

    expect(state.sessionId).toBe("new-session");
    expect(state.messages).toHaveLength(0);
    expect(state.forecastData).toBeNull();
    expect(state.writebacks).toHaveLength(0);
    expect(state.isHydrating).toBe(false);
  });

  it("HYDRATE_SESSION restores audit actions", () => {
    const state = chatReducer(initialState, {
      type: "HYDRATE_SESSION",
      sessionId: "session-1",
      messages: [],
      forecastData: null,
      writebacks: [
        {
          id: "action-1",
          session_id: "session-1",
          action_type: "purchase_order",
          title: "Create PO",
          summary: "Replenish stock",
          payload: {},
          status: "pending",
        },
      ],
    });

    expect(state.writebacks).toHaveLength(1);
    expect(state.writebacks[0].title).toBe("Create PO");
  });

  it("SUBMIT adds user + assistant messages and sets isStreaming", () => {
    const state = chatReducer(initialState, submitAction);

    expect(state.messages).toHaveLength(2);
    expect(state.messages[0]).toMatchObject({
      id: "user-1",
      role: "user",
      text: "Hello",
      status: "done",
    });
    expect(state.messages[1]).toMatchObject({
      id: "asst-1",
      role: "assistant",
      text: "",
      status: "streaming",
    });
    expect(state.isStreaming).toBe(true);
  });

  it("TOOL_START appends a running tool event to the assistant message", () => {
    const afterSubmit = chatReducer(initialState, submitAction);
    const state = chatReducer(afterSubmit, {
      type: "TOOL_START",
      messageId: "asst-1",
      toolEvent: {
        id: "te-1",
        name: "sql_analytics",
        input: { sql: "SELECT 1" },
      },
    });

    expect(state.messages[1].toolEvents).toHaveLength(1);
    expect(state.messages[1].toolEvents[0]).toMatchObject({
      name: "sql_analytics",
      status: "running",
    });
  });

  it("TOOL_RESULT marks tool done and extracts forecastData", () => {
    let state = chatReducer(initialState, submitAction);
    state = chatReducer(state, {
      type: "TOOL_START",
      messageId: "asst-1",
      toolEvent: {
        id: "te-1",
        name: "forecast_demand",
        input: { category: "Outerwear" },
      },
    });
    state = chatReducer(state, {
      type: "TOOL_RESULT",
      name: "forecast_demand",
      messageId: "asst-1",
      patch: {
        forecastData: {
          category: "Outerwear",
          history: [],
          forecast: [{ month: "2026-07-01", units: 312 }],
        },
      },
    });

    expect(state.messages[1].toolEvents[0].status).toBe("done");
    expect(state.forecastData?.category).toBe("Outerwear");
    expect(state.forecastData?.forecast[0].units).toBe(312);
  });

  it("TOOL_RESULT adds writeback proposals to the audit list", () => {
    let state = chatReducer(initialState, submitAction);
    state = chatReducer(state, {
      type: "TOOL_START",
      messageId: "asst-1",
      toolEvent: {
        id: "te-1",
        name: "propose_purchase_order",
        input: {},
      },
    });
    state = chatReducer(state, {
      type: "TOOL_RESULT",
      name: "propose_purchase_order",
      messageId: "asst-1",
      patch: {
        writeback: {
          id: "action-1",
          session_id: "session-1",
          action_type: "purchase_order",
          title: "Create PO",
          summary: "Replenish stock",
          payload: {},
          status: "pending",
        },
      },
    });

    expect(state.writebacks).toHaveLength(1);
    expect(state.messages[1].toolEvents[0].writeback?.id).toBe("action-1");
  });

  it("TEXT_DELTA appends text to the assistant message", () => {
    let state = chatReducer(initialState, submitAction);
    state = chatReducer(state, {
      type: "TEXT_DELTA",
      text: "Hello ",
      messageId: "asst-1",
    });
    state = chatReducer(state, {
      type: "TEXT_DELTA",
      text: "world",
      messageId: "asst-1",
    });

    expect(state.messages[1].text).toBe("Hello world");
  });

  it("DONE sets message status to done and clears isStreaming", () => {
    let state = chatReducer(initialState, submitAction);
    state = chatReducer(state, { type: "DONE", messageId: "asst-1" });

    expect(state.messages[1].status).toBe("done");
    expect(state.isStreaming).toBe(false);
  });

  it("ERROR sets message status to error and clears isStreaming", () => {
    let state = chatReducer(initialState, submitAction);
    state = chatReducer(state, {
      type: "ERROR",
      message: "Something failed",
      messageId: "asst-1",
    });

    expect(state.messages[1]).toMatchObject({
      status: "error",
      text: "Something failed",
    });
    expect(state.isStreaming).toBe(false);
  });

  it("SESSION_ERROR sets bannerMessage and clears isHydrating", () => {
    const state = chatReducer(initialState, {
      type: "SESSION_ERROR",
      message: "Could not connect to the backend.",
    });
    expect(state.isHydrating).toBe(false);
    expect(state.bannerMessage).toBe("Could not connect to the backend.");
  });

  it("SESSION_ERROR uses default message when none provided", () => {
    const state = chatReducer(initialState, { type: "SESSION_ERROR" });
    expect(state.bannerMessage).toBe(
      "Could not connect to the backend. Check the API is running and refresh.",
    );
  });

  it("HYDRATE_SESSION clears bannerMessage", () => {
    const withBanner = chatReducer(initialState, {
      type: "SESSION_ERROR",
      message: "Offline",
    });
    const state = chatReducer(withBanner, {
      type: "HYDRATE_SESSION",
      sessionId: "s1",
      messages: [],
      forecastData: null,
      writebacks: [],
    });
    expect(state.bannerMessage).toBeNull();
  });

  it("RESET_SESSION clears bannerMessage", () => {
    const withBanner = chatReducer(initialState, {
      type: "SESSION_ERROR",
      message: "Offline",
    });
    const state = chatReducer(withBanner, {
      type: "RESET_SESSION",
      sessionId: "s2",
    });
    expect(state.bannerMessage).toBeNull();
  });

  it("SET_HYDRATING resets isHydrating and clears bannerMessage", () => {
    const withBanner = chatReducer(initialState, {
      type: "SESSION_ERROR",
      message: "Offline",
    });
    const state = chatReducer(withBanner, { type: "SET_HYDRATING" });
    expect(state.isHydrating).toBe(true);
    expect(state.bannerMessage).toBeNull();
  });
});
