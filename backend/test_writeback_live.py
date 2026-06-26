"""Live writeback integration tests against a seeded Odoo 18 instance.

Mocked unit tests can't catch Odoo 17->18 API breakage because they assert on the
arguments passed to a fake ``odoo.execute`` — the code can be wrong about Odoo's
real API and still pass. These tests execute every writeback against a live Odoo
18 stack.

Contract: each writeback must EITHER succeed OR raise a business ``WritebackError``
— never a low-level Odoo XML-RPC fault (which is what the removed ``type='product'``
value, the ``action_apply_inventory`` None return, a renamed ``use_pricelist``
field, etc. would produce).

These mutate Odoo, so they are meant for the ephemeral CI stack (run after the
golden eval). Gated behind RUN_LIVE_TESTS=1 so the offline suite skips them.
"""
import os
import unittest

from app.odoo_client import odoo
from app.writeback import (
    WritebackError,
    _ensure_discount_pricelist,
    execute_discount_rule,
    execute_email_campaign,
    execute_inventory_adjustment,
    execute_invoice_reminder,
    execute_pos_pricelist,
    execute_price_update,
    execute_purchase_order,
    execute_restock_rule,
    execute_sale_order_cancel,
    execute_transfer_stock,
    execute_vendor_price_update,
)

RUN_LIVE = os.getenv("RUN_LIVE_TESTS") == "1"

PRODUCT = "Wool Coat"
SUPPLIER = "Nordic Wool Co."


@unittest.skipUnless(RUN_LIVE, "requires a seeded Odoo 18 stack; set RUN_LIVE_TESTS=1")
class WritebackLiveTests(unittest.TestCase):
    def _must_not_crash(self, fn, payload):
        """Run a writeback that may legitimately have no data to act on.

        A business WritebackError is acceptable; any other exception (e.g. an
        xmlrpc Fault from an Odoo 18 API mismatch) propagates and fails the test.
        """
        try:
            fn(payload)
        except WritebackError:
            pass

    # --- known Odoo 18 bug: stock.quant.action_apply_inventory returns None ---
    def test_inventory_adjustment_applies(self):
        result = execute_inventory_adjustment({"product": PRODUCT, "qty": 5})
        self.assertEqual(result["odoo_model"], "stock.quant")
        self.assertEqual(result["adjusted_qty"], 5.0)

    # --- suspected Odoo 18 issue: pos.config.use_pricelist field --------------
    def test_pos_pricelist_applies(self):
        _ensure_discount_pricelist()  # guarantee the pricelist exists
        result = execute_pos_pricelist({"pricelist_name": "Copilot Approved Discounts"})
        self.assertEqual(result["odoo_model"], "pos.config")

    def test_discount_rule_applies(self):
        result = execute_discount_rule({"products": [PRODUCT], "discount_percent": 10})
        self.assertEqual(result["odoo_model"], "product.pricelist.item")
        self.assertTrue(result["odoo_record_ids"])

    def test_restock_rule_applies(self):
        result = execute_restock_rule(
            {"items": [{"product": PRODUCT, "min_qty": 5, "max_qty": 20}]}
        )
        self.assertEqual(result["odoo_model"], "stock.warehouse.orderpoint")

    def test_price_update_applies(self):
        result = execute_price_update({"updates": [{"product": PRODUCT, "pct_change": 5}]})
        self.assertEqual(result["odoo_model"], "product.template")

    def test_purchase_order_applies(self):
        result = execute_purchase_order({
            "supplier": SUPPLIER,
            "items": [{"product": PRODUCT, "qty": 10, "unit_price": 50.0}],
        })
        self.assertEqual(result["odoo_model"], "purchase.order")
        self.assertTrue(result["po_name"])

    def test_vendor_price_update_applies(self):
        result = execute_vendor_price_update({
            "updates": [
                {"product": PRODUCT, "supplier": SUPPLIER, "new_price": 40.0, "lead_time_days": 7}
            ],
        })
        self.assertEqual(result["odoo_model"], "product.supplierinfo")

    def test_email_campaign_applies(self):
        result = execute_email_campaign({
            "subject": "Live test campaign",
            "body_html": "<p>hello</p>",
        })
        self.assertEqual(result["odoo_model"], "mailing.mailing")

    def test_sale_order_cancel_applies(self):
        # Create a fresh draft order so the cancellation is deterministic.
        partner_ids = odoo.execute("res.partner", "search", [["customer_rank", ">", 0]], limit=1)
        self.assertTrue(partner_ids, "seed should have customers")
        pp = odoo.search_read("product.product", [["name", "ilike", PRODUCT]], ["id"], limit=1)
        self.assertTrue(pp, "seed should have the product")
        so_id = int(odoo.execute("sale.order", "create", {
            "partner_id": int(partner_ids[0]),
            "order_line": [(0, 0, {"product_id": int(pp[0]["id"]), "product_uom_qty": 1})],
        }))
        name = odoo.search_read("sale.order", [["id", "=", so_id]], ["name"])[0]["name"]

        result = execute_sale_order_cancel({"order_names": [name]})
        self.assertEqual(result["cancelled_count"], 1)

    # --- data-dependent writebacks: must not crash on the Odoo 18 API ---------
    def test_invoice_reminder_does_not_crash(self):
        partner = odoo.search_read("res.partner", [["customer_rank", ">", 0]], ["name"], limit=1)
        customer = partner[0]["name"] if partner else "Nobody"
        self._must_not_crash(execute_invoice_reminder, {"customer": customer, "message": "Reminder"})

    def test_transfer_stock_does_not_crash(self):
        self._must_not_crash(execute_transfer_stock, {
            "product": PRODUCT,
            "qty": 1,
            "from_location": "WH/Stock",
            "to_location": "WH/Output",
        })


if __name__ == "__main__":
    unittest.main()
