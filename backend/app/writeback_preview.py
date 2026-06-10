"""Server-built previews for human-approved Odoo write-backs.

The preview is audit/display data. Approval execution still validates and uses
the stored payload, not the preview.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from .session_store import get_session_engine


def _as_text(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _change(field: str, old_value: Any, new_value: Any, label: str | None = None) -> dict[str, Any]:
    return {
        "field": field,
        "label": label or field,
        "old_value": old_value,
        "new_value": new_value,
    }


def _record(
    *,
    label: str,
    operation: str,
    odoo_id: int | None = None,
    changes: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "label": label,
        "operation": operation,
        "odoo_id": odoo_id,
        "changes": changes or [],
        "metadata": metadata or {},
    }


def _preview(
    *,
    odoo_model: str,
    operation: str,
    records: list[dict[str, Any]],
    expected_impact: list[str],
    risk_notes: list[str],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "odoo_model": odoo_model,
        "operation": operation,
        "records": records,
        "expected_impact": expected_impact,
        "risk_notes": risk_notes,
        "metadata": metadata or {},
    }


def _json_safe_pair(payload: dict[str, Any], preview: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        json.loads(json.dumps(payload, default=str)),
        json.loads(json.dumps(preview, default=str)),
    )


def _fetch_one(sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
    try:
        with get_session_engine().connect() as conn:
            row = conn.execute(text(sql), params).mappings().first()
        return dict(row) if row else None
    except Exception:
        return None


def _fetch_all(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        with get_session_engine().connect() as conn:
            rows = list(conn.execute(text(sql), params).mappings())
        return [dict(row) for row in rows]
    except Exception:
        return []


def _product_template(product_name: str) -> dict[str, Any] | None:
    return _fetch_one(
        """
        SELECT pt.id,
               COALESCE(pt.name->>'en_US', pt.name::text) AS name,
               pt.list_price,
               pt.standard_price,
               pc.name AS category
        FROM product_template pt
        LEFT JOIN product_category pc ON pc.id = pt.categ_id
        WHERE COALESCE(pt.name->>'en_US', pt.name::text) ILIKE :name
        ORDER BY pt.id
        LIMIT 1
        """,
        {"name": f"%{product_name}%"},
    )


def _product_variant(product_name: str) -> dict[str, Any] | None:
    return _fetch_one(
        """
        SELECT pp.id,
               pp.product_tmpl_id,
               COALESCE(pt.name->>'en_US', pt.name::text) AS name,
               pt.list_price,
               pt.standard_price,
               pc.name AS category
        FROM product_product pp
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        LEFT JOIN product_category pc ON pc.id = pt.categ_id
        WHERE COALESCE(pt.name->>'en_US', pt.name::text) ILIKE :name
        ORDER BY pp.id
        LIMIT 1
        """,
        {"name": f"%{product_name}%"},
    )


def _sales_units(product_name: str, horizon_days: int = 90) -> float:
    row = _fetch_one(
        """
        SELECT COALESCE(SUM(sol.product_uom_qty), 0) AS units
        FROM sale_order_line sol
        JOIN sale_order so ON so.id = sol.order_id
        JOIN product_product pp ON pp.id = sol.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        WHERE so.state IN ('sale', 'done')
          AND so.date_order >= now() - (:days || ' days')::interval
          AND COALESCE(pt.name->>'en_US', pt.name::text) ILIKE :name
        """,
        {"days": horizon_days, "name": f"%{product_name}%"},
    )
    return float(row["units"]) if row and row.get("units") is not None else 0.0


def _current_orderpoint(product_name: str) -> dict[str, Any] | None:
    return _fetch_one(
        """
        SELECT swo.id, swo.product_min_qty, swo.product_max_qty, swo.qty_multiple
        FROM stock_warehouse_orderpoint swo
        JOIN product_product pp ON pp.id = swo.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        WHERE COALESCE(pt.name->>'en_US', pt.name::text) ILIKE :name
        ORDER BY swo.id
        LIMIT 1
        """,
        {"name": f"%{product_name}%"},
    )


def _supplier_for_items(items: list[dict[str, Any]], requested_supplier: str | None) -> dict[str, Any]:
    product_names = [str(item.get("product") or "") for item in items if item.get("product")]
    requested = requested_supplier.strip() if requested_supplier else ""
    if requested:
        row = _fetch_one(
            """
            SELECT id, name
            FROM res_partner
            WHERE supplier_rank > 0 AND name ILIKE :name
            ORDER BY supplier_rank DESC, id
            LIMIT 1
            """,
            {"name": f"%{requested}%"},
        )
        if row:
            return {"supplier_id": row["id"], "supplier": row["name"], "source": "requested"}

    params: dict[str, Any] = {}
    filters: list[str] = []
    for index, product_name in enumerate(product_names):
        key = f"product_{index}"
        params[key] = f"%{product_name}%"
        filters.append(f"COALESCE(pt.name->>'en_US', pt.name::text) ILIKE :{key}")
    rows = _fetch_all(
        f"""
        SELECT rp.id AS supplier_id,
               rp.name AS supplier,
               COUNT(*) AS purchase_count,
               AVG(pol.price_unit) AS avg_purchase_price,
               AVG(EXTRACT(day FROM COALESCE(po.effective_date, po.date_approve) - po.date_order)) AS avg_lead_days
        FROM purchase_order_line pol
        JOIN purchase_order po ON po.id = pol.order_id
        JOIN res_partner rp ON rp.id = po.partner_id
        JOIN product_product pp ON pp.id = pol.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        WHERE po.state IN ('purchase', 'done')
          AND ({' OR '.join(filters) if filters else 'FALSE'})
        GROUP BY rp.id, rp.name
        ORDER BY purchase_count DESC, avg_purchase_price ASC NULLS LAST
        LIMIT 1
        """,
        params,
    )
    if rows:
        return {**rows[0], "source": "historical purchases"}

    row = _fetch_one(
        """
        SELECT id, name
        FROM res_partner
        WHERE supplier_rank > 0
        ORDER BY supplier_rank DESC, id
        LIMIT 1
        """,
        {},
    )
    if row:
        return {"supplier_id": row["id"], "supplier": row["name"], "source": "highest supplier rank"}
    return {"supplier_id": None, "supplier": requested or "Unresolved supplier", "source": "unresolved"}


def _email_segment(segment: str) -> dict[str, Any]:
    if not segment or segment == "all_customers":
        row = _fetch_one(
            "SELECT COUNT(*) AS recipient_count FROM res_partner WHERE customer_rank > 0",
            {},
        )
        return {
            "recipient_count": int(row["recipient_count"] or 0) if row else 0,
            "mailing_domain": str([["customer_rank", ">", 0]]),
            "label": "All customers",
        }

    row = _fetch_one(
        """
        SELECT COUNT(DISTINCT so.partner_id) AS recipient_count
        FROM sale_order so
        JOIN sale_order_line sol ON sol.order_id = so.id
        JOIN product_product pp ON pp.id = sol.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        JOIN product_category pc ON pc.id = pt.categ_id
        WHERE so.state IN ('sale', 'done')
          AND pc.name ILIKE :category
        """,
        {"category": segment},
    )
    partner_rows = _fetch_all(
        """
        SELECT DISTINCT so.partner_id
        FROM sale_order so
        JOIN sale_order_line sol ON sol.order_id = so.id
        JOIN product_product pp ON pp.id = sol.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        JOIN product_category pc ON pc.id = pt.categ_id
        WHERE so.state IN ('sale', 'done')
          AND pc.name ILIKE :category
          AND so.partner_id IS NOT NULL
        LIMIT 500
        """,
        {"category": segment},
    )
    partner_ids = [int(row["partner_id"]) for row in partner_rows if row.get("partner_id")]
    mailing_domain = str([["id", "in", partner_ids]]) if partner_ids else str([["customer_rank", ">", 0]])
    return {
        "recipient_count": int(row["recipient_count"] or 0) if row else len(partner_ids),
        "mailing_domain": mailing_domain,
        "label": f"Customers who bought {segment}",
    }


def _overdue_invoices(customer: str) -> list[dict[str, Any]]:
    return _fetch_all(
        """
        SELECT am.id,
               am.name,
               am.invoice_date_due,
               am.amount_residual,
               rp.name AS customer
        FROM account_move am
        JOIN res_partner rp ON rp.id = am.partner_id
        WHERE rp.name ILIKE :customer
          AND am.move_type = 'out_invoice'
          AND am.state = 'posted'
          AND am.payment_state IN ('not_paid', 'partial')
          AND am.invoice_date_due < CURRENT_DATE
        ORDER BY am.invoice_date_due ASC
        LIMIT 25
        """,
        {"customer": f"%{customer}%"},
    )


def prepare_writeback_action(action_type: str, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(json.dumps(payload, default=str))

    if action_type == "purchase_order":
        return _json_safe_pair(*_prepare_purchase_order(payload))
    if action_type == "email_campaign":
        return _json_safe_pair(*_prepare_email_campaign(payload))
    if action_type == "invoice_reminder":
        return _json_safe_pair(*_prepare_invoice_reminder(payload))
    if action_type == "pos_pricelist":
        return _json_safe_pair(payload, _preview_pos_pricelist(payload))
    if action_type == "restock_rule":
        return _json_safe_pair(payload, _preview_restock_rule(payload))
    if action_type == "discount_rule":
        return _json_safe_pair(payload, _preview_discount_rule(payload))
    if action_type == "price_update":
        return _json_safe_pair(payload, _preview_price_update(payload))
    if action_type == "transfer_stock":
        return _json_safe_pair(payload, _preview_transfer_stock(payload))

    return _json_safe_pair(payload, _preview(
        odoo_model="unknown",
        operation=action_type,
        records=[],
        expected_impact=["Server stored a pending action for human review."],
        risk_notes=["Unsupported preview type; approval will still run server validation."],
    ))


def _prepare_purchase_order(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    items = payload.get("items") or []
    supplier = _supplier_for_items(items, str(payload.get("supplier") or ""))
    payload["supplier"] = supplier["supplier"]
    payload["supplier_id"] = supplier.get("supplier_id")
    payload["supplier_source"] = supplier.get("source")

    total_cost = 0.0
    records = []
    for item in items:
        product_name = str(item.get("product") or "")
        qty = float(item.get("qty") or 0)
        unit_price = float(item.get("unit_price") or 0)
        total_cost += qty * unit_price
        orderpoint = _current_orderpoint(product_name)
        records.append(
            _record(
                label=product_name,
                operation="create_line",
                changes=[
                    _change("product_qty", None, qty, "Quantity"),
                    _change("price_unit", None, unit_price, "Unit cost"),
                    _change("supplier", None, supplier["supplier"], "Supplier"),
                ],
                metadata={"current_reorder_rule": orderpoint or "None"},
            )
        )

    lead = supplier.get("avg_lead_days")
    lead_text = f"{float(lead):.1f} days" if lead is not None else "not enough history"
    return payload, _preview(
        odoo_model="purchase.order",
        operation="create_confirmed_order",
        records=records,
        expected_impact=[
            f"Creates one confirmed purchase order for {_as_text(supplier['supplier'])}.",
            f"Estimated total cost: ${total_cost:,.2f}.",
            f"Estimated supplier lead time: {lead_text}.",
        ],
        risk_notes=[
            "Approval confirms the PO; supplier, quantities, and prices are revalidated by Odoo.",
            "No automatic receipt is created; warehouse receiving remains a separate process.",
        ],
        metadata={"supplier": supplier, "estimated_total_cost": round(total_cost, 2)},
    )


def _prepare_email_campaign(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    segment = str(payload.get("segment") or "all_customers")
    segment_info = _email_segment(segment)
    payload["mailing_domain"] = segment_info["mailing_domain"]
    payload["recipient_count"] = segment_info["recipient_count"]
    return payload, _preview(
        odoo_model="mailing.mailing",
        operation="create_draft",
        records=[
            _record(
                label=str(payload.get("subject") or "Email campaign"),
                operation="create",
                changes=[
                    _change("subject", None, payload.get("subject"), "Subject"),
                    _change("mailing_domain", None, segment_info["label"], "Target segment"),
                    _change("state", None, "draft", "State"),
                ],
                metadata={
                    "recipient_count": segment_info["recipient_count"],
                    "body_preview": str(payload.get("body_html") or "")[:500],
                },
            )
        ],
        expected_impact=[
            f"Creates a draft campaign for {segment_info['recipient_count']} recipients.",
            "Never auto-sends; the human still reviews and sends from Odoo.",
        ],
        risk_notes=[
            "Recipient count is a point-in-time preview and is re-evaluated by Odoo domain rules.",
            "Subject and body should be reviewed for brand/compliance before sending.",
        ],
        metadata=segment_info,
    )


def _prepare_invoice_reminder(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    customer = str(payload.get("customer") or "")
    invoices = _overdue_invoices(customer)
    payload["invoice_ids"] = [int(inv["id"]) for inv in invoices]
    payload["overdue_invoices"] = invoices
    records = [
        _record(
            label=str(inv.get("name") or f"Invoice {inv['id']}"),
            operation="create_activity",
            odoo_id=int(inv["id"]),
            changes=[
                _change("activity", None, "Payment reminder", "Activity"),
                _change("note", None, payload.get("message"), "Message"),
            ],
            metadata={
                "due_date": str(inv.get("invoice_date_due")),
                "residual": float(inv.get("amount_residual") or 0),
            },
        )
        for inv in invoices
    ]
    return payload, _preview(
        odoo_model="mail.activity",
        operation="create_followups",
        records=records,
        expected_impact=[f"Creates payment reminder activities on {len(invoices)} overdue invoices."],
        risk_notes=[
            "Approval revalidates that invoices are still posted, unpaid, and overdue.",
            "No invoice payment state is changed by this action.",
        ],
        metadata={"customer": customer, "message_preview": str(payload.get("message") or "")[:500]},
    )


def _preview_pos_pricelist(payload: dict[str, Any]) -> dict[str, Any]:
    pricelist_name = str(payload.get("pricelist_name") or "")
    current = _fetch_one(
        """
        SELECT pc.id AS config_id,
               pc.name AS config_name,
               current_pl.name AS current_pricelist,
               target_pl.id AS target_pricelist_id,
               target_pl.name AS target_pricelist
        FROM pos_config pc
        LEFT JOIN product_pricelist current_pl ON current_pl.id = pc.pricelist_id
        LEFT JOIN product_pricelist target_pl ON target_pl.name = :target
        WHERE pc.name = 'Main Store'
        LIMIT 1
        """,
        {"target": pricelist_name},
    )
    affected = _fetch_all(
        """
        SELECT COALESCE(pt.name->>'en_US', pt.name::text) AS product,
               ppi.percent_price,
               ppi.fixed_price
        FROM product_pricelist_item ppi
        JOIN product_pricelist pl ON pl.id = ppi.pricelist_id
        LEFT JOIN product_template pt ON pt.id = ppi.product_tmpl_id
        WHERE pl.name = :target
        LIMIT 12
        """,
        {"target": pricelist_name},
    )
    return _preview(
        odoo_model="pos.config",
        operation="update_main_store_pricelist",
        records=[
            _record(
                label="Main Store",
                operation="update",
                odoo_id=int(current["config_id"]) if current and current.get("config_id") else None,
                changes=[
                    _change(
                        "pricelist_id",
                        current.get("current_pricelist") if current else None,
                        pricelist_name,
                        "POS pricelist",
                    )
                ],
                metadata={"affected_products": affected},
            )
        ],
        expected_impact=["Only the Main Store POS config changes.", f"{len(affected)} sample affected pricelist items found."],
        risk_notes=["Cashiers will see the new POS pricing after the POS session reloads."],
        metadata={"affected_products": affected},
    )


def _preview_restock_rule(payload: dict[str, Any]) -> dict[str, Any]:
    records = []
    for item in payload.get("items") or []:
        product_name = str(item.get("product") or "")
        current = _current_orderpoint(product_name)
        records.append(
            _record(
                label=product_name,
                operation="update" if current else "create",
                odoo_id=int(current["id"]) if current and current.get("id") else None,
                changes=[
                    _change("product_min_qty", current.get("product_min_qty") if current else None, item.get("min_qty"), "Minimum quantity"),
                    _change("product_max_qty", current.get("product_max_qty") if current else None, item.get("max_qty"), "Maximum quantity"),
                    _change("qty_multiple", current.get("qty_multiple") if current else None, item.get("qty_multiple", 1), "Order multiple"),
                ],
            )
        )
    return _preview(
        odoo_model="stock.warehouse.orderpoint",
        operation="upsert_manual_reorder_rules",
        records=records,
        expected_impact=[f"Creates or updates {len(records)} manual reordering rules."],
        risk_notes=["Rules are manual triggers; approval does not automatically place purchase orders."],
    )


def _preview_discount_rule(payload: dict[str, Any]) -> dict[str, Any]:
    discount = float(payload.get("discount_percent") or 0)
    records = []
    for product in payload.get("products") or []:
        row = _product_template(str(product))
        old_price = float(row["list_price"]) if row and row.get("list_price") is not None else None
        new_price = round(old_price * (1 - discount / 100), 2) if old_price is not None else None
        records.append(
            _record(
                label=str(product),
                operation="create",
                odoo_id=int(row["id"]) if row else None,
                changes=[
                    _change("percent_price", None, discount, "Discount percent"),
                    _change("effective_price", old_price, new_price, "Effective list price"),
                    _change("min_quantity", None, payload.get("min_quantity", 1), "Minimum quantity"),
                ],
                metadata={"last_90d_units": _sales_units(str(product))},
            )
        )
    return _preview(
        odoo_model="product.pricelist.item",
        operation="create_discount_items",
        records=records,
        expected_impact=[f"Creates discount rules for {len(records)} products."],
        risk_notes=["Margin impact depends on actual POS/sales pricelist usage and product cost."],
    )


def _preview_price_update(payload: dict[str, Any]) -> dict[str, Any]:
    records = []
    for update in payload.get("updates") or []:
        product_name = str(update.get("product") or "")
        row = _product_template(product_name)
        current = float(row["list_price"]) if row and row.get("list_price") is not None else None
        if update.get("new_price") is not None:
            new_price = round(float(update["new_price"]), 2)
        elif current is not None:
            new_price = round(current * (1 + float(update.get("pct_change") or 0) / 100), 2)
        else:
            new_price = update.get("pct_change")
        records.append(
            _record(
                label=product_name,
                operation="update",
                odoo_id=int(row["id"]) if row else None,
                changes=[_change("list_price", current, new_price, "List price")],
            )
        )
    return _preview(
        odoo_model="product.template",
        operation="update_list_prices",
        records=records,
        expected_impact=[f"Updates list prices on {len(records)} products."],
        risk_notes=["Approval writes product.template list_price directly."],
    )


def _preview_transfer_stock(payload: dict[str, Any]) -> dict[str, Any]:
    product = str(payload.get("product") or "")
    return _preview(
        odoo_model="stock.picking",
        operation="create_internal_transfer",
        records=[
            _record(
                label=product,
                operation="create",
                changes=[
                    _change("product_uom_qty", None, payload.get("qty"), "Quantity"),
                    _change("location_id", payload.get("from_location"), payload.get("to_location"), "Location"),
                ],
            )
        ],
        expected_impact=[f"Creates an internal transfer for {payload.get('qty')} x {product}."],
        risk_notes=["Warehouse staff still validates and completes the stock transfer in Odoo."],
    )
