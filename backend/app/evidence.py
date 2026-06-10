"""Compact, UI-safe evidence objects for streamed and persisted tool results."""

from __future__ import annotations

from typing import Any


def _rows(value: Any, limit: int = 8) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value[:limit] if isinstance(row, dict)]


def build_tool_evidence(
    name: str,
    input_data: dict[str, Any],
    output: dict[str, Any],
    *,
    summary: str,
) -> dict[str, Any]:
    if "error" in output:
        return {
            "title": f"{name} failed",
            "data_used": "Tool execution error",
            "rows_returned": 0,
            "top_rows": [],
            "why": str(output["error"]),
        }

    if name == "sql_analytics":
        rows = _rows(output.get("rows"))
        return {
            "title": "SQL analytics",
            "data_used": "Odoo Postgres tables from the schema glossary",
            "sql": str(input_data.get("sql") or ""),
            "rows_returned": int(output.get("row_count") or len(rows)),
            "top_rows": rows,
            "why": summary,
        }

    if name == "forecast_demand":
        history = output.get("history") or []
        forecast = output.get("forecast") or []
        return {
            "title": f"{output.get('category') or input_data.get('category') or 'Demand'} forecast",
            "data_used": "Confirmed sales history grouped by month and category",
            "rows_returned": len(history) + len(forecast),
            "top_rows": _rows(history[-6:] + forecast, 8),
            "why": summary,
        }

    if name == "odoo_query":
        return {
            "title": f"Odoo query: {input_data.get('model') or 'model'}",
            "data_used": "Odoo XML-RPC search_read",
            "rows_returned": int(output.get("count") or 0),
            "top_rows": _rows(output.get("records")),
            "why": summary,
        }

    if name == "simulate_discount_impact":
        return {
            "title": "Discount impact simulation",
            "data_used": "90-day confirmed sales, list price, and standard cost",
            "rows_returned": len(output.get("products") or []),
            "top_rows": _rows(output.get("products")),
            "why": summary,
        }

    if name.startswith("propose_"):
        return {
            "title": output.get("title") or "Write-back proposal",
            "data_used": "Proposal payload validated and previewed by the server",
            "rows_returned": 1,
            "top_rows": [{"action_type": output.get("action_type"), "summary": output.get("summary")}],
            "why": output.get("summary") or summary,
        }

    return {
        "title": name,
        "data_used": "Tool result",
        "rows_returned": 0,
        "top_rows": [],
        "why": summary,
    }
