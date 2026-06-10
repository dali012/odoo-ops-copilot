# backend/app/seed/pos.py
"""Seed POS config, historical sessions, and orders."""
from __future__ import annotations

import random
from datetime import date, timedelta

from ._base import SEED_PREFIX, add_months, get_or_create
from ..odoo_client import odoo

POS_CONFIG_NAME = "Main Store"
POS_MONTHS = 12
SESSIONS_PER_MONTH = 3
ORDERS_PER_SESSION_MIN = 8
ORDERS_PER_SESSION_MAX = 15


def _pos_payment_methods() -> tuple[int | None, int | None]:
    bank_ids = odoo.execute("pos.payment.method", "search", [["is_cash_count", "=", False]], limit=1)
    cash_ids = odoo.execute("pos.payment.method", "search", [["is_cash_count", "=", True]], limit=1)
    return (
        int(bank_ids[0]) if bank_ids else None,
        int(cash_ids[0]) if cash_ids else None,
    )


def seed_pos(product_ids: dict[str, list[int]], customer_ids: list[int]) -> tuple[int, int]:
    """Create POS config + 12 months x 3 sessions with 8-15 orders each.

    Args:
        product_ids:  {category_name: [product.product id, ...]} from seed_catalog().
        customer_ids: [res.partner id, ...] from seed_catalog().

    Returns:
        (created_session_count, skipped_session_count)
    """
    all_pp_ids = [pp_id for pp_ids in product_ids.values() for pp_id in pp_ids]
    if not all_pp_ids:
        print("  [pos] No products found; skipping POS seeding.")
        return 0, 0

    # Cache list prices for POS order line amounts
    pp_price_map: dict[int, float] = {}
    for pp_id in all_pp_ids:
        row = odoo.search_read("product.product", [["id", "=", pp_id]], ["product_tmpl_id"])
        if row:
            t = odoo.search_read(
                "product.template", [["id", "=", row[0]["product_tmpl_id"][0]]], ["list_price"]
            )
            pp_price_map[pp_id] = float(t[0]["list_price"]) if t else 50.0
        else:
            pp_price_map[pp_id] = 50.0

    config_id = get_or_create("pos.config", [["name", "=", POS_CONFIG_NAME]], {"name": POS_CONFIG_NAME})
    bank_method_id, cash_method_id = _pos_payment_methods()

    if bank_method_id is None and cash_method_id is None:
        print("  [pos] No POS payment methods found; skipping POS seeding.")
        return 0, 0

    today = date.today().replace(day=1)
    end_month = add_months(today, -1)
    start_month = add_months(end_month, -(POS_MONTHS - 1))

    created_count = 0
    skipped_count = 0
    month = start_month

    while month <= end_month:
        for session_idx in range(1, SESSIONS_PER_MONTH + 1):
            session_name = f"{SEED_PREFIX}:pos:{month:%Y-%m}:{session_idx}"
            existing = odoo.execute(
                "pos.session", "search", [["name", "=", session_name]], limit=1
            )
            if existing:
                skipped_count += 1
                continue

            session_day = month + timedelta(days=random.randint(0, 25))
            day_str = session_day.strftime("%Y-%m-%d")

            session_id = int(odoo.execute("pos.session", "create", {
                "config_id": config_id,
            }))
            # Odoo's sequence generator overwrites name during create; write it
            # afterwards so the idempotency search can find it on re-runs.
            odoo.execute("pos.session", "write", [session_id], {"name": session_name})

            num_orders = random.randint(ORDERS_PER_SESSION_MIN, ORDERS_PER_SESSION_MAX)
            for _ in range(num_orders):
                pp_id = random.choice(all_pp_ids)
                qty = random.randint(1, 3)
                unit_price = pp_price_map[pp_id]
                amount = round(qty * unit_price, 2)
                use_bank = random.random() < 0.70
                method_id = (bank_method_id if use_bank else cash_method_id) or bank_method_id or cash_method_id

                order_id = int(odoo.execute("pos.order", "create", {
                    "session_id": session_id,
                    "partner_id": random.choice(customer_ids),
                    "amount_total": amount,
                    "amount_tax": 0.0,
                    "amount_paid": amount,
                    "amount_return": 0.0,
                    "lines": [(0, 0, {
                        "product_id": pp_id,
                        "qty": qty,
                        "price_unit": unit_price,
                        "price_subtotal": amount,
                        "price_subtotal_incl": amount,
                    })],
                }))
                odoo.execute("pos.payment", "create", {
                    "pos_order_id": order_id,
                    "amount": amount,
                    "payment_method_id": method_id,
                })
                try:
                    odoo.execute("pos.order", "action_pos_order_paid", [order_id])
                except Exception:
                    pass  # order may already transition on payment create

            # Force-close session as historical record (Odoo allows admin write on state)
            try:
                odoo.execute("pos.session", "write", [session_id], {
                    "state": "closed",
                    "start_at": f"{day_str} 09:00:00",
                    "stop_at": f"{day_str} 18:00:00",
                })
            except Exception:
                try:
                    odoo.execute("pos.session", "action_pos_session_close", [session_id])
                except Exception:
                    pass  # session left open is acceptable; data still useful for analytics

            created_count += 1

        month = add_months(month, 1)

    print(f"  [pos] Created {created_count} sessions, skipped {skipped_count} existing.")
    return created_count, skipped_count
