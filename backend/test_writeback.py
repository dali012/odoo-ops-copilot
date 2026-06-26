import unittest
from unittest.mock import call
from unittest.mock import patch

from app.writeback import WritebackError, execute_restock_rule, execute_writeback, reject_writeback


class WritebackTests(unittest.TestCase):
    @patch("app.writeback.update_writeback_status")
    @patch("app.writeback.execute_discount_rule")
    @patch("app.writeback.get_writeback_action")
    def test_execute_writeback_requires_pending_action(
        self,
        get_writeback_action,
        execute_discount_rule,
        update_writeback_status,
    ):
        get_writeback_action.return_value = {
            "id": "action-1",
            "status": "approved",
            "action_type": "discount_rule",
            "payload": {},
        }

        with self.assertRaisesRegex(WritebackError, "already approved"):
            execute_writeback("action-1")

        execute_discount_rule.assert_not_called()
        update_writeback_status.assert_not_called()

    @patch("app.writeback.update_writeback_status")
    @patch("app.writeback.try_claim_writeback_action")
    @patch("app.writeback.execute_discount_rule")
    @patch("app.writeback.get_writeback_action")
    def test_execute_discount_writeback_updates_status(
        self,
        get_writeback_action,
        execute_discount_rule,
        try_claim_writeback_action,
        update_writeback_status,
    ):
        get_writeback_action.return_value = {
            "id": "action-1",
            "status": "pending",
            "action_type": "discount_rule",
            "payload": {"products": ["Wool Coat"], "discount_percent": 15},
        }
        execute_discount_rule.return_value = {
            "odoo_model": "product.pricelist.item",
            "odoo_record_ids": [42],
        }
        try_claim_writeback_action.return_value = True
        update_writeback_status.return_value = {"id": "action-1", "status": "approved"}

        result = execute_writeback("action-1")

        self.assertEqual(result["status"], "approved")
        execute_discount_rule.assert_called_once()
        try_claim_writeback_action.assert_called_once_with("action-1", "Demo Manager")
        update_writeback_status.assert_called_once_with(
            action_id="action-1",
            status="approved",
            odoo_model="product.pricelist.item",
            odoo_record_ids=[42],
            error=None,
            decided_by="Demo Manager",
        )

    @patch("app.writeback.try_reject_writeback_action")
    @patch("app.writeback.get_writeback_action")
    def test_reject_writeback_updates_status(self, get_writeback_action, try_reject_writeback_action):
        get_writeback_action.side_effect = [
            {
                "id": "action-1",
                "status": "pending",
                "action_type": "restock_rule",
                "payload": {},
            },
            {"id": "action-1", "status": "rejected"},
        ]
        try_reject_writeback_action.return_value = True

        result = reject_writeback("action-1")

        self.assertEqual(result["status"], "rejected")
        try_reject_writeback_action.assert_called_once_with("action-1", "Demo Manager")

    @patch("app.writeback.try_reject_writeback_action")
    @patch("app.writeback.get_writeback_action")
    def test_reject_writeback_detects_concurrent_claim(self, get_writeback_action, try_reject_writeback_action):
        get_writeback_action.return_value = {
            "id": "action-1",
            "status": "pending",
            "action_type": "restock_rule",
            "payload": {},
        }
        try_reject_writeback_action.return_value = False

        with self.assertRaisesRegex(WritebackError, "already claimed"):
            reject_writeback("action-1")

    @patch("app.writeback._product_variant")
    @patch("app.writeback._warehouse_defaults")
    @patch("app.writeback.odoo")
    def test_restock_writeback_updates_existing_orderpoint(
        self,
        odoo_mock,
        warehouse_defaults,
        product_variant,
    ):
        warehouse_defaults.return_value = (10, 20, 30)
        product_variant.return_value = {
            "id": 40,
            "display_name": "Cap",
            "uom_id": [50, "Units"],
        }
        odoo_mock.execute.side_effect = [[77], True]

        result = execute_restock_rule(
            {"items": [{"product": "Cap", "min_qty": 5, "max_qty": 12, "qty_multiple": 1}]}
        )

        self.assertEqual(result["odoo_record_ids"], [77])
        self.assertEqual(result["created_ids"], [])
        self.assertEqual(result["updated_ids"], [77])
        self.assertEqual(
            odoo_mock.execute.call_args_list[0],
            call(
                "stock.warehouse.orderpoint",
                "search",
                [
                    ["product_id", "=", 40],
                    ["location_id", "=", 20],
                    ["company_id", "=", 30],
                ],
                limit=1,
            ),
        )
        self.assertEqual(odoo_mock.execute.call_args_list[1].args[:3], ("stock.warehouse.orderpoint", "write", [77]))


