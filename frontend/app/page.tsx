"use client";

import { useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { ErrorBanner } from "@/components/ErrorBanner";
import { RightRail } from "@/components/RightRail";
import { StatusBar } from "@/components/StatusBar";
import { useBreakpoint } from "@/hooks/useBreakpoint";
import { useChat } from "@/hooks/useChat";

export default function Home() {
  const {
    messages,
    forecastData,
    isHydrating,
    isStreaming,
    submit,
    newChat,
    updateWriteback,
    writebacks,
    bannerMessage,
    reloadSession,
  } = useChat();

  const breakpoint = useBreakpoint();
  const [railOpen, setRailOpen] = useState(false);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        background: "var(--ds-background-200)",
      }}
    >
      <StatusBar
        onNewChat={
          breakpoint !== "narrow"
            ? () => {
                void newChat();
              }
            : undefined
        }
        disableNewChat={isStreaming || isHydrating}
        breakpoint={breakpoint}
        railOpen={railOpen}
        onToggleRail={() => setRailOpen((prev) => !prev)}
      />
      {bannerMessage && (
        <ErrorBanner message={bannerMessage} onRetry={reloadSession} />
      )}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <ChatPanel
          messages={messages}
          isStreaming={isStreaming}
          isHydrating={isHydrating}
          onSubmit={submit}
          onWritebackDecision={updateWriteback}
        />
        <RightRail
          forecastData={forecastData}
          messages={messages}
          writebacks={writebacks}
          breakpoint={breakpoint}
          railOpen={railOpen}
          onCloseRail={() => setRailOpen(false)}
          onNewChat={() => {
            void newChat();
          }}
        />
      </div>
    </div>
  );
}
