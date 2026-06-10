"""Shared helpers for all seed phases."""
from __future__ import annotations

from datetime import date

from ..odoo_client import odoo

SEED_PREFIX = "odoo-ops-copilot-seed"


def get_or_create(model: str, domain: list, values: dict) -> int:
    """Return existing record ID or create and return the new one."""
    found = odoo.execute(model, "search", domain, limit=1)
    if found:
        return int(found[0])
    return int(odoo.execute(model, "create", values))


def add_months(d: date, months: int) -> date:
    """Add or subtract whole months, returning the first of the resulting month."""
    month_index = d.month - 1 + months
    return date(d.year + month_index // 12, month_index % 12 + 1, 1)
