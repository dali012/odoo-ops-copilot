# backend/app/tools_writeback.py
"""Write-back proposal tools (human-approval pattern).

Each propose_* function returns a dict with action_type/title/summary/payload.
agent.py persists this as a pending writeback_action. A human approves or
rejects via the API; only then does writeback.py's execute_* function write to Odoo.
"""
from __future__ import annotations

from typing import Any

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "propose_purchase_order",
        "description": (
            "Draft a human-approval write-back proposal for a purchase order to a supplier. "
            "Use only after analysis confirms replenishment is justified (e.g. stock < reorder point, "
            "forecast shows demand). This does not write to Odoo - a human must approve first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier": {
                    "type": "string",
                    "description": "Optional supplier name as stored in Odoo res.partner. If omitted, the backend selects a preferred supplier from purchase history.",
                },
                "items": {
                    "type": "array",
                    "description": "Order lines.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product":    {"type": "string", "description": "Product display name."},
                            "qty":        {"type": "number", "description": "Ordered quantity."},
                            "unit_price": {"type": "number", "description": "Price per unit."},
                        },
                        "required": ["product", "qty", "unit_price"],
                    },
                },
                "reason": {"type": "string", "description": "Short data-backed justification."},
            },
            "required": ["items", "reason"],
        },
    },
    {
        "name": "propose_invoice_reminder",
        "description": (
            "Draft a human-approval action to add a payment follow-up activity on overdue "
            "customer invoices. Use after sql_analytics confirms unpaid overdue balances. "
            "This does not write to Odoo - a human must approve first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer": {"type": "string", "description": "Customer name as stored in Odoo."},
                "message":  {"type": "string", "description": "Reminder note to attach to the activity."},
            },
            "required": ["customer", "message"],
        },
    },
    {
        "name": "propose_price_update",
        "description": (
            "Draft a human-approval write-back proposal to update product list prices. "
            "Use after analysis confirms pricing action is warranted (e.g. margins too thin, "
            "competitor data, seasonal repricing). This does not write to Odoo - a human must approve first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product": {
                                "type": "string",
                                "description": "Product name (ilike match against product_template.name).",
                            },
                            "new_price": {
                                "type": "number",
                                "description": "Absolute new list price. Provide this OR pct_change, not both.",
                            },
                            "pct_change": {
                                "type": "number",
                                "description": (
                                    "Signed percentage change. 10 means +10%, -5 means -5%. "
                                    "Must be between -80 and +200. Provide this OR new_price, not both."
                                ),
                            },
                        },
                        "required": ["product"],
                    },
                },
                "reason": {"type": "string", "description": "Short data-backed justification."},
            },
            "required": ["updates", "reason"],
        },
    },
    {
        "name": "propose_pos_pricelist",
        "description": (
            "Draft a human-approval proposal to apply a pricelist to the Main Store POS terminal. "
            "Use after confirming the pricelist exists via odoo_query. "
            "This does not write to Odoo - a human must approve first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pricelist_name": {
                    "type": "string",
                    "description": "Exact name of the product.pricelist to apply.",
                },
                "reason": {"type": "string", "description": "Short data-backed justification."},
            },
            "required": ["pricelist_name", "reason"],
        },
    },
    {
        "name": "propose_email_campaign",
        "description": (
            "Draft a human-approval proposal to create a marketing email campaign in Odoo. "
            "The campaign is created in draft state and NEVER auto-sends - the human sends it. "
            "This does not write to Odoo - a human must approve first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject":  {"type": "string", "description": "Email subject line."},
                "body":     {"type": "string", "description": "Email body (plain text or HTML). Will be wrapped in <p> if plain text."},
                "segment":  {"type": "string", "description": "'all_customers' or a product category name to target customers of that category."},
                "reason":   {"type": "string", "description": "Short business justification."},
            },
            "required": ["subject", "body", "segment", "reason"],
        },
    },
    {
        "name": "propose_inventory_adjustment",
        "description": (
            "Draft a human-approval proposal to correct a product's on-hand quantity via a "
            "physical inventory count (stock.quant adjustment). Use after sql_analytics or "
            "odoo_query reveals a discrepancy between system quantity and actual count. "
            "This does not write to Odoo - a human must approve first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product":  {"type": "string", "description": "Product display name."},
                "qty":      {"type": "number", "description": "Correct counted quantity (>= 0)."},
                "location": {"type": "string", "default": "WH/Stock", "description": "Internal stock location name, e.g. 'WH/Stock'."},
                "reason":   {"type": "string", "description": "Short data-backed justification."},
            },
            "required": ["product", "qty", "reason"],
        },
    },
    {
        "name": "propose_vendor_price_update",
        "description": (
            "Draft a human-approval proposal to update purchase price and/or lead time on "
            "product.supplierinfo records. Use after supplier_scorecard finds price drift or "
            "a supplier quote differs from Odoo's recorded price. "
            "This does not write to Odoo - a human must approve first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product":       {"type": "string", "description": "Product display name."},
                            "supplier":      {"type": "string", "description": "Supplier name (optional; updates all vendors if omitted)."},
                            "new_price":     {"type": "number", "description": "New purchase price per unit."},
                            "lead_time_days":{"type": "integer", "description": "New lead time in days."},
                        },
                        "required": ["product"],
                    },
                },
                "reason": {"type": "string", "description": "Short data-backed justification."},
            },
            "required": ["updates", "reason"],
        },
    },
    {
        "name": "propose_sale_order_cancel",
        "description": (
            "Draft a human-approval proposal to cancel one or more confirmed sale orders. "
            "Only orders in draft / sent / sale state can be cancelled. "
            "Use after verifying the order exists and cancellation is appropriate. "
            "This does not write to Odoo - a human must approve first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Sale order reference(s), e.g. ['S00001', 'S00002'].",
                },
                "reason": {"type": "string", "description": "Short business justification."},
            },
            "required": ["order_names", "reason"],
        },
    },
    {
        "name": "propose_transfer_stock",
        "description": (
            "Draft a human-approval proposal for an internal stock transfer between two locations. "
            "The transfer is created in confirmed state for warehouse staff to execute. "
            "This does not write to Odoo - a human must approve first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product":       {"type": "string", "description": "Product display name."},
                "qty":           {"type": "number", "description": "Quantity to transfer."},
                "from_location": {"type": "string", "description": "Source location name, e.g. 'WH/Stock'."},
                "to_location":   {"type": "string", "description": "Destination location name, e.g. 'WH/Output'."},
                "reason":        {"type": "string", "description": "Short business justification."},
            },
            "required": ["product", "qty", "from_location", "to_location", "reason"],
        },
    },
]


