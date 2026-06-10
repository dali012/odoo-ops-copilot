# backend/app/seed/purchase.py
"""Seed supplier partners, purchase orders, and receipts."""
from __future__ import annotations

import random
from datetime import date
from typing import Any

from ._base import SEED_PREFIX, add_months, get_or_create
from ..odoo_client import odoo

SUPPLIERS = [
    {"name": "Nordic Wool Co.",         "categories": ["Outerwear", "Knitwear"], "country_code": "NO"},
    {"name": "Pacific Footwear Ltd.",   "categories": ["Footwear"],              "country_code": "VN"},
    {"name": "Global Accessories Inc.", "categories": ["Accessories"],           "country_code": "CN"},
]

PURCHASE_MONTHS = 12


def _do_incoming_receipt(picking_id: int) -> None:
    """Set done qty = demand on every move line then validate the receipt.

    In Odoo 18, stock.move.line.quantity is the done quantity (renamed from
    qty_done in Odoo 16). We create move lines when Odoo did not auto-create
    them. button_validate may return a wizard dict on some builds; we attempt
    to process it gracefully.
    """
    moves = odoo.search_read(
        "stock.move",
        domain=[["picking_id", "=", picking_id], ["state", "not in", ["done", "cancel"]]],
        fields=["id", "product_uom_qty", "product_id", "location_id", "location_dest_id"],
    )
    for move in moves:
        existing_mls = odoo.execute(
            "stock.move.line", "search", [["move_id", "=", move["id"]]]
        )
        if existing_mls:
            odoo.execute(
                "stock.move.line", "write", existing_mls, {"quantity": move["product_uom_qty"]}
            )
        else:
            odoo.execute("stock.move.line", "create", {
                "move_id": move["id"],
                "picking_id": picking_id,
                "product_id": move["product_id"][0],
                "quantity": move["product_uom_qty"],
                "location_id": move["location_id"][0],
                "location_dest_id": move["location_dest_id"][0],
            })

    result = odoo.execute("stock.picking", "button_validate", [picking_id])
    if isinstance(result, dict) and result.get("res_model"):
        wizard_model = result["res_model"]
        try:
            wizard_id = odoo.execute(
                wizard_model, "create", {"pick_ids": [[6, 0, [picking_id]]]}
            )
            if isinstance(wizard_id, (list, tuple)):
                wizard_id = wizard_id[0]
            odoo.execute(wizard_model, "process_cancel_backorder", [wizard_id])
        except Exception:
            pass


def seed_purchase(product_ids: dict[str, list[int]]) -> tuple[int, int]:
    """Create suppliers, 12 months of confirmed POs, and validated receipts.

    Args:
        product_ids: {category_name: [product.product id, ...]} from seed_catalog().

    Returns:
        (created_count, skipped_count)
    """
    # Resolve country IDs (best-effort; missing country just skips the field)
    country_map: dict[str, int] = {}
    for code in ["NO", "VN", "CN"]:
        ids = odoo.execute("res.country", "search", [["code", "=", code]], limit=1)
        if ids:
            country_map[code] = int(ids[0])

    # Ensure supplier contacts exist
    supplier_ids: dict[str, int] = {}
    for sup in SUPPLIERS:
        vals: dict[str, Any] = {
            "name": sup["name"],
            "supplier_rank": 1,
            "company_type": "company",
        }
        if sup["country_code"] in country_map:
            vals["country_id"] = country_map[sup["country_code"]]
        supplier_ids[sup["name"]] = get_or_create(
            "res.partner",
            [["name", "=", sup["name"]], ["supplier_rank", ">", 0]],
            vals,
        )

    # Cache purchase price: 45% of list_price
    pp_price_cache: dict[int, float] = {}

    def _purchase_price(pp_id: int) -> float:
        if pp_id in pp_price_cache:
            return pp_price_cache[pp_id]
        row = odoo.search_read("product.product", [["id", "=", pp_id]], ["product_tmpl_id"])
        if row:
            t = odoo.search_read(
                "product.template", [["id", "=", row[0]["product_tmpl_id"][0]]], ["list_price"]
            )
            price = round(float(t[0]["list_price"]) * 0.45, 2) if t else 50.0
        else:
            price = 50.0
        pp_price_cache[pp_id] = price
        return price

    today = date.today().replace(day=1)
    end_month = add_months(today, -1)
    start_month = add_months(end_month, -(PURCHASE_MONTHS - 1))

    created_count = 0
    skipped_count = 0
    month = start_month

    while month <= end_month:
        for sup in SUPPLIERS:
            ref = (
                f"{SEED_PREFIX}:po:"
                f"{sup['name'].lower().replace(' ', '-').replace('.', '')}:"
                f"{month:%Y-%m}"
            )
            existing = odoo.execute(
                "purchase.order", "search", [["partner_ref", "=", ref]], limit=1
            )
            if existing:
                skipped_count += 1
                continue

            lines = [
                (0, 0, {
                    "product_id": pp_id,
                    "product_qty": random.randint(20, 50),
                    "price_unit": _purchase_price(pp_id),
                })
                for cat_name in sup["categories"]
                for pp_id in product_ids.get(cat_name, [])
            ]
            if not lines:
                continue

            po_id = int(odoo.execute("purchase.order", "create", {
                "partner_id": supplier_ids[sup["name"]],
                "partner_ref": ref,
                "date_order": f"{month:%Y-%m-10}",
                "order_line": lines,
            }))
            odoo.execute("purchase.order", "button_confirm", [po_id])

            picking_ids = odoo.execute(
                "stock.picking", "search", [["purchase_id", "=", po_id]]
            )
            for pid in picking_ids:
                _do_incoming_receipt(pid)

            created_count += 1

        month = add_months(month, 1)

    print(f"  [purchase] Created {created_count} POs, skipped {skipped_count} existing.")
    return created_count, skipped_count
