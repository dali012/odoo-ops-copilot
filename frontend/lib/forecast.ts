export function parseForecastSeries(
  value: unknown,
): { month: string; units: number }[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(
      (item): item is { month: unknown; units: unknown } =>
        typeof item === "object" &&
        item !== null &&
        "month" in item &&
        "units" in item,
    )
    .map((item) => ({
      month: String(item.month),
      units: Number(item.units) || 0,
    }));
}
