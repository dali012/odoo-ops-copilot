"""A minimal, readable tool-calling loop over the Anthropic Messages API.

No agent framework on purpose: the mechanics are the interesting part to review.
"""
import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from anthropic import Anthropic, AsyncAnthropic, BadRequestError

log = logging.getLogger(__name__)

from .config import config
from .evidence import build_tool_evidence
from .schema_context import build_system_prompt
from .session_store import (
    append_turn,
    create_writeback_action,
    get_prompt_history,
    summarize_tool_result,
)
from .tools import TOOL_SCHEMAS as _ANALYTICS_SCHEMAS
from .tools import DISPATCH as _ANALYTICS_DISPATCH
from .tools_writeback import TOOL_SCHEMAS as _WRITEBACK_SCHEMAS
from .tools_writeback import DISPATCH as _WRITEBACK_DISPATCH
from .writeback_preview import prepare_writeback_action

TOOL_SCHEMAS = _ANALYTICS_SCHEMAS + _WRITEBACK_SCHEMAS
_COMBINED_DISPATCH = {**_ANALYTICS_DISPATCH, **_WRITEBACK_DISPATCH}


def run_tool(name: str, args: dict) -> str:
    import json
    try:
        result = _COMBINED_DISPATCH[name](**args)
    except Exception as exc:
        result = {"error": str(exc)}
    return json.dumps(result, default=str)

client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
async_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

SYSTEM = build_system_prompt()

MAX_TURNS = 6


def chat(message: str) -> str:
    messages = [{"role": "user", "content": message}]

    try:
        for _ in range(MAX_TURNS):
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                system=SYSTEM,
                tools=TOOL_SCHEMAS,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason != "tool_use":
                return "".join(b.text for b in resp.content if b.type == "text")

            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    output = run_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                    })
            messages.append({"role": "user", "content": tool_results})

    except BadRequestError as exc:
        error_body = str(exc)
        if "credit balance" in error_body.lower():
            return (
                "The Anthropic API key has insufficient credits. "
                "Please add credits at console.anthropic.com/settings/billing."
            )
        raise

    return "Stopped after the maximum number of reasoning steps."


def sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


