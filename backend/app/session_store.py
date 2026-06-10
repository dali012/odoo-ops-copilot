"""Postgres-backed chat session storage for the copilot UI."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import config

MEMORY_RECORD_LIMIT = 12

_engine: Engine | None = None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=str)


def get_session_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(config.PG_URL)
    return _engine


def init_session_store() -> None:
    with get_session_engine().begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS copilot"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS copilot.chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS copilot.chat_messages (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES copilot.chat_sessions(session_id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL DEFAULT '',
                    tool_summary TEXT,
                    tool_events JSONB,
                    forecast_data JSONB,
                    status TEXT NOT NULL DEFAULT 'done',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS chat_messages_session_created_idx
                ON copilot.chat_messages (session_id, created_at, id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS copilot.writeback_actions (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES copilot.chat_sessions(session_id) ON DELETE CASCADE,
                    action_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    preview JSONB,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected', 'failed')),
                    odoo_model TEXT,
                    odoo_record_ids JSONB,
                    error TEXT,
                    created_by TEXT NOT NULL DEFAULT 'Agent',
                    decided_by TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    decided_at TIMESTAMPTZ
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS writeback_actions_session_status_idx
                ON copilot.writeback_actions (session_id, status, created_at)
                """
            )
        )
        conn.execute(text("ALTER TABLE copilot.chat_messages ADD COLUMN IF NOT EXISTS tool_events JSONB"))
        conn.execute(text("ALTER TABLE copilot.writeback_actions ADD COLUMN IF NOT EXISTS preview JSONB"))
        conn.execute(
            text(
                "ALTER TABLE copilot.writeback_actions "
                "ADD COLUMN IF NOT EXISTS created_by TEXT NOT NULL DEFAULT 'Agent'"
            )
        )
        conn.execute(text("ALTER TABLE copilot.writeback_actions ADD COLUMN IF NOT EXISTS decided_by TEXT"))
        # Migrate: ensure action_type CHECK constraint covers all 8 types.
        old_constraint = conn.execute(
            text("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_schema = 'copilot'
                  AND table_name = 'writeback_actions'
                  AND constraint_type = 'CHECK'
                  AND constraint_name LIKE '%action_type%'
            """)
        ).scalar()
        if old_constraint:
            conn.execute(
                text(
                    f"ALTER TABLE copilot.writeback_actions "
                    f"DROP CONSTRAINT {old_constraint}"
                )
            )
        conn.execute(
            text("""
                ALTER TABLE copilot.writeback_actions
                ADD CONSTRAINT writeback_actions_action_type_check
                CHECK (action_type IN (
                    'discount_rule', 'restock_rule',
                    'purchase_order', 'invoice_reminder',
                    'price_update', 'pos_pricelist',
                    'email_campaign', 'transfer_stock'
                ))
            """)
        )


def create_session() -> str:
    session_id = str(uuid.uuid4())
    with get_session_engine().begin() as conn:
        conn.execute(
            text("INSERT INTO copilot.chat_sessions (session_id) VALUES (:session_id)"),
            {"session_id": session_id},
        )
    return session_id


def session_exists(session_id: str) -> bool:
    with get_session_engine().connect() as conn:
        found = conn.execute(
            text("SELECT 1 FROM copilot.chat_sessions WHERE session_id = :session_id"),
            {"session_id": session_id},
        ).scalar()
    return bool(found)


def touch_session(session_id: str) -> None:
    with get_session_engine().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE copilot.chat_sessions
                SET updated_at = now()
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        )


def append_turn(
    *,
    session_id: str,
    user_text: str,
    assistant_text: str,
    tool_summary: str | None,
    tool_events: list[dict[str, Any]] | None = None,
    forecast_data: dict[str, Any] | None = None,
    status: str = "done",
) -> None:
    now = datetime.now(timezone.utc)
    with get_session_engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO copilot.chat_messages (session_id, role, content, status, created_at)
                VALUES (:session_id, 'user', :content, 'done', :created_at)
                """
            ),
            {"session_id": session_id, "content": user_text, "created_at": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO copilot.chat_messages
                    (session_id, role, content, tool_summary, tool_events, forecast_data, status, created_at)
                VALUES
                    (:session_id, 'assistant', :content, :tool_summary, CAST(:tool_events AS JSONB), CAST(:forecast_data AS JSONB), :status, :created_at)
                """
            ),
            {
                "session_id": session_id,
                "content": assistant_text,
                "tool_summary": tool_summary,
                "tool_events": _json_dumps(tool_events) if tool_events is not None else None,
                "forecast_data": _json_dumps(forecast_data) if forecast_data is not None else None,
                "status": status,
                "created_at": now,
            },
        )
        conn.execute(
            text(
                """
                UPDATE copilot.chat_sessions
                SET updated_at = now()
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        )


def create_writeback_action(
    *,
    session_id: str,
    action_type: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
    preview: dict[str, Any] | None = None,
    created_by: str = "Agent",
) -> dict[str, Any]:
    action_id = str(uuid.uuid4())
    with get_session_engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO copilot.writeback_actions
                    (id, session_id, action_type, title, summary, payload, preview, created_by)
                VALUES
                    (:id, :session_id, :action_type, :title, :summary, CAST(:payload AS JSONB), CAST(:preview AS JSONB), :created_by)
                """
            ),
            {
                "id": action_id,
                "session_id": session_id,
                "action_type": action_type,
                "title": title,
                "summary": summary,
                "payload": _json_dumps(payload),
                "preview": _json_dumps(preview) if preview is not None else None,
                "created_by": created_by,
            },
        )

    created = get_writeback_action(action_id)
    if created is None:
        raise RuntimeError("Write-back action could not be loaded after insert.")
    return created


def get_writeback_action(action_id: str) -> dict[str, Any] | None:
    with get_session_engine().connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, session_id, action_type, title, summary, payload, preview, status,
                       odoo_model, odoo_record_ids, error, created_by, decided_by,
                       created_at, decided_at
                FROM copilot.writeback_actions
                WHERE id = :id
                """
            ),
            {"id": action_id},
        ).mappings().first()

    return dict(row) if row else None


