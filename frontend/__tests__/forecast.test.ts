import { parseForecastSeries } from "@/lib/forecast";

describe("parseForecastSeries", () => {
  it("maps valid items to month/units pairs", () => {
    const input = [
      { month: "2026-01-01", units: 42 },
      { month: "2026-02-01", units: 37.5 },
    ];
    expect(parseForecastSeries(input)).toEqual([
      { month: "2026-01-01", units: 42 },
      { month: "2026-02-01", units: 37.5 },
    ]);
  });

  it("returns empty array for non-array input", () => {
    expect(parseForecastSeries(null)).toEqual([]);
    expect(parseForecastSeries(undefined)).toEqual([]);
    expect(parseForecastSeries("string")).toEqual([]);
  });

  it("filters out items missing month or units", () => {
    const input = [
      { month: "2026-01-01", units: 10 },
      { month: "2026-02-01" },
      { units: 5 },
      null,
    ];
    expect(parseForecastSeries(input)).toEqual([
      { month: "2026-01-01", units: 10 },
    ]);
  });

  it("coerces non-numeric units to 0", () => {
    const input = [{ month: "2026-01-01", units: "bad" }];
    expect(parseForecastSeries(input)).toEqual([
      { month: "2026-01-01", units: 0 },
    ]);
  });
});