# --- Implementations -------------------------------------------------------

def propose_purchase_order(items: list[dict], reason: str, supplier: str | None = None) -> dict[str, Any]:
    supplier_label = supplier or "preferred supplier"
    return {
        "action_type": "purchase_order",
        "title": f"Create PO for {supplier_label}",
        "summary": reason,
        "payload": {
            "supplier": supplier or "",
            "items": [
                {
                    "product":    str(item["product"]),
                    "qty":        float(item["qty"]),
                    "unit_price": float(item["unit_price"]),
                }
                for item in items
            ],
            "reason": reason,
        },
    }


def propose_invoice_reminder(customer: str, message: str) -> dict[str, Any]:
    return {
        "action_type": "invoice_reminder",
        "title": f"Payment reminder: {customer}",
        "summary": message,
        "payload": {"customer": customer, "message": message},
    }


def propose_price_update(updates: list[dict], reason: str) -> dict[str, Any]:
    product_names = [str(u["product"]) for u in updates]
    normalized = []
    for u in updates:
        entry: dict[str, Any] = {"product": str(u["product"])}
        if u.get("new_price") is not None:
            entry["new_price"] = float(u["new_price"])
        if u.get("pct_change") is not None:
            entry["pct_change"] = float(u["pct_change"])
        normalized.append(entry)
    return {
        "action_type": "price_update",
        "title": f"Update prices: {', '.join(product_names)}",
        "summary": reason,
        "payload": {"updates": normalized, "reason": reason},
    }


def propose_pos_pricelist(pricelist_name: str, reason: str) -> dict[str, Any]:
    return {
        "action_type": "pos_pricelist",
        "title": f"Apply pricelist '{pricelist_name}' to Main Store",
        "summary": reason,
        "payload": {"pricelist_name": pricelist_name, "reason": reason},
    }


def propose_email_campaign(subject: str, body: str, segment: str, reason: str) -> dict[str, Any]:
    body_html = body if body.strip().startswith("<") else f"<p>{body}</p>"
    return {
        "action_type": "email_campaign",
        "title": f"Email: {subject}",
        "summary": reason,
        "payload": {
            "subject":   subject,
            "body_html": body_html,
            "segment":   segment,
            "reason":    reason,
        },
    }


def propose_inventory_adjustment(
    product: str,
    qty: float | int,
    reason: str,
    location: str = "WH/Stock",
) -> dict[str, Any]:
    return {
        "action_type": "inventory_adjustment",
        "title": f"Inventory adjustment: {product} → {float(qty):g} units",
        "summary": reason,
        "payload": {
            "product":  product,
            "location": location,
            "qty":      float(qty),
            "reason":   reason,
        },
    }


def propose_vendor_price_update(updates: list[dict], reason: str) -> dict[str, Any]:
    product_names = [str(u.get("product") or "") for u in updates]
    normalized = []
    for u in updates:
        entry: dict[str, Any] = {"product": str(u["product"])}
        if u.get("supplier"):
            entry["supplier"] = str(u["supplier"])
        if u.get("new_price") is not None:
            entry["new_price"] = float(u["new_price"])
        if u.get("lead_time_days") is not None:
            entry["lead_time_days"] = int(u["lead_time_days"])
        normalized.append(entry)
    return {
        "action_type": "vendor_price_update",
        "title": f"Update vendor prices: {', '.join(product_names)}",
        "summary": reason,
        "payload": {"updates": normalized, "reason": reason},
    }


def propose_sale_order_cancel(order_names: list[str], reason: str) -> dict[str, Any]:
    names = [str(n) for n in order_names]
    label = ", ".join(names[:3]) + (f" +{len(names) - 3} more" if len(names) > 3 else "")
    return {
        "action_type": "sale_order_cancel",
        "title": f"Cancel sale order(s): {label}",
        "summary": reason,
        "payload": {"order_names": names, "reason": reason},
    }


def propose_transfer_stock(
    product: str,
    qty: float | int,
    from_location: str,
    to_location: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "action_type": "transfer_stock",
        "title": f"Transfer {qty} x {product}",
        "summary": reason,
        "payload": {
            "product":       product,
            "qty":           float(qty),
            "from_location": from_location,
            "to_location":   to_location,
            "reason":        reason,
        },
    }


DISPATCH: dict[str, Any] = {
    "propose_purchase_order":     propose_purchase_order,
    "propose_invoice_reminder":   propose_invoice_reminder,
    "propose_price_update":       propose_price_update,
    "propose_pos_pricelist":      propose_pos_pricelist,
    "propose_email_campaign":     propose_email_campaign,
    "propose_transfer_stock":     propose_transfer_stock,
    "propose_inventory_adjustment": propose_inventory_adjustment,
    "propose_vendor_price_update":  propose_vendor_price_update,
    "propose_sale_order_cancel":    propose_sale_order_cancel,
}