from app.writeback import execute_purchase_order


class TestExecutePurchaseOrder(unittest.TestCase):
    @patch("app.writeback._product_variant")
    @patch("app.writeback._first_id")
    @patch("app.writeback.odoo")
    def test_creates_po_and_confirms(self, odoo_mock, first_id_mock, product_variant_mock):
        first_id_mock.return_value = 99
        product_variant_mock.return_value = {"id": 10, "display_name": "Wool Coat", "uom_id": [5, "Units"]}
        odoo_mock.execute.side_effect = [
            1001,
            None,
        ]
        odoo_mock.search_read.return_value = [{"name": "P00001"}]

        result = execute_purchase_order({
            "supplier": "Nordic Wool Co.",
            "items": [{"product": "Wool Coat", "qty": 10, "unit_price": 81.0}],
        })

        self.assertEqual(result["odoo_model"], "purchase.order")
        self.assertEqual(result["odoo_record_ids"], [1001])
        self.assertEqual(result["po_name"], "P00001")
        confirm_call = odoo_mock.execute.call_args_list[1]
        self.assertEqual(confirm_call.args[:2], ("purchase.order", "button_confirm"))

    @patch("app.writeback._first_id")
    @patch("app.writeback.odoo")
    def test_raises_when_no_items(self, odoo_mock, first_id_mock):
        first_id_mock.return_value = 99
        with self.assertRaisesRegex(WritebackError, "no lines"):
            execute_purchase_order({"supplier": "Nordic Wool Co.", "items": []})


from app.writeback import execute_invoice_reminder


class TestExecuteInvoiceReminder(unittest.TestCase):
    @patch("app.writeback.odoo")
    def test_creates_activities_on_overdue_invoices(self, odoo_mock):
        odoo_mock.execute.side_effect = [
            [42],
            [101, 102],
            [77],
            [5],
            201,
            202,
        ]

        result = execute_invoice_reminder({
            "customer": "Aurora Retail",
            "message": "Please settle outstanding balance.",
        })

        self.assertEqual(result["odoo_model"], "mail.activity")
        self.assertEqual(result["odoo_record_ids"], [201, 202])
        self.assertEqual(result["invoices_reminded"], 2)

    @patch("app.writeback.odoo")
    def test_raises_when_no_overdue_invoices(self, odoo_mock):
        odoo_mock.execute.side_effect = [
            [42],
            [],
        ]
        with self.assertRaisesRegex(WritebackError, "No overdue invoices"):
            execute_invoice_reminder({"customer": "Aurora Retail", "message": "Pay up."})


from app.writeback import execute_price_update


class TestExecutePriceUpdate(unittest.TestCase):
    @patch("app.writeback._product_template_id")
    @patch("app.writeback.odoo")
    def test_updates_price_by_absolute_value(self, odoo_mock, tmpl_id_mock):
        tmpl_id_mock.return_value = 55
        odoo_mock.search_read.return_value = [{"list_price": 100.0}]
        odoo_mock.execute.return_value = True

        result = execute_price_update({
            "updates": [{"product": "Wool Coat", "new_price": 120.0}],
            "reason": "Margin improvement",
        })

        self.assertEqual(result["odoo_model"], "product.template")
        self.assertEqual(result["odoo_record_ids"], [55])
        self.assertEqual(result["price_changes"][0]["old_price"], 100.0)
        self.assertEqual(result["price_changes"][0]["new_price"], 120.0)
        odoo_mock.execute.assert_called_once_with(
            "product.template", "write", [55], {"list_price": 120.0}
        )

    @patch("app.writeback._product_template_id")
    @patch("app.writeback.odoo")
    def test_updates_price_by_pct_change(self, odoo_mock, tmpl_id_mock):
        tmpl_id_mock.return_value = 55
        odoo_mock.search_read.return_value = [{"list_price": 100.0}]
        odoo_mock.execute.return_value = True

        result = execute_price_update({
            "updates": [{"product": "Wool Coat", "pct_change": 10.0}],
            "reason": "Seasonal uplift",
        })

        self.assertAlmostEqual(result["price_changes"][0]["new_price"], 110.0, places=2)

    @patch("app.writeback._product_template_id")
    @patch("app.writeback.odoo")
    def test_rejects_price_outside_safety_range(self, odoo_mock, tmpl_id_mock):
        tmpl_id_mock.return_value = 55
        odoo_mock.search_read.return_value = [{"list_price": 100.0}]

        with self.assertRaisesRegex(WritebackError, "outside allowed range"):
            execute_price_update({
                "updates": [{"product": "Wool Coat", "new_price": 600.0}],
                "reason": "Test",
            })


