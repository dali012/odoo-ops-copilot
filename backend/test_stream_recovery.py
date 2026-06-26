"""Async tests for the streaming agent loop and bounded error recovery.

These mock the Anthropic async stream entirely — no network, no DB — so they run
in the offline suite and prove two things end to end:
  1. stream_chat emits token-level text_delta SSE events (streaming works).
  2. a tool that errors at runtime is fed back, retried once, and the retry +
     recovery are labelled in the trace.
"""
import json
import unittest
from unittest.mock import patch

import app.agent as agent


# --- Fakes that mimic the Anthropic streaming SDK shape --------------------

class FakeTextDelta:
    type = "text_delta"

    def __init__(self, text: str) -> None:
        self.text = text


class FakeDeltaEvent:
    type = "content_block_delta"

    def __init__(self, text: str) -> None:
        self.delta = FakeTextDelta(text)


class FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, name: str, tool_input: dict, block_id: str) -> None:
        self.name = name
        self.input = tool_input
        self.id = block_id


class FakeFinal:
    def __init__(self, content: list, stop_reason: str) -> None:
        self.content = content
        self.stop_reason = stop_reason


class FakeStream:
    """One streamed assistant turn: some delta events + a final message."""

    def __init__(self, events: list, final: FakeFinal) -> None:
        self._events = events
        self._final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def __aiter__(self):  # pragma: no cover - trivial generator
        for event in self._events:
            yield event

    async def get_final_message(self):
        return self._final


class FakeMessages:
    def __init__(self, streams: list[FakeStream]) -> None:
        self._streams = streams
        self._i = 0

    def stream(self, **_kwargs):
        stream = self._streams[self._i]
        self._i += 1
        return stream


class FakeClient:
    def __init__(self, streams: list[FakeStream]) -> None:
        self.messages = FakeMessages(streams)


def _collect_events(sse_chunks: list[str]) -> list[dict]:
    events = []
    for chunk in sse_chunks:
        line = chunk.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


class StreamingTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, streams, run_tool_side_effect=None):
        with (
            patch.object(agent, "async_client", FakeClient(streams)),
            patch.object(agent, "get_prompt_history", return_value=[]),
            patch.object(agent, "append_turn", return_value=None),
            patch.object(agent, "summarize_tool_result", return_value="summary"),
            patch.object(agent, "build_tool_evidence", return_value={"title": "t"}),
        ):
            if run_tool_side_effect is not None:
                with patch.object(agent, "run_tool", side_effect=run_tool_side_effect):
                    return [chunk async for chunk in agent.stream_chat("hi", "s1")]
            return [chunk async for chunk in agent.stream_chat("hi", "s1")]

    async def test_streams_text_deltas_token_by_token(self):
        final = FakeFinal([FakeTextBlock("Hello world")], stop_reason="end_turn")
        streams = [FakeStream([FakeDeltaEvent("Hello "), FakeDeltaEvent("world")], final)]

        events = _collect_events(await self._run(streams))

        deltas = [e["text"] for e in events if e["type"] == "text_delta"]
        self.assertEqual(deltas, ["Hello ", "world"])
        self.assertEqual(events[-1]["type"], "done")

    async def test_tool_error_is_retried_and_recovery_is_labelled(self):
        # Turn 1: model calls sql_analytics -> errors at runtime.
        turn1 = FakeStream(
            [],
            FakeFinal(
                [FakeToolUseBlock("sql_analytics", {"sql": "SELECT bad"}, "t1")],
                stop_reason="tool_use",
            ),
        )
        # Turn 2: model retries sql_analytics -> succeeds.
        turn2 = FakeStream(
            [],
            FakeFinal(
                [FakeToolUseBlock("sql_analytics", {"sql": "SELECT good"}, "t2")],
                stop_reason="tool_use",
            ),
        )
        # Turn 3: model answers.
        turn3 = FakeStream(
            [FakeDeltaEvent("Fixed it.")],
            FakeFinal([FakeTextBlock("Fixed it.")], stop_reason="end_turn"),
        )

        run_tool_results = [
            json.dumps({"error": "column bad does not exist"}),
            json.dumps({"rows": [{"n": 1}], "row_count": 1, "row_cap": 100}),
        ]

        events = _collect_events(
            await self._run([turn1, turn2, turn3], run_tool_side_effect=run_tool_results)
        )

        # First tool_result carries the runtime error.
        first_result = next(e for e in events if e["type"] == "tool_result")
        self.assertEqual(first_result["error"], "column bad does not exist")
        self.assertNotIn("recovered", first_result)

        # The retry tool_start is labelled as a retry (attempt 2).
        retry_start = next(
            e for e in events if e["type"] == "tool_start" and e.get("is_retry")
        )
        self.assertEqual(retry_start["attempt"], 2)

        # The retry's tool_result is labelled recovered.
        recovered_result = next(
            e for e in events if e["type"] == "tool_result" and e.get("recovered")
        )
        self.assertTrue(recovered_result["recovered"])
        self.assertEqual(events[-1]["type"], "done")


if __name__ == "__main__":
    unittest.main()