def update_writeback_status(
    *,
    action_id: str,
    status: str,
    odoo_model: str | None = None,
    odoo_record_ids: list[int] | None = None,
    error: str | None = None,
    decided_by: str | None = None,
) -> dict[str, Any] | None:
    with get_session_engine().begin() as conn:
        conn.execute(
            text(
                """
                UPDATE copilot.writeback_actions
                SET status = :status,
                    odoo_model = COALESCE(:odoo_model, odoo_model),
                    odoo_record_ids = CASE
                        WHEN :odoo_record_ids IS NULL THEN odoo_record_ids
                        ELSE CAST(:odoo_record_ids AS JSONB)
                    END,
                    error = :error,
                    decided_by = COALESCE(:decided_by, decided_by),
                    decided_at = now()
                WHERE id = :id
                """
            ),
            {
                "id": action_id,
                "status": status,
                "odoo_model": odoo_model,
                "odoo_record_ids": _json_dumps(odoo_record_ids) if odoo_record_ids is not None else None,
                "error": error,
                "decided_by": decided_by,
            },
        )

    return get_writeback_action(action_id)


def try_claim_writeback_action(action_id: str, decided_by: str | None = None) -> bool:
    """Atomically transition a pending action to 'approved', preventing concurrent double-execution.

    Returns True if this call won the race (row was pending and is now approved).
    Returns False if another request already claimed it.
    The caller is responsible for updating odoo_model/odoo_record_ids after the Odoo write,
    or rolling back to 'failed' if the write fails.
    """
    with get_session_engine().begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE copilot.writeback_actions
                SET status = 'approved',
                    decided_at = now(),
                    decided_by = COALESCE(:decided_by, decided_by)
                WHERE id = :id AND status = 'pending'
                """
            ),
            {"id": action_id, "decided_by": decided_by},
        )
    return result.rowcount > 0


def try_reject_writeback_action(action_id: str, decided_by: str | None = None) -> bool:
    """Atomically reject a pending action."""
    with get_session_engine().begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE copilot.writeback_actions
                SET status = 'rejected',
                    decided_at = now(),
                    decided_by = COALESCE(:decided_by, decided_by),
                    error = NULL
                WHERE id = :id AND status = 'pending'
                """
            ),
            {"id": action_id, "decided_by": decided_by},
        )
    return result.rowcount > 0