from app.writeback import execute_pos_pricelist


class TestExecutePosPricelist(unittest.TestCase):
    @patch("app.writeback._first_id")
    @patch("app.writeback.odoo")
    def test_applies_pricelist_to_pos_config(self, odoo_mock, first_id_mock):
        first_id_mock.side_effect = [88, 33]
        odoo_mock.execute.return_value = True

        result = execute_pos_pricelist({
            "pricelist_name": "Summer Sale",
            "reason": "Summer promotion",
        })

        self.assertEqual(result["odoo_model"], "pos.config")
        self.assertEqual(result["odoo_record_ids"], [33])
        self.assertEqual(result["applied_pricelist"], "Summer Sale")
        odoo_mock.execute.assert_called_once_with(
            "pos.config", "write", [33], {"pricelist_id": 88, "use_pricelist": True}
        )

    @patch("app.writeback._first_id")
    def test_raises_when_pricelist_not_found(self, first_id_mock):
        first_id_mock.side_effect = WritebackError("Could not find pricelist 'Nonexistent'.")
        with self.assertRaises(WritebackError):
            execute_pos_pricelist({"pricelist_name": "Nonexistent", "reason": "test"})


from app.writeback import execute_email_campaign


class TestExecuteEmailCampaign(unittest.TestCase):
    @patch("app.writeback.odoo")
    def test_creates_draft_mailing(self, odoo_mock):
        odoo_mock.execute.side_effect = [
            [7],
            [50, 51, 52],
            999,
        ]

        result = execute_email_campaign({
            "subject": "Summer Sale!",
            "body_html": "<p>Big discounts this summer.</p>",
            "segment": "all_customers",
            "reason": "Drive summer revenue",
        })

        self.assertEqual(result["odoo_model"], "mailing.mailing")
        self.assertEqual(result["odoo_record_ids"], [999])
        self.assertEqual(result["recipient_count"], 3)

        create_call = odoo_mock.execute.call_args_list[2]
        self.assertEqual(create_call.args[0], "mailing.mailing")
        self.assertEqual(create_call.args[1], "create")
        vals = create_call.args[2]
        self.assertEqual(vals["state"], "draft")
        self.assertEqual(vals["subject"], "Summer Sale!")

    @patch("app.writeback.odoo")
    def test_raises_when_model_not_found(self, odoo_mock):
        odoo_mock.execute.side_effect = [[]]
        with self.assertRaisesRegex(WritebackError, "ir.model"):
            execute_email_campaign({
                "subject": "Hi",
                "body_html": "<p>x</p>",
                "segment": "all_customers",
                "reason": "test",
            })


from app.writeback import execute_transfer_stock


class TestExecuteTransferStock(unittest.TestCase):
    @patch("app.writeback._product_variant")
    @patch("app.writeback._first_id")
    @patch("app.writeback.odoo")
    def test_creates_internal_picking(self, odoo_mock, first_id_mock, product_variant_mock):
        first_id_mock.side_effect = [
            11,
            22,
            33,
        ]
        product_variant_mock.return_value = {
            "id": 5,
            "display_name": "Wool Coat",
            "uom_id": [1, "Units"],
        }
        odoo_mock.execute.side_effect = [
            777,
            None,
        ]
        odoo_mock.search_read.return_value = [{"name": "INT/00001"}]

        result = execute_transfer_stock({
            "product": "Wool Coat",
            "qty": 10,
            "from_location": "WH/Stock",
            "to_location": "WH/Output",
            "reason": "Replenish output",
        })

        self.assertEqual(result["odoo_model"], "stock.picking")
        self.assertEqual(result["odoo_record_ids"], [777])
        self.assertEqual(result["picking_name"], "INT/00001")

        create_call = odoo_mock.execute.call_args_list[0]
        vals = create_call.args[2]
        self.assertEqual(vals["picking_type_id"], 33)
        self.assertEqual(vals["location_id"], 11)
        self.assertEqual(vals["location_dest_id"], 22)

    @patch("app.writeback.odoo")
    def test_raises_on_zero_qty(self, odoo_mock):
        with self.assertRaisesRegex(WritebackError, "positive"):
            execute_transfer_stock({
                "product": "Wool Coat",
                "qty": 0,
                "from_location": "WH/Stock",
                "to_location": "WH/Output",
                "reason": "test",
            })


if __name__ == "__main__":
    unittest.main()
