# backend/app/seed/invoicing.py
"""Seed customer invoices from existing sale orders."""
from __future__ import annotations

import random
import xmlrpc.client
from datetime import datetime, timedelta

from ._base import SEED_PREFIX
from ..odoo_client import odoo

PAID_FRACTION = 0.80
BANK_FRACTION = 0.70  # fraction of paid invoices using the bank journal


def _get_journals() -> tuple[int, int]:
    bank_ids = odoo.execute("account.journal", "search", [["type", "=", "bank"]], limit=1)
    cash_ids = odoo.execute("account.journal", "search", [["type", "=", "cash"]], limit=1)
    if not bank_ids:
        raise RuntimeError("No bank journal found - check Odoo chart of accounts.")
    if not cash_ids:
        raise RuntimeError("No cash journal found - check Odoo chart of accounts.")
    return int(bank_ids[0]), int(cash_ids[0])


def _receivable_account_ids() -> list[int]:
    ids = odoo.execute("account.account", "search", [
        ["account_type", "=", "asset_receivable"],
        ["deprecated", "=", False],
    ])
    return [int(i) for i in ids]


def _register_payment_and_reconcile(
    move_id: int,
    partner_id: int,
    amount: float,
    date_str: str,
    journal_id: int,
    receivable_ids: list[int],
) -> None:
    payment_id = int(odoo.execute("account.payment", "create", {
        "payment_type": "inbound",
        "partner_type": "customer",
        "partner_id": partner_id,
        "amount": amount,
        "journal_id": journal_id,
        "date": date_str,
    }))
    try:
        odoo.execute("account.payment", "action_post", [payment_id])
    except xmlrpc.client.Fault as fault:
        # Odoo 18: action_post returns None, which Odoo's own marshaller can't
        # serialize (allow_none=False). The payment was already posted; ignore.
        if "cannot marshal None" not in fault.faultString:
            raise

    inv_lines = odoo.search_read("account.move.line", [
        ["move_id", "=", move_id],
        ["account_id", "in", receivable_ids],
    ], ["id"])

    pay_data = odoo.search_read("account.payment", [["id", "=", payment_id]], ["move_id"])[0]
    pay_lines = odoo.search_read("account.move.line", [
        ["move_id", "=", pay_data["move_id"][0]],
        ["account_id", "in", receivable_ids],
    ], ["id"])

    all_ids = [l["id"] for l in inv_lines + pay_lines]
    if all_ids:
        try:
            odoo.execute("account.move.line", "reconcile", all_ids)
        except Exception:
            pass  # Some Odoo builds expose reconcile under a different API path


def seed_invoicing() -> tuple[int, int]:
    """Create one invoice per seeded sale order (80% paid, 20% overdue).

    Returns:
        (created_count, skipped_count)
    """
    bank_journal_id, cash_journal_id = _get_journals()
    receivable_ids = _receivable_account_ids()

    sale_orders = odoo.search_read(
        "sale.order",
        domain=[["client_order_ref", "like", f"{SEED_PREFIX}:"]],
        fields=["id", "partner_id", "date_order", "client_order_ref"],
        limit=0,
    )

    created_count = 0
    skipped_count = 0

    for so in sale_orders:
        # Derive unique invoice ref from the sale order ref
        so_ref_suffix = so["client_order_ref"][len(SEED_PREFIX) + 1:]
        ref = f"{SEED_PREFIX}:inv:{so_ref_suffix}"

        existing = odoo.execute("account.move", "search", [["ref", "=", ref]], limit=1)
        if existing:
            skipped_count += 1
            continue

        lines = odoo.search_read(
            "sale.order.line",
            [["order_id", "=", so["id"]]],
            ["product_id", "product_uom_qty", "price_unit"],
        )
        invoice_lines = [
            (0, 0, {
                "product_id": line["product_id"][0],
                "quantity": line["product_uom_qty"],
                "price_unit": line["price_unit"],
            })
            for line in lines
            if line.get("product_id")
        ]
        if not invoice_lines:
            continue

        date_str = so["date_order"][:10]
        due_date = (
            datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=30)
        ).strftime("%Y-%m-%d")
        partner_id = int(so["partner_id"][0])

        move_id = int(odoo.execute("account.move", "create", {
            "move_type": "out_invoice",
            "partner_id": partner_id,
            "invoice_date": date_str,
            "invoice_date_due": due_date,
            "ref": ref,
            "invoice_line_ids": invoice_lines,
        }))

        try:
            odoo.execute("account.move", "action_post", [move_id])
        except xmlrpc.client.Fault as fault:
            if "cannot marshal None" not in fault.faultString:
                raise

        if random.random() < PAID_FRACTION:
            move_data = odoo.search_read("account.move", [["id", "=", move_id]], ["amount_total"])[0]
            amount = float(move_data["amount_total"])
            journal_id = bank_journal_id if random.random() < BANK_FRACTION else cash_journal_id
            _register_payment_and_reconcile(
                move_id, partner_id, amount, date_str, journal_id, receivable_ids
            )

        created_count += 1

    print(
        f"  [invoicing] Created {created_count} invoices "
        f"({int(PAID_FRACTION * 100)}% paid), skipped {skipped_count} existing."
    )
    return created_count, skipped_count
