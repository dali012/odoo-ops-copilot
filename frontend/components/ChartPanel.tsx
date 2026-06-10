"use client";

import { useMemo } from "react";
import {
  Bar,
  Cell,
  ComposedChart,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ForecastData } from "@/types/chat";
import { parseForecastSeries } from "@/lib/forecast";

type ChartEntry = {
  month: string;
  units: number;
  isForecast: boolean;
  unitsLabel: string;
};

type TooltipPayload = { value: number }[];

function EmptyState() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        gap: "8px",
        padding: "24px",
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: "32px",
          height: "24px",
          borderBottom: "1px solid var(--ds-border-strong)",
          display: "flex",
          alignItems: "end",
          justifyContent: "center",
          gap: "3px",
          opacity: 0.55,
        }}
      >
        {[12, 19, 15, 23].map((height, index) => (
          <span
            key={index}
            style={{
              width: "4px",
              height,
              background: "var(--ds-gray-700)",
              borderRadius: "2px 2px 0 0",
            }}
          />
        ))}
      </div>
      <p
        style={{
          fontSize: "12px",
          color: "var(--ds-gray-700)",
          lineHeight: 1.5,
          margin: 0,
        }}
      >
        Ask about a category to see a forecast
      </p>
      <div
        style={{
          marginTop: "4px",
          padding: "4px 12px",
          background: "var(--ds-gray-100)",
          border: "1px solid var(--ds-border)",
          borderRadius: "16px",
          fontSize: "11px",
          color: "var(--ds-gray-800)",
        }}
      >
        Forecast Outerwear demand
      </div>
    </div>
  );
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayload;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div
      style={{
        background: "var(--ds-gray-100)",
        border: "1px solid var(--ds-border)",
        borderRadius: "6px",
        padding: "6px 10px",
        fontSize: "11px",
        color: "var(--ds-gray-900)",
      }}
    >
      <div style={{ color: "var(--ds-gray-700)", marginBottom: "2px" }}>
        {label}
      </div>
      <div>{payload[0].value} units</div>
    </div>
  );
}

function normalizeForecastData(forecastData: ForecastData): ForecastData {
  return {
    category: forecastData.category || "Demand",
    history: parseForecastSeries(forecastData.history),
    forecast: parseForecastSeries(forecastData.forecast),
  };
}

function buildChartData(forecastData: ForecastData): ChartEntry[] {
  const history = parseForecastSeries(forecastData.history);
  const forecast = parseForecastSeries(forecastData.forecast);

  return [
    ...history.map((item) => ({
      ...item,
      isForecast: false,
      unitsLabel: "",
    })),
    ...forecast.map((item) => ({
      ...item,
      isForecast: true,
      unitsLabel: String(item.units),
    })),
  ];
}

export function ChartPanel({
  forecastData,
  embedded = false,
}: {
  forecastData: ForecastData | null;
  embedded?: boolean;
}) {
  const memoized = useMemo(() => {
    if (!forecastData) return null;
    const normalized = normalizeForecastData(forecastData);
    return { normalized, entries: buildChartData(normalized) };
  }, [forecastData]);

  const normalizedForecastData = memoized?.normalized ?? null;
  const chartData = memoized?.entries ?? [];

  return (
    <div
      style={{
        width: embedded ? "100%" : "288px",
        flexShrink: 0,
        background: "var(--ds-background-100)",
        borderLeft: embedded ? "none" : "1px solid var(--ds-border)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
      }}
    >
      {!normalizedForecastData ? (
        <EmptyState />
      ) : (
        <>
          <div
            style={{
              padding: "12px 16px",
              borderBottom: "1px solid var(--ds-border)",
              flexShrink: 0,
            }}
          >
            <div
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: "var(--ds-gray-1000)",
              }}
            >
              {normalizedForecastData.category} Demand Forecast
            </div>
            <div
              style={{
                fontSize: "10px",
                color: "var(--ds-gray-700)",
                marginTop: "2px",
              }}
            >
              {normalizedForecastData.history.length} months history -{" "}
              {normalizedForecastData.forecast.length} ahead
            </div>
          </div>

          <div style={{ flex: 1, padding: "12px 8px 8px", minHeight: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={chartData}
                margin={{ top: 16, right: 8, left: -24, bottom: 0 }}
              >
                <XAxis
                  dataKey="month"
                  tickFormatter={(value) => {
                    const date = new Date(String(value));
                    return date.toLocaleDateString("en", { month: "short" });
                  }}
                  tick={{
                    fontSize: 9,
                    fill: "var(--ds-gray-700)",
                    fontFamily: "var(--font-geist-mono)",
                  }}
                  axisLine={{ stroke: "var(--ds-border)" }}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{
                    fontSize: 9,
                    fill: "var(--ds-gray-700)",
                    fontFamily: "var(--font-geist-mono)",
                  }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  content={<CustomTooltip />}
                  cursor={{ fill: "rgba(255,255,255,0.03)" }}
                />
                <Bar dataKey="units" radius={[2, 2, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`${entry.month}-${index}`}
                      fill={entry.isForecast ? "transparent" : "#0070f3"}
                      fillOpacity={entry.isForecast ? 1 : 0.45}
                      stroke={entry.isForecast ? "#50e3c2" : undefined}
                      strokeWidth={entry.isForecast ? 1 : undefined}
                      strokeDasharray={entry.isForecast ? "4 2" : undefined}
                    />
                  ))}
                  <LabelList
                    dataKey="unitsLabel"
                    position="top"
                    style={{
                      fontSize: "9px",
                      fill: "var(--ds-green-400)",
                      fontFamily: "var(--font-geist-mono)",
                    }}
                  />
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <div
            style={{
              display: "flex",
              gap: "12px",
              padding: "8px 16px",
              borderTop: "1px solid var(--ds-border)",
              flexShrink: 0,
            }}
          >
            {[
              { color: "#0070f3", opacity: 0.45, label: "History" },
              { color: "#50e3c2", opacity: 1, label: "Forecast" },
            ].map((item) => (
              <div
                key={item.label}
                style={{ display: "flex", alignItems: "center", gap: "5px" }}
              >
                <div
                  style={{
                    width: "10px",
                    height: "10px",
                    borderRadius: "2px",
                    background:
                      item.label === "Forecast" ? "transparent" : item.color,
                    opacity: item.opacity,
                    border:
                      item.label === "Forecast"
                        ? `1px dashed ${item.color}`
                        : "none",
                  }}
                />
                <span style={{ fontSize: "10px", color: "var(--ds-gray-700)" }}>
                  {item.label}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
