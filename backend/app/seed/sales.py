# backend/app/seed/sales.py
"""Seed 30 months of confirmed sale orders."""
from __future__ import annotations

import random
from datetime import date, timedelta

from ._base import SEED_PREFIX, add_months
from ..odoo_client import odoo

MONTHS_TO_SEED = 30

SEASONALITY: dict[str, list[float]] = {
    "Outerwear":   [1.55, 1.35, 1.05, 0.75, 0.45, 0.32, 0.30, 0.45, 0.85, 1.20, 1.60, 1.85],
    "Footwear":    [0.90, 0.85, 1.00, 1.15, 1.10, 1.05, 1.00, 1.20, 1.30, 1.10, 0.95, 1.05],
    "Accessories": [0.85, 0.80, 0.90, 1.00, 1.05, 1.00, 0.95, 1.05, 1.10, 1.20, 1.45, 1.75],
    "Knitwear":    [1.45, 1.30, 1.05, 0.80, 0.55, 0.40, 0.35, 0.50, 0.85, 1.20, 1.55, 1.70],
}

BASE_MONTHLY_UNITS: dict[str, int] = {
    "Outerwear": 42, "Footwear": 58, "Accessories": 75, "Knitwear": 36,
}


def _monthly_units(category: str, month: date, start_month: date, rng: random.Random) -> int:
    seasonal = SEASONALITY[category][month.month - 1]
    baseline = BASE_MONTHLY_UNITS[category]
    offset = (month.year - start_month.year) * 12 + (month.month - start_month.month)
    trend = 1 + offset * 0.004
    return max(4, int(round(rng.gauss(baseline * seasonal * trend, baseline * 0.10))))


def _split_units(total: int, parts: int, rng: random.Random) -> list[int]:
    if parts <= 1 or total <= parts:
        return [max(1, total)]
    cuts = sorted(rng.sample(range(1, total), parts - 1))
    return [b - a for a, b in zip([0, *cuts], [*cuts, total])]


def seed_sales(product_ids: dict[str, list[int]], customer_ids: list[int]) -> tuple[int, int]:
    """Create 30 months of confirmed sale orders.

    Args:
        product_ids:  {category_name: [product.product id, ...]} from seed_catalog().
        customer_ids: [res.partner id, ...] from seed_catalog().

    Returns:
        (created_count, skipped_count)
    """
    today = date.today().replace(day=1)
    end_month = add_months(today, -1)
    start_month = add_months(end_month, -(MONTHS_TO_SEED - 1))

    created_count = 0
    skipped_count = 0
    month = start_month

    while month <= end_month:
        for cat, pp_ids in product_ids.items():
            # Deterministic RNG per (category, month) so the number of order
            # indices is identical across runs, keeping the idempotency key space stable.
            rng = random.Random(f"{cat}:{month:%Y-%m}")
            total_units = _monthly_units(cat, month, start_month, rng)
            order_parts = rng.randint(3, min(6, max(3, total_units)))
            for idx, qty in enumerate(_split_units(total_units, order_parts, rng), start=1):
                ref = f"{SEED_PREFIX}:{cat}:{month:%Y-%m}:{idx}"
                existing = odoo.execute(
                    "sale.order", "search", [["client_order_ref", "=", ref]], limit=1
                )
                if existing:
                    skipped_count += 1
                    continue

                order_day = month + timedelta(days=rng.randint(0, 26))
                date_str = order_day.strftime("%Y-%m-%d 12:00:00")
                pp_id = rng.choice(pp_ids)
                so_id = int(odoo.execute("sale.order", "create", {
                    "partner_id": rng.choice(customer_ids),
                    "date_order": date_str,
                    "client_order_ref": ref,
                    "order_line": [(0, 0, {"product_id": pp_id, "product_uom_qty": qty})],
                }))
                odoo.execute("sale.order", "action_confirm", [so_id])
                # action_confirm resets date_order to now; restore historical date.
                odoo.execute("sale.order", "write", [so_id], {"date_order": date_str})
                created_count += 1

        month = add_months(month, 1)

    print(f"  [sales] Created {created_count} orders, skipped {skipped_count} existing.")
    return created_count, skipped_count
