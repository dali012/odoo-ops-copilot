# backend/app/seed/stock_levels.py
"""Seed a deterministic stockout signal.

Purchases stock every product generously (12 months x 20-50 units), so on a
fresh seed nothing is ever at risk of running out. This step drives the single
highest-velocity product (by units sold in the last 90 days) to zero on-hand
stock, giving `stockout_risk` a genuine `out_of_stock` product to surface.

Picking the top recent seller dynamically (rather than a hardcoded name) keeps
this in lock-step with how `stockout_risk` measures velocity: both read from
`sale.order.line` over the trailing 90 days, so they always agree on the #1
at-risk product. Mirrors the Odoo 18 `stock.quant` inventory-adjustment API
used in app.writeback.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..odoo_client import odoo

STOCKOUT_LOOKBACK_DAYS = 90


def _top_recent_product(days: int = STOCKOUT_LOOKBACK_DAYS) -> int | None:
    """product.product id with the most units sold in confirmed orders over `days`."""
    cutoff = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    lines = odoo.search_read(
        "sale.order.line",
        domain=[
            ["order_id.state", "in", ["sale", "done"]],
            ["order_id.date_order", ">=", cutoff],
            ["product_id", "!=", False],
        ],
        fields=["product_id", "product_uom_qty"],
    )
    totals: dict[int, float] = {}
    for line in lines:
        pid = int(line["product_id"][0])
        totals[pid] = totals.get(pid, 0.0) + float(line["product_uom_qty"] or 0)
    if not totals:
        return None
    return max(totals, key=lambda pid: totals[pid])


def _internal_stock_location() -> int | None:
    ids = odoo.execute(
        "stock.location",
        "search",
        [["usage", "=", "internal"], ["complete_name", "ilike", "WH/Stock"]],
        limit=1,
    )
    if not ids:
        ids = odoo.execute("stock.location", "search", [["usage", "=", "internal"]], limit=1)
    return int(ids[0]) if ids else None


def seed_stockout_signal() -> None:
    """Zero the on-hand stock of the top recent seller for a deterministic stockout."""
    pp_id = _top_recent_product()
    location_id = _internal_stock_location()
    if pp_id is None or location_id is None:
        print("  [stockout] No recent sales or internal location found; skipping.")
        return

    quant_ids = odoo.execute(
        "stock.quant",
        "search",
        [["product_id", "=", pp_id], ["location_id", "=", location_id]],
        limit=1,
    )
    if quant_ids:
        quant_id = int(quant_ids[0])
        odoo.execute("stock.quant", "write", [quant_id], {"inventory_quantity": 0.0})
    else:
        quant_id = int(odoo.execute("stock.quant", "create", {
            "product_id": pp_id,
            "location_id": location_id,
            "inventory_quantity": 0.0,
        }))
    odoo.execute("stock.quant", "action_apply_inventory", [quant_id])

    name_rows = odoo.search_read("product.product", [["id", "=", pp_id]], ["display_name"])
    name = name_rows[0]["display_name"] if name_rows else pp_id
    print(f"  [stockout] Zeroed on-hand stock for '{name}' (deterministic out_of_stock).")
