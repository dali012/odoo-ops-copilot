"""Bounded, visible error recovery for the agent tool loop.

When a tool errors at runtime (e.g. SQL that parses but hits a bad column) or
returns nothing, we feed actionable guidance back to the model so it can
self-correct exactly once. A second failure tells the model to stop and explain
the limitation instead of looping. All state here is per-request and the logic
is pure, so it is unit-tested in test_recovery.py.
"""
from __future__ import annotations

MAX_RETRIES_PER_TOOL = 1

# Read tools where an empty result is worth a gentle "double-check" nudge.
_EMPTY_RESULT_TOOLS = {"sql_analytics", "odoo_query"}


class RecoveryTracker:
    """Tracks consecutive failures per tool name within a single chat turn."""

    def __init__(self, max_retries: int = MAX_RETRIES_PER_TOOL) -> None:
        self.max_retries = max_retries
        self._failures: dict[str, int] = {}

    def attempt_number(self, name: str) -> int:
        """1-based attempt number for the *next* call to this tool."""
        return self._failures.get(name, 0) + 1

    def record_error(self, name: str) -> int:
        """Record a failure for this tool; return the failure count so far."""
        self._failures[name] = self._failures.get(name, 0) + 1
        return self._failures[name]

    def record_success(self, name: str) -> bool:
        """Record a success; return True if it recovered a previously-failed tool."""
        recovered = self._failures.get(name, 0) > 0
        self._failures[name] = 0
        return recovered

    def budget_exhausted(self, name: str) -> bool:
        """True once the tool has failed more than its retry budget allows."""
        return self._failures.get(name, 0) > self.max_retries


def is_empty_result(name: str, output: dict) -> bool:
    """True when a read tool succeeded but returned no rows."""
    if "error" in output:
        return False
    if name == "sql_analytics":
        return output.get("row_count") == 0
    if name == "odoo_query":
        return output.get("count") == 0
    return False


def empty_result_note(name: str) -> str:
    """Soft guidance attached to a zero-row result (not an error)."""
    return (
        "The query succeeded but returned 0 rows. Before telling the user there is "
        "no data, double-check once whether a filter, name, or date range is too "
        "narrow — Odoo stores translatable names as jsonb (e.g. pt.name->>'en_US'), "
        "and a misspelled category or an off-by-one date window often yields 0 rows."
    )


def build_retry_hint(name: str, error: str, *, exhausted: bool) -> str:
    """Actionable guidance appended to a failed tool result.

    This is the tunable heart of the recovery policy — adjust the wording here to
    change how the agent self-corrects.
    """
    if exhausted:
        return (
            f"The {name} tool has now failed twice. Do not call it again. Explain "
            "the limitation to the user in plain language and, if possible, suggest "
            "an alternative approach."
        )
    if name == "sql_analytics":
        return (
            "The SQL parsed but failed at runtime. Check your column and table names "
            "against the schema glossary in the system prompt — Odoo stores "
            "translatable names as jsonb (e.g. pt.name->>'en_US'), and many columns "
            "differ from their UI labels. Fix the query and try once more."
        )
    return (
        f"The {name} call failed. Review the error, correct the arguments, and try "
        "once more. If it fails again, explain the issue to the user instead of retrying."
    )