async def stream_chat(message: str, session_id: str) -> AsyncGenerator[str, None]:
    messages = await asyncio.to_thread(get_prompt_history, session_id)
    messages.append({"role": "user", "content": message})
    # last_turn_text holds only the most recent turn's text so we persist
    # the final user-facing reply, not a concatenation of all intermediate turns.
    last_turn_text = ""
    tool_summaries: list[str] = []
    turn_tool_events: list[dict] = []
    forecast_data: dict | None = None
    persisted = False

    async def persist_turn(assistant_text: str, status: str = "done") -> None:
        nonlocal persisted
        if persisted:
            return
        persisted = True
        await asyncio.to_thread(
            append_turn,
            session_id=session_id,
            user_text=message,
            assistant_text=assistant_text,
            tool_summary="\n".join(tool_summaries) or None,
            forecast_data=forecast_data,
            tool_events=turn_tool_events,
            status=status,
        )

    try:
        for _ in range(MAX_TURNS):
            turn_text_parts: list[str] = []
            async with async_client.messages.stream(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                system=SYSTEM,
                tools=TOOL_SCHEMAS,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and hasattr(event.delta, "type")
                        and event.delta.type == "text_delta"
                    ):
                        turn_text_parts.append(event.delta.text)
                        yield sse({"type": "text_delta", "text": event.delta.text})

                final = await stream.get_final_message()

            last_turn_text = "".join(turn_text_parts)
            messages.append({"role": "assistant", "content": final.content})

            if final.stop_reason != "tool_use":
                await persist_turn(last_turn_text, "done")
                yield sse({"type": "done"})
                return

            tool_results = []
            for block in final.content:
                if block.type != "tool_use":
                    continue

                yield sse({"type": "tool_start", "name": block.name, "input": block.input})

                output_str = await asyncio.to_thread(run_tool, block.name, block.input)
                try:
                    output = json.loads(output_str)
                except json.JSONDecodeError:
                    output = {"error": output_str}

                if block.name in {
                    "propose_discount_rule", "propose_restock_rule",
                    "propose_purchase_order", "propose_invoice_reminder",
                    "propose_price_update", "propose_pos_pricelist",
                    "propose_email_campaign", "propose_transfer_stock",
                    "propose_inventory_adjustment",
                    "propose_vendor_price_update",
                    "propose_sale_order_cancel",
                } and "error" not in output:
                    try:
                        prepared_payload, preview = await asyncio.to_thread(
                            prepare_writeback_action,
                            output["action_type"],
                            output["payload"],
                        )
                        output["payload"] = prepared_payload
                        output["preview"] = preview
                    except Exception as exc:
                        output = {"error": f"Could not build write-back preview: {exc}"}

                tool_summary = summarize_tool_result(block.name, block.input, output)
                tool_summaries.append(tool_summary)
                evidence = build_tool_evidence(
                    block.name,
                    block.input,
                    output,
                    summary=tool_summary,
                )

                result_event: dict = {"type": "tool_result", "name": block.name}
                persisted_tool_event: dict = {
                    "id": f"db-tool-{len(turn_tool_events) + 1}",
                    "name": block.name,
                    "status": "done",
                    "input": block.input,
                    "evidence": evidence,
                }
                if "error" in output:
                    result_event["error"] = output["error"]
                    persisted_tool_event["error"] = output["error"]
                elif block.name == "sql_analytics":
                    result_event["sql"] = block.input.get("sql", "")
                    result_event["row_count"] = output.get("row_count", 0)
                    result_event["rows"] = output.get("rows", [])[:20]
                    persisted_tool_event.update({
                        "sql": result_event["sql"],
                        "rowCount": result_event["row_count"],
                        "rows": result_event["rows"],
                    })
                elif block.name == "forecast_demand":
                    result_event["category"] = output.get("category", "")
                    result_event["history"] = output.get("history", [])
                    result_event["forecast"] = output.get("forecast", [])
                    forecast_data = {
                        "category": result_event["category"],
                        "history": result_event["history"],
                        "forecast": result_event["forecast"],
                    }
                    persisted_tool_event["forecastData"] = forecast_data
                elif block.name == "odoo_query":
                    result_event["count"] = output.get("count", 0)
                elif block.name in {
                    "propose_discount_rule", "propose_restock_rule",
                    "propose_purchase_order", "propose_invoice_reminder",
                    "propose_price_update", "propose_pos_pricelist",
                    "propose_email_campaign", "propose_transfer_stock",
                    "propose_inventory_adjustment",
                    "propose_vendor_price_update",
                    "propose_sale_order_cancel",
                }:
                    proposal = await asyncio.to_thread(
                        create_writeback_action,
                        session_id=session_id,
                        action_type=output["action_type"],
                        title=output["title"],
                        summary=output["summary"],
                        payload=output["payload"],
                        preview=output.get("preview"),
                    )
                    result_event["writeback"] = proposal
                    output["writeback_action_id"] = proposal["id"]
                    persisted_tool_event["writeback"] = proposal
                elif block.name == "simulate_discount_impact":
                    result_event["simulation"] = output
                    persisted_tool_event["simulation"] = output

                result_event["evidence"] = evidence
                persisted_tool_event["evidence"] = evidence
                turn_tool_events.append(persisted_tool_event)

                output_str = json.dumps(output, default=str)

                yield sse(result_event)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output_str,
                })

            messages.append({"role": "user", "content": tool_results})

        await persist_turn(last_turn_text, "done")
        yield sse({"type": "done"})

    except BadRequestError as exc:
        msg = (
            "API credits exhausted. Please add credits at console.anthropic.com/settings/billing."
            if "credit balance" in str(exc).lower()
            else f"API error: {exc}"
        )
        await persist_turn(msg, "error")
        yield sse({"type": "error", "message": msg})
    except Exception as exc:
        log.exception("stream_chat unhandled error")
        msg = "An internal error occurred."
        await persist_turn(msg, "error")
        yield sse({"type": "error", "message": msg})
