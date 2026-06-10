"""Human-approved write-back actions for Odoo."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .config import config
from .odoo_client import odoo
from .session_store import (
    get_writeback_action,
    try_claim_writeback_action,
    try_reject_writeback_action,
    update_writeback_status,
)


class WritebackError(ValueError):
    pass


def _get_pending_action(action_id: str) -> dict[str, Any]:
    action = get_writeback_action(action_id)
    if action is None:
        raise WritebackError("Write-back action not found.")
    if action["status"] != "pending":
        raise WritebackError(f"Write-back action is already {action['status']}.")
    return action


def _first_id(model: str, domain: list, *, label: str) -> int:
    ids = odoo.execute(model, "search", domain, limit=1)
    if not ids:
        raise WritebackError(f"Could not find {label}.")
    return int(ids[0])


def _company_id() -> int:
    return _first_id("res.company", [], label="company")


def _company_currency_id(company_id: int) -> int:
    rows = odoo.search_read("res.company", domain=[["id", "=", company_id]], fields=["currency_id"], limit=1)
    if not rows or not rows[0].get("currency_id"):
        raise WritebackError("Could not determine company currency.")
    return int(rows[0]["currency_id"][0])


def _ensure_discount_pricelist() -> int:
    existing = odoo.execute("product.pricelist", "search", [["name", "=", "Copilot Approved Discounts"]], limit=1)
    if existing:
        return int(existing[0])

    company_id = _company_id()
    currency_id = _company_currency_id(company_id)
    return int(
        odoo.execute(
            "product.pricelist",
            "create",
            {
                "name": "Copilot Approved Discounts",
                "currency_id": currency_id,
                "company_id": company_id,
                "active": True,
            },
        )
    )


def _product_template_id(product_name: str) -> int:
    return _first_id("product.template", [["name", "ilike", product_name]], label=f"product template '{product_name}'")


def _product_variant(product_name: str) -> dict[str, Any]:
    rows = odoo.search_read(
        "product.product",
        domain=[["display_name", "ilike", product_name]],
        fields=["id", "display_name", "uom_id"],
        limit=1,
    )
    if not rows:
        raise WritebackError(f"Could not find product variant '{product_name}'.")
    return rows[0]


def _warehouse_defaults() -> tuple[int, int, int]:
    rows = odoo.search_read(
        "stock.warehouse",
        domain=[],
        fields=["id", "lot_stock_id", "company_id"],
        limit=1,
    )
    if not rows:
        raise WritebackError("Could not find a stock warehouse.")

    warehouse = rows[0]
    warehouse_id = int(warehouse["id"])
    location_id = int(warehouse["lot_stock_id"][0])
    company_id = int(warehouse["company_id"][0]) if warehouse.get("company_id") else _company_id()
    return warehouse_id, location_id, company_id


def _existing_orderpoint_id(product_id: int, location_id: int, company_id: int) -> int | None:
    ids = odoo.execute(
        "stock.warehouse.orderpoint",
        "search",
        [
            ["product_id", "=", product_id],
            ["location_id", "=", location_id],
            ["company_id", "=", company_id],
        ],
        limit=1,
    )
    return int(ids[0]) if ids else None


def execute_discount_rule(payload: dict[str, Any]) -> dict[str, Any]:
    products = payload.get("products") or []
    discount_percent = float(payload.get("discount_percent") or 0)
    min_quantity = float(payload.get("min_quantity") or 1)

    if not products:
        raise WritebackError("Discount proposal has no products.")
    if discount_percent <= 0 or discount_percent > 80:
        raise WritebackError("Discount percent must be between 0 and 80.")

    pricelist_id = _ensure_discount_pricelist()
    record_ids: list[int] = []
    for product_name in products:
        tmpl_id = _product_template_id(str(product_name))
        item_id = odoo.execute(
            "product.pricelist.item",
            "create",
            {
                "name": f"Copilot {discount_percent:g}% discount",
                "pricelist_id": pricelist_id,
                "applied_on": "1_product",
                "product_tmpl_id": tmpl_id,
                "compute_price": "percentage",
                "percent_price": discount_percent,
                "min_quantity": min_quantity,
            },
        )
        record_ids.append(int(item_id))

    return {"odoo_model": "product.pricelist.item", "odoo_record_ids": record_ids}


def execute_restock_rule(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items") or []
    if not items:
        raise WritebackError("Restock proposal has no items.")

    warehouse_id, location_id, company_id = _warehouse_defaults()
    record_ids: list[int] = []
    created_ids: list[int] = []
    updated_ids: list[int] = []
    for item in items:
        product_name = str(item.get("product") or "")
        min_qty = float(item.get("min_qty") or 0)
        max_qty = float(item.get("max_qty") or 0)
        if not product_name:
            raise WritebackError("Restock item is missing a product name.")
        if min_qty < 0 or max_qty <= 0 or max_qty < min_qty:
            raise WritebackError(f"Invalid restock quantities for {product_name}.")

        product = _product_variant(product_name)
        values = {
            "name": f"Copilot reorder {product['display_name']}",
            "product_id": int(product["id"]),
            "product_min_qty": min_qty,
            "product_max_qty": max_qty,
            "qty_multiple": float(item.get("qty_multiple") or 1),
            "location_id": location_id,
            "warehouse_id": warehouse_id,
            "company_id": company_id,
            "trigger": "manual",
        }
        if product.get("uom_id"):
            values["product_uom"] = int(product["uom_id"][0])

        existing_id = _existing_orderpoint_id(int(product["id"]), location_id, company_id)
        if existing_id is not None:
            odoo.execute("stock.warehouse.orderpoint", "write", [existing_id], values)
            record_ids.append(existing_id)
            updated_ids.append(existing_id)
        else:
            record_id = int(odoo.execute("stock.warehouse.orderpoint", "create", values))
            record_ids.append(record_id)
            created_ids.append(record_id)

    return {
        "odoo_model": "stock.warehouse.orderpoint",
        "odoo_record_ids": record_ids,
        "created_ids": created_ids,
        "updated_ids": updated_ids,
    }


def execute_purchase_order(payload: dict[str, Any]) -> dict[str, Any]:
    supplier_name = str(payload.get("supplier") or "")
    items = payload.get("items") or []

    if not supplier_name:
        raise WritebackError("Purchase order proposal is missing a supplier.")
    if not items:
        raise WritebackError("Purchase order proposal has no lines.")

    supplier_id = _first_id(
        "res.partner",
        [["name", "ilike", supplier_name], ["supplier_rank", ">", 0]],
        label=f"supplier '{supplier_name}'",
    )

    order_lines = []
    for item in items:
        pp = _product_variant(str(item.get("product") or ""))
        order_lines.append((0, 0, {
            "product_id": int(pp["id"]),
            "product_qty": float(item.get("qty") or 0),
            "price_unit": float(item.get("unit_price") or 0),
        }))

    po_id = int(odoo.execute("purchase.order", "create", {
        "partner_id": supplier_id,
        "order_line": order_lines,
    }))
    odoo.execute("purchase.order", "button_confirm", [po_id])

    po_data = odoo.search_read("purchase.order", [["id", "=", po_id]], ["name"])[0]
    return {
        "odoo_model": "purchase.order",
        "odoo_record_ids": [po_id],
        "po_name": po_data["name"],
    }


def execute_invoice_reminder(payload: dict[str, Any]) -> dict[str, Any]:
    customer_name = str(payload.get("customer") or "")
    message = str(payload.get("message") or "")
    proposed_invoice_ids = [int(item) for item in payload.get("invoice_ids") or []]

    if not customer_name:
        raise WritebackError("Invoice reminder proposal is missing a customer name.")

    partner_ids = odoo.execute("res.partner", "search", [["name", "ilike", customer_name]], limit=1)
    if not partner_ids:
        raise WritebackError(f"Customer '{customer_name}' not found in Odoo.")
    partner_id = int(partner_ids[0])

    today_str = date.today().strftime("%Y-%m-%d")
    invoice_domain = [
        ["partner_id", "=", partner_id],
        ["move_type", "=", "out_invoice"],
        ["state", "=", "posted"],
        ["payment_state", "in", ["not_paid", "partial"]],
        ["invoice_date_due", "<", today_str],
    ]
    if proposed_invoice_ids:
        invoice_domain.append(["id", "in", proposed_invoice_ids])
    invoice_ids = odoo.execute("account.move", "search", invoice_domain)
    if not invoice_ids:
        raise WritebackError(f"No overdue invoices found for '{customer_name}'.")

    act_type_ids = odoo.execute("mail.activity.type", "search", [["name", "=", "To Do"]], limit=1)
    if not act_type_ids:
        raise WritebackError("Activity type 'To Do' not found in Odoo.")
    act_type_id = int(act_type_ids[0])

    model_ids = odoo.execute("ir.model", "search", [["model", "=", "account.move"]], limit=1)
    if not model_ids:
        raise WritebackError("ir.model for account.move not found.")
    model_id = int(model_ids[0])

    deadline_str = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
    activity_ids: list[int] = []
    for inv_id in invoice_ids:
        act_id = int(odoo.execute("mail.activity", "create", {
            "res_model_id": model_id,
            "res_id": inv_id,
            "activity_type_id": act_type_id,
            "summary": "Payment reminder",
            "note": message,
            "date_deadline": deadline_str,
        }))
        activity_ids.append(act_id)

    return {
        "odoo_model": "mail.activity",
        "odoo_record_ids": activity_ids,
        "invoices_reminded": len(invoice_ids),
    }


def execute_price_update(payload: dict[str, Any]) -> dict[str, Any]:
    updates = payload.get("updates") or []
    if not updates:
        raise WritebackError("Price update proposal has no items.")

    record_ids: list[int] = []
    price_changes: list[dict[str, Any]] = []

    for update in updates:
        product_name = str(update.get("product") or "")
        tmpl_id = _product_template_id(product_name)

        tmpl_data = odoo.search_read(
            "product.template", [["id", "=", tmpl_id]], ["list_price"]
        )[0]
        current_price = float(tmpl_data["list_price"])

        if update.get("new_price") is not None:
            new_price = round(float(update["new_price"]), 2)
        elif update.get("pct_change") is not None:
            pct = float(update["pct_change"])
            if pct < -80 or pct > 200:
                raise WritebackError(
                    f"pct_change {pct} for '{product_name}' is out of range (-80 to +200)."
                )
            new_price = round(current_price * (1 + pct / 100), 2)
        else:
            raise WritebackError(
                f"Item for '{product_name}' must have either new_price or pct_change."
            )

        if new_price <= 0:
            raise WritebackError(f"New price {new_price} for '{product_name}' must be positive.")
        if new_price < current_price * 0.01 or new_price > current_price * 5:
            raise WritebackError(
                f"New price {new_price} for '{product_name}' is outside allowed range "
                f"(1%-500% of current price {current_price})."
            )

        odoo.execute("product.template", "write", [tmpl_id], {"list_price": new_price})
        record_ids.append(tmpl_id)
        price_changes.append({
            "product":   product_name,
            "old_price": current_price,
            "new_price": new_price,
        })

    return {
        "odoo_model": "product.template",
        "odoo_record_ids": record_ids,
        "price_changes": price_changes,
    }


def execute_pos_pricelist(payload: dict[str, Any]) -> dict[str, Any]:
    pricelist_name = str(payload.get("pricelist_name") or "")
    if not pricelist_name:
        raise WritebackError("POS pricelist proposal is missing a pricelist name.")

    pricelist_id = _first_id(
        "product.pricelist",
        [["name", "=", pricelist_name]],
        label=f"pricelist '{pricelist_name}'",
    )
    config_id = _first_id(
        "pos.config",
        [["name", "=", "Main Store"]],
        label="POS config 'Main Store'",
    )

    odoo.execute("pos.config", "write", [config_id], {
        "pricelist_id": pricelist_id,
        "use_pricelist": True,
    })

    return {
        "odoo_model": "pos.config",
        "odoo_record_ids": [config_id],
        "applied_pricelist": pricelist_name,
    }


def execute_email_campaign(payload: dict[str, Any]) -> dict[str, Any]:
    subject = str(payload.get("subject") or "")
    body_html = str(payload.get("body_html") or "")
    segment = str(payload.get("segment") or "all_customers")

    if not subject:
        raise WritebackError("Email campaign proposal is missing a subject.")

    model_ids = odoo.execute("ir.model", "search", [["model", "=", "res.partner"]], limit=1)
    if not model_ids:
        raise WritebackError("ir.model for res.partner not found in Odoo.")
    model_id = int(model_ids[0])

    mailing_domain = str(payload.get("mailing_domain") or [["customer_rank", ">", 0]])
    recipient_count = int(payload.get("recipient_count") or 0)
    if recipient_count <= 0:
        recipient_ids = odoo.execute("res.partner", "search", [["customer_rank", ">", 0]])
        recipient_count = len(recipient_ids)

    mailing_id = int(odoo.execute("mailing.mailing", "create", {
        "subject":          subject,
        "body_html":        body_html,
        "mailing_model_id": model_id,
        "mailing_domain":   mailing_domain,
        "state":            "draft",
    }))

    return {
        "odoo_model":      "mailing.mailing",
        "odoo_record_ids": [mailing_id],
        "recipient_count": recipient_count,
    }


def execute_transfer_stock(payload: dict[str, Any]) -> dict[str, Any]:
    product_name  = str(payload.get("product") or "")
    qty           = float(payload.get("qty") or 0)
    from_loc_name = str(payload.get("from_location") or "")
    to_loc_name   = str(payload.get("to_location") or "")

    if qty <= 0:
        raise WritebackError("Transfer quantity must be positive.")
    if not product_name:
        raise WritebackError("Transfer proposal is missing a product name.")

    pp = _product_variant(product_name)
    pp_id  = int(pp["id"])
    uom_id = int(pp["uom_id"][0]) if pp.get("uom_id") else None

    from_loc_id = _first_id(
        "stock.location",
        [["complete_name", "ilike", from_loc_name], ["usage", "=", "internal"]],
        label=f"source location '{from_loc_name}'",
    )
    to_loc_id = _first_id(
        "stock.location",
        [["complete_name", "ilike", to_loc_name], ["usage", "=", "internal"]],
        label=f"destination location '{to_loc_name}'",
    )
    picking_type_id = _first_id(
        "stock.picking.type",
        [["code", "=", "internal"]],
        label="internal picking type",
    )

    move_vals: dict[str, Any] = {
        "name":             f"Transfer {product_name}",
        "product_id":       pp_id,
        "product_uom_qty":  qty,
        "location_id":      from_loc_id,
        "location_dest_id": to_loc_id,
    }
    if uom_id:
        move_vals["product_uom"] = uom_id

    picking_id = int(odoo.execute("stock.picking", "create", {
        "picking_type_id":  picking_type_id,
        "location_id":      from_loc_id,
        "location_dest_id": to_loc_id,
        "move_ids": [(0, 0, move_vals)],
    }))
    odoo.execute("stock.picking", "action_confirm", [picking_id])

    pick_data = odoo.search_read("stock.picking", [["id", "=", picking_id]], ["name"])[0]
    return {
        "odoo_model":      "stock.picking",
        "odoo_record_ids": [picking_id],
        "picking_name":    pick_data["name"],
    }


def execute_inventory_adjustment(payload: dict[str, Any]) -> dict[str, Any]:
    product_name  = str(payload.get("product") or "")
    location_name = str(payload.get("location") or "WH/Stock")
    qty = float(payload["qty"]) if payload.get("qty") is not None else 0.0

    if qty < 0:
        raise WritebackError("Inventory adjustment quantity must be >= 0.")

    pp = _product_variant(product_name)
    pp_id = int(pp["id"])

    location_id = _first_id(
        "stock.location",
        [["complete_name", "ilike", location_name], ["usage", "=", "internal"]],
        label=f"location '{location_name}'",
    )

    quant_ids = odoo.execute(
        "stock.quant",
        "search",
        [["product_id", "=", pp_id], ["location_id", "=", location_id]],
        limit=1,
    )
    if quant_ids:
        quant_id = int(quant_ids[0])
        odoo.execute("stock.quant", "write", [quant_id], {"inventory_quantity": qty})
    else:
        quant_id = int(odoo.execute("stock.quant", "create", {
            "product_id": pp_id,
            "location_id": location_id,
            "inventory_quantity": qty,
        }))

    odoo.execute("stock.quant", "action_apply_inventory", [quant_id])
    return {"odoo_model": "stock.quant", "odoo_record_ids": [quant_id], "adjusted_qty": qty}


def execute_vendor_price_update(payload: dict[str, Any]) -> dict[str, Any]:
    updates = payload.get("updates") or []
    if not updates:
        raise WritebackError("Vendor price update has no items.")

    record_ids: list[int] = []
    changes: list[dict[str, Any]] = []

    for update in updates:
        product_name  = str(update.get("product") or "")
        supplier_name = update.get("supplier")
        new_price     = update.get("new_price")
        lead_time     = update.get("lead_time_days")

        if new_price is None and lead_time is None:
            raise WritebackError(f"Item for '{product_name}' needs new_price or lead_time_days.")

        tmpl_id = _product_template_id(product_name)
        domain: list[Any] = [["product_tmpl_id", "=", tmpl_id]]
        partner_id: int | None = None
        if supplier_name:
            partner_id = _first_id(
                "res.partner",
                [["name", "ilike", supplier_name], ["supplier_rank", ">", 0]],
                label=f"supplier '{supplier_name}'",
            )
            domain.append(["partner_id", "=", partner_id])

        infos = odoo.search_read(
            "product.supplierinfo",
            domain=domain,
            fields=["id", "partner_id", "price", "delay"],
        )
        vals: dict[str, Any] = {}
        if new_price is not None:
            vals["price"] = round(float(new_price), 4)
        if lead_time is not None:
            vals["delay"] = int(lead_time)

        if infos:
            for info in infos:
                info_id = int(info["id"])
                odoo.execute("product.supplierinfo", "write", [info_id], vals)
                record_ids.append(info_id)
                changes.append({
                    "product":       product_name,
                    "supplier":      info["partner_id"][1] if info.get("partner_id") else "unknown",
                    "old_price":     float(info.get("price") or 0),
                    "new_price":     vals.get("price", float(info.get("price") or 0)),
                    "old_lead_days": info.get("delay"),
                    "new_lead_days": vals.get("delay", info.get("delay")),
                    "action":        "updated",
                })
        else:
            create_vals: dict[str, Any] = {"product_tmpl_id": tmpl_id, **vals}
            if partner_id is not None:
                create_vals["partner_id"] = partner_id
            new_id = int(odoo.execute("product.supplierinfo", "create", create_vals))
            record_ids.append(new_id)
            changes.append({
                "product":    product_name,
                "supplier":   supplier_name or "unknown",
                "new_price":  vals.get("price"),
                "new_lead_days": vals.get("delay"),
                "action":     "created",
            })

    return {"odoo_model": "product.supplierinfo", "odoo_record_ids": record_ids, "changes": changes}


def execute_sale_order_cancel(payload: dict[str, Any]) -> dict[str, Any]:
    order_names = [str(n) for n in (payload.get("order_names") or []) if n]
    if not order_names:
        raise WritebackError("Sale order cancel has no order references.")

    cancelled_ids: list[int] = []
    skipped: list[str] = []

    for name in order_names:
        ids = odoo.execute(
            "sale.order",
            "search",
            [["name", "=", name], ["state", "in", ["draft", "sent", "sale"]]],
            limit=1,
        )
        if not ids:
            skipped.append(f"{name}: not found or already in non-cancellable state")
            continue
        order_id = int(ids[0])
        odoo.execute("sale.order", "action_cancel", [order_id])
        cancelled_ids.append(order_id)

    if not cancelled_ids:
        raise WritebackError(f"No orders cancelled. Issues: {'; '.join(skipped)}")

    return {
        "odoo_model": "sale.order",
        "odoo_record_ids": cancelled_ids,
        "cancelled_count": len(cancelled_ids),
        "skipped": skipped,
    }


def execute_writeback(action_id: str) -> dict[str, Any]:
    action = _get_pending_action(action_id)

    # Atomically claim the action before touching Odoo; this prevents double-execution.
    if not try_claim_writeback_action(action_id, config.APPROVER_DISPLAY_NAME):
        raise WritebackError("Write-back action was already claimed by a concurrent request.")

    payload = action["payload"]
    try:
        if action["action_type"] == "discount_rule":
            result = execute_discount_rule(payload)
        elif action["action_type"] == "restock_rule":
            result = execute_restock_rule(payload)
        elif action["action_type"] == "purchase_order":
            result = execute_purchase_order(payload)
        elif action["action_type"] == "invoice_reminder":
            result = execute_invoice_reminder(payload)
        elif action["action_type"] == "price_update":
            result = execute_price_update(payload)
        elif action["action_type"] == "pos_pricelist":
            result = execute_pos_pricelist(payload)
        elif action["action_type"] == "email_campaign":
            result = execute_email_campaign(payload)
        elif action["action_type"] == "transfer_stock":
            result = execute_transfer_stock(payload)
        elif action["action_type"] == "inventory_adjustment":
            result = execute_inventory_adjustment(payload)
        elif action["action_type"] == "vendor_price_update":
            result = execute_vendor_price_update(payload)
        elif action["action_type"] == "sale_order_cancel":
            result = execute_sale_order_cancel(payload)
        else:
            raise WritebackError(f"Unsupported write-back action type: {action['action_type']}.")
    except Exception as exc:
        update_writeback_status(
            action_id=action_id,
            status="failed",
            error=str(exc),
            decided_by=config.APPROVER_DISPLAY_NAME,
        )
        raise WritebackError(str(exc)) from exc

    updated = update_writeback_status(
        action_id=action_id,
        status="approved",
        odoo_model=result["odoo_model"],
        odoo_record_ids=result["odoo_record_ids"],
        error=None,
        decided_by=config.APPROVER_DISPLAY_NAME,
    )
    if updated is None:
        raise WritebackError("Write-back action disappeared during approval.")
    return updated


def reject_writeback(action_id: str) -> dict[str, Any]:
    _get_pending_action(action_id)
    if not try_reject_writeback_action(action_id, config.APPROVER_DISPLAY_NAME):
        raise WritebackError("Write-back action was already claimed by a concurrent request.")
    updated = get_writeback_action(action_id)
    if updated is None:
        raise WritebackError("Write-back action disappeared during rejection.")
    return updated