def list_writeback_actions(session_id: str) -> list[dict[str, Any]]:
    with get_session_engine().connect() as conn:
        rows = list(
            conn.execute(
                text(
                    """
                    SELECT id, session_id, action_type, title, summary, payload, preview, status,
                           odoo_model, odoo_record_ids, error, created_by, decided_by,
                           created_at, decided_at
                    FROM copilot.writeback_actions
                    WHERE session_id = :session_id
                    ORDER BY created_at DESC, id DESC
                    """
                ),
                {"session_id": session_id},
            ).mappings()
        )
    return [dict(row) for row in rows]


def get_session_snapshot(session_id: str) -> dict[str, Any] | None:
    with get_session_engine().connect() as conn:
        session = conn.execute(
            text(
                """
                SELECT session_id
                FROM copilot.chat_sessions
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        ).first()
        if session is None:
            return None

        raw_rows = list(
            conn.execute(
                text(
                    """
                    SELECT id, role, content, status, tool_events, forecast_data
                    FROM copilot.chat_messages
                    WHERE session_id = :session_id
                    ORDER BY created_at, id
                    """
                ),
                {"session_id": session_id},
            ).mappings()
        )

    messages = [
        {
            "id": f"db-{row['id']}",
            "role": row["role"],
            "text": row["content"],
            "toolEvents": row["tool_events"] or [],
            "status": row["status"] if row["role"] == "assistant" else "done",
        }
        for row in raw_rows
    ]

    # Derive forecast_data from already-fetched rows; no second round-trip needed.
    forecast_data = next(
        (row["forecast_data"] for row in reversed(raw_rows) if row["forecast_data"] is not None),
        None,
    )

    return {"session_id": session_id, "messages": messages, "forecastData": forecast_data}


def get_prompt_history(session_id: str) -> list[dict[str, str]]:
    with get_session_engine().connect() as conn:
        rows = list(
            conn.execute(
                text(
                    """
                    SELECT role, content, tool_summary
                    FROM copilot.chat_messages
                    WHERE session_id = :session_id
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit
                    """
                ),
                {"session_id": session_id, "limit": MEMORY_RECORD_LIMIT},
            ).mappings()
        )

    history: list[dict[str, str]] = []
    for row in reversed(rows):
        content = row["content"] or ""
        if row["role"] == "assistant" and row["tool_summary"]:
            content = f"{content}\n\n{row['tool_summary']}"
        if content.strip():
            history.append({"role": row["role"], "content": content})

    return history


def summarize_tool_result(name: str, input_data: dict[str, Any], output: dict[str, Any]) -> str:
    if "error" in output:
        return f"Tool context: {name} failed with error: {output['error']}."

    if name == "forecast_demand":
        forecast = output.get("forecast") or []
        history = output.get("history") or []
        category = output.get("category") or input_data.get("category") or "unknown category"
        first_forecast = forecast[0] if forecast else {}
        month = first_forecast.get("month", "next period")
        units = first_forecast.get("units", "unknown")
        return (
            f"Tool context: forecast_demand for {category} returned {len(history)} history rows "
            f"and {len(forecast)} forecast rows; forecast for {month}: {units} units."
        )

    if name == "sql_analytics":
        row_count = output.get("row_count", 0)
        sql = str(input_data.get("sql", "")).strip().replace("\n", " ")
        return f"Tool context: sql_analytics returned {row_count} rows for SQL: {sql[:240]}."

    if name == "odoo_query":
        model = input_data.get("model", "unknown model")
        count = output.get("count", 0)
        return f"Tool context: odoo_query read {count} records from {model}."

    if name == "simulate_discount_impact":
        products = output.get("products") or []
        totals = output.get("totals") or {}
        return (
            f"Tool context: simulate_discount_impact evaluated {len(products)} products; "
            f"revenue delta {totals.get('revenue_delta', 'unknown')}, "
            f"margin delta {totals.get('margin_delta', 'unknown')}."
        )

    if name in {
        "propose_discount_rule", "propose_restock_rule",
        "propose_purchase_order", "propose_invoice_reminder",
        "propose_price_update", "propose_pos_pricelist",
        "propose_email_campaign", "propose_transfer_stock",
    }:
        action_type = output.get("action_type", "write-back")
        title = output.get("title", "pending approval")
        return f"Tool context: drafted {action_type} proposal pending human approval: {title}."

    return f"Tool context: {name} completed."
