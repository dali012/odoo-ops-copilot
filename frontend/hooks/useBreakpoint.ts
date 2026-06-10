"use client";

import { useEffect, useState } from "react";

export type Breakpoint = "wide" | "mid" | "narrow";

function getBreakpoint(width: number): Breakpoint {
  if (width >= 1100) return "wide";
  if (width >= 800) return "mid";
  return "narrow";
}

export function useBreakpoint(): Breakpoint {
  const [breakpoint, setBreakpoint] = useState<Breakpoint>(() =>
    typeof document !== "undefined"
      ? getBreakpoint(document.documentElement.clientWidth)
      : "wide",
  );

  useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      const width =
        entries[0]?.contentRect.width ??
        document.documentElement.clientWidth;
      setBreakpoint(getBreakpoint(width));
    });

    observer.observe(document.documentElement);
    return () => observer.disconnect();
  }, []);

  return breakpoint;
}
