"""Agent tools. Each has a JSON schema (sent to the LLM) and an implementation.

Keep tools small, read-only, and predictable. The LLM does the reasoning;
tools just fetch facts.
"""
import json
import re

import numpy as np
import pandas as pd
import statsmodels.api as sm
import sqlparse
from sqlparse.sql import Identifier, IdentifierList, Parenthesis
from sqlparse.tokens import DML, Keyword, Name, Punctuation
from sqlalchemy import create_engine, text

from .config import config
from .odoo_client import odoo

_engine = None

SQL_ROW_CAP = 100
SQL_TIMEOUT_MS = 5000
ALLOWED_SQL_TABLES = {
    "product_template",
    "product_product",
    "product_category",
    "sale_order",
    "sale_order_line",
    "stock_quant",
    "stock_location",
    "res_partner",
    # Added for purchase, invoicing, POS, marketing phases
    "purchase_order",
    "purchase_order_line",
    "account_move",
    "account_move_line",
    "pos_order",
    "pos_order_line",
    "mailing_mailing",
    "mail_activity",
    "product_pricelist",
    "product_pricelist_item",
    "pos_config",
    "stock_warehouse_orderpoint",
}
TABLE_REFERENCE_KEYWORDS = {
    "FROM",
    "JOIN",
    "INNER JOIN",
    "LEFT JOIN",
    "LEFT OUTER JOIN",
    "RIGHT JOIN",
    "RIGHT OUTER JOIN",
    "FULL JOIN",
    "FULL OUTER JOIN",
    "CROSS JOIN",
}
TABLE_REFERENCE_STOPWORDS = {
    "WHERE",
    "GROUP BY",
    "ORDER BY",
    "HAVING",
    "LIMIT",
    "OFFSET",
    "UNION",
    "EXCEPT",
    "INTERSECT",
    "ON",
}


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(config.PG_URL, execution_options={"postgresql_readonly": True})
    return _engine


def _strip_trailing_semicolon(sql: str) -> str:
    return sql.strip().rstrip(";").strip()


def _parenthesis_sql(token: Parenthesis) -> str:
    value = str(token).strip()
    if value.startswith("(") and value.endswith(")"):
        return value[1:-1].strip()
    return value


def _identifier_table_name(identifier: Identifier) -> str | None:
    real_name = identifier.get_real_name()
    if real_name:
        return real_name.lower()

    names = [
        token.value.lower()
        for token in identifier.tokens
        if token.ttype in (Name,) and token.value
    ]
    return names[-1] if names else None


def _tables_from_token(token) -> set[str]:
    if isinstance(token, IdentifierList):
        tables: set[str] = set()
        for identifier in token.get_identifiers():
            tables.update(_tables_from_token(identifier))
        return tables

    if isinstance(token, Identifier):
        nested_tables: set[str] = set()
        for child in token.tokens:
            if isinstance(child, Parenthesis):
                nested_tables.update(extract_sql_tables(_parenthesis_sql(child)))
        if nested_tables:
            return nested_tables
        table_name = _identifier_table_name(token)
        return {table_name} if table_name else set()

    if isinstance(token, Parenthesis):
        return extract_sql_tables(_parenthesis_sql(token))

    if token.ttype in (Name,):
        return {token.value.lower()}

    return set()


def _cte_aliases_from_token(token) -> set[str]:
    if isinstance(token, IdentifierList):
        aliases: set[str] = set()
        for identifier in token.get_identifiers():
            aliases.update(_cte_aliases_from_token(identifier))
        return aliases

    if isinstance(token, Identifier):
        first_name = next(
            (
                child.value.lower()
                for child in token.tokens
                if child.ttype in (Name,) and child.value
            ),
            None,
        )
        return {first_name} if first_name else set()

    return set()


def extract_sql_tables(sql: str) -> set[str]:
    tables: set[str] = set()
    cte_aliases: set[str] = set()
    for statement in sqlparse.parse(sql):
        expect_table = False
        in_cte = False
        for token in statement.tokens:
            if token.is_whitespace or token.ttype is Punctuation:
                continue

            value = token.normalized.upper()
            if token.ttype is Keyword.CTE and value == "WITH":
                in_cte = True
                continue

            if in_cte and token.ttype is DML and value == "SELECT":
                in_cte = False

            if in_cte:
                cte_aliases.update(_cte_aliases_from_token(token))
                tables.update(_tables_from_token(token))
                continue

            if expect_table:
                if token.ttype is Keyword and value in TABLE_REFERENCE_STOPWORDS:
                    expect_table = False
                else:
                    tables.update(_tables_from_token(token))
                    expect_table = False

            if token.ttype is Keyword and value in TABLE_REFERENCE_KEYWORDS:
                expect_table = True
            elif isinstance(token, Parenthesis):
                tables.update(extract_sql_tables(_parenthesis_sql(token)))

    return {table for table in tables if table and table not in cte_aliases}


def validate_sql(sql: str) -> str:
    cleaned = _strip_trailing_semicolon(sql)
    statements = [statement for statement in sqlparse.parse(cleaned) if str(statement).strip()]
    if len(statements) != 1:
        raise ValueError("Only a single SELECT statement is allowed.")

    statement = statements[0]
    if statement.get_type() != "SELECT":
        raise ValueError("Only SELECT statements are allowed.")

    tables = extract_sql_tables(cleaned)
    blocked = sorted(table for table in tables if table not in ALLOWED_SQL_TABLES)
    if blocked:
        allowed = ", ".join(sorted(ALLOWED_SQL_TABLES))
        raise ValueError(f"SQL references non-allowlisted table(s): {', '.join(blocked)}. Allowed tables: {allowed}.")

    return cleaned


def cap_sql(sql: str, row_cap: int = SQL_ROW_CAP) -> str:
    stripped = sql.strip()
    # CTEs (WITH ...) cannot appear inside a FROM subquery in PostgreSQL.
    # Append LIMIT directly to the outer SELECT instead of wrapping.
    if re.match(r"(?i)^\s*with\b", stripped):
        return f"{stripped} LIMIT {row_cap}"
    return f"SELECT * FROM ({stripped}) AS guarded_query LIMIT {row_cap}"

# --- Tool schemas advertised to the model ---------------------------------

TOOL_SCHEMAS = [
    {
        "name": "odoo_query",
        "description": (
            "Read records from an Odoo model via search_read. Use for catalog, stock, "
            "or order lookups when you need example records. Returns up to `limit` "
            "records as JSON; do not use this for total counts or aggregates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Odoo model, e.g. 'product.template', 'sale.order'."},
                "domain": {"type": "array", "description": "Odoo domain filter, e.g. [['sale_ok','=',true]]. [] for all.", "items": {}},
                "fields": {"type": "array", "items": {"type": "string"}, "description": "Field names to return."},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["model", "fields"],
        },
    },
    {
        "name": "sql_analytics",
        "description": (
            "Run a single read-only SELECT against the Odoo Postgres database for "
            "aggregations the ORM is awkward at (group-bys, joins, time buckets). "
            "Use the schema glossary in the system prompt for Odoo table and field names. "
            f"Only SELECT is allowed. Queries are restricted to allowlisted Odoo tables, "
            f"capped at {SQL_ROW_CAP} returned rows, and timed out after {SQL_TIMEOUT_MS} ms."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "A single SELECT statement."},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "forecast_demand",
        "description": (
            "Forecast monthly units sold for a product category using historical sales. "
            "Fits a seasonal exponential-smoothing model. Returns the forecast plus the "
            "history used, so you can explain the trend."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Product category name as stored in Odoo."},
                "months_ahead": {"type": "integer", "default": 1},
            },
            "required": ["category"],
        },
    },
    {
        "name": "simulate_discount_impact",
        "description": (
            "Read-only scenario planning tool. Estimate what may happen if products are "
            "discounted for a future horizon. This never writes to Odoo and never creates "
            "an approval card. Use it for 'what if we discount...' questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "products": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Product names to simulate, e.g. ['Wool Coat'].",
                },
                "discount_percent": {"type": "number", "description": "Discount percent to test."},
                "horizon_days": {"type": "integer", "default": 90},
                "expected_lift_percent": {
                    "type": ["number", "null"],
                    "description": "Expected unit lift. If omitted, defaults to min(discount_percent * 1.2, 50).",
                },
            },
            "required": ["products", "discount_percent"],
        },
    },
    {
        "name": "propose_discount_rule",
        "description": (
            "Draft a human-approval write-back proposal for a product discount rule. "
            "This does not write to Odoo. Use only after analysis shows a pricing action is justified."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "products": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Product names to discount, e.g. ['Wool Coat'].",
                },
                "discount_percent": {"type": "number", "description": "Discount percent, 1-80."},
                "min_quantity": {"type": "number", "default": 1},
                "reason": {"type": "string", "description": "Short data-backed justification for the proposal."},
            },
            "required": ["products", "discount_percent", "reason"],
        },
    },
    {
        "name": "propose_restock_rule",
        "description": (
            "Draft a human-approval write-back proposal for manual Odoo reordering rules. "
            "This does not write to Odoo. Use only after analysis shows replenishment is justified."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product": {"type": "string"},
                            "min_qty": {"type": "number"},
                            "max_qty": {"type": "number"},
                            "qty_multiple": {"type": "number", "default": 1},
                        },
                        "required": ["product", "min_qty", "max_qty"],
                    },
                },
                "reason": {"type": "string", "description": "Short data-backed justification for the proposal."},
            },
            "required": ["items", "reason"],
        },
    },
]


# --- Implementations -------------------------------------------------------

def _read_only_sql(sql: str) -> pd.DataFrame:
    validated_sql = validate_sql(sql)
    capped_sql = cap_sql(validated_sql)
    with _get_engine().connect() as conn:
        with conn.begin():
            conn.execute(text("SET LOCAL TRANSACTION READ ONLY"))
            conn.execute(text(f"SET LOCAL statement_timeout = {SQL_TIMEOUT_MS}"))
            return pd.read_sql_query(text(capped_sql), conn)


def odoo_query(model, fields, domain=None, limit=50):
    rows = odoo.search_read(model, domain=domain, fields=fields, limit=limit)
    return {"count": len(rows), "records": rows}


def sql_analytics(sql):
    df = _read_only_sql(sql)
    return {"rows": df.to_dict(orient="records"), "row_count": len(df), "row_cap": SQL_ROW_CAP}


def forecast_demand(category, months_ahead=1):
    # Monthly units sold for the category, from confirmed sale order lines.
    sql = text("""
        SELECT date_trunc('month', so.date_order) AS month,
               SUM(sol.product_uom_qty)           AS units
        FROM sale_order_line sol
        JOIN sale_order so       ON so.id = sol.order_id
        JOIN product_product pp  ON pp.id = sol.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        JOIN product_category pc ON pc.id = pt.categ_id
        WHERE so.state IN ('sale', 'done')
          AND pc.name = :category
        GROUP BY 1 ORDER BY 1
    """)
    with _get_engine().connect() as conn:
        with conn.begin():
            conn.execute(text(f"SET LOCAL statement_timeout = {SQL_TIMEOUT_MS}"))
            df = pd.read_sql_query(sql, conn, params={"category": category})

    if len(df) < 24:
        return {"error": f"Not enough history for '{category}' to forecast (need >= 24 months)."}

    series = df.set_index("month")["units"].astype(float).asfreq("MS").fillna(0)
    model = sm.tsa.ExponentialSmoothing(
        series, trend="add", seasonal="add", seasonal_periods=12
    ).fit()
    fc = model.forecast(months_ahead)

    if not np.isfinite(fc.values).all():
        return {
            "error": (
                f"Forecast model produced invalid values for '{category}'. "
                "The category may have too many zero-sales months for seasonal smoothing."
            )
        }

    return {
        "category": category,
        "history": [{"month": str(i.date()), "units": float(v)} for i, v in series.items()],
        "forecast": [{"month": str(i.date()), "units": round(float(v), 1)} for i, v in fc.items()],
    }


def simulate_discount_impact(
    products,
    discount_percent,
    horizon_days=90,
    expected_lift_percent=None,
):
    discount_percent = float(discount_percent)
    horizon_days = int(horizon_days or 90)
    if discount_percent <= 0 or discount_percent > 80:
        raise ValueError("discount_percent must be between 0 and 80.")
    if horizon_days <= 0 or horizon_days > 365:
        raise ValueError("horizon_days must be between 1 and 365.")

    product_names = [str(product).strip() for product in products or [] if str(product).strip()]
    if not product_names:
        raise ValueError("At least one product is required.")

    lift_percent = (
        min(discount_percent * 1.2, 50.0)
        if expected_lift_percent is None
        else float(expected_lift_percent)
    )
    if lift_percent < -90 or lift_percent > 300:
        raise ValueError("expected_lift_percent must be between -90 and 300.")

    params: dict[str, object] = {"days": horizon_days}
    filters: list[str] = []
    for index, name in enumerate(product_names):
        key = f"name_{index}"
        params[key] = f"%{name}%"
        filters.append(f"COALESCE(pt.name->>'en_US', pt.name::text) ILIKE :{key}")

    sql = text(f"""
        SELECT pt.id,
               COALESCE(pt.name->>'en_US', pt.name::text) AS product,
               pt.list_price,
               pt.standard_price,
               COALESCE(SUM(sol.product_uom_qty), 0) AS baseline_units
        FROM product_template pt
        LEFT JOIN product_product pp ON pp.product_tmpl_id = pt.id
        LEFT JOIN sale_order_line sol ON sol.product_id = pp.id
        LEFT JOIN sale_order so
          ON so.id = sol.order_id
         AND so.state IN ('sale', 'done')
         AND so.date_order >= now() - (:days || ' days')::interval
        WHERE {' OR '.join(filters)}
        GROUP BY pt.id, product, pt.list_price, pt.standard_price
        ORDER BY product
    """)
    with _get_engine().connect() as conn:
        with conn.begin():
            conn.execute(text("SET LOCAL TRANSACTION READ ONLY"))
            conn.execute(text(f"SET LOCAL statement_timeout = {SQL_TIMEOUT_MS}"))
            df = pd.read_sql_query(sql, conn, params=params)

    results: list[dict[str, object]] = []
    totals = {
        "baseline_revenue": 0.0,
        "baseline_margin": 0.0,
        "simulated_revenue": 0.0,
        "simulated_margin": 0.0,
    }
    for row in df.to_dict(orient="records"):
        price = float(row.get("list_price") or 0)
        cost = float(row.get("standard_price") or 0)
        units = float(row.get("baseline_units") or 0)
        simulated_price = round(price * (1 - discount_percent / 100), 2)
        simulated_units = round(units * (1 + lift_percent / 100), 1)
        baseline_revenue = units * price
        baseline_margin = units * (price - cost)
        simulated_revenue = simulated_units * simulated_price
        simulated_margin = simulated_units * (simulated_price - cost)

        totals["baseline_revenue"] += baseline_revenue
        totals["baseline_margin"] += baseline_margin
        totals["simulated_revenue"] += simulated_revenue
        totals["simulated_margin"] += simulated_margin

        results.append({
            "product": row["product"],
            "baseline_units": round(units, 1),
            "list_price": round(price, 2),
            "standard_price": round(cost, 2),
            "discount_percent": round(discount_percent, 2),
            "expected_lift_percent": round(lift_percent, 2),
            "simulated_price": simulated_price,
            "simulated_units": simulated_units,
            "baseline_revenue": round(baseline_revenue, 2),
            "simulated_revenue": round(simulated_revenue, 2),
            "revenue_delta": round(simulated_revenue - baseline_revenue, 2),
            "baseline_margin": round(baseline_margin, 2),
            "simulated_margin": round(simulated_margin, 2),
            "margin_delta": round(simulated_margin - baseline_margin, 2),
        })

    return {
        "products": results,
        "totals": {
            **{key: round(value, 2) for key, value in totals.items()},
            "revenue_delta": round(totals["simulated_revenue"] - totals["baseline_revenue"], 2),
            "margin_delta": round(totals["simulated_margin"] - totals["baseline_margin"], 2),
        },
        "assumptions": [
            f"Historical baseline uses confirmed sales over the last {horizon_days} days.",
            f"Expected unit lift is {lift_percent:g}%.",
            "Costs use product.template.standard_price; this is advisory, not accounting truth.",
        ],
        "risk_notes": [
            "Demand lift is an assumption, not a causal forecast.",
            "Discounts can reduce margin even when revenue rises.",
            "This tool is read-only and creates no Odoo records.",
        ],
    }


def propose_discount_rule(products, discount_percent, reason, min_quantity=1):
    return {
        "action_type": "discount_rule",
        "title": f"Create {float(discount_percent):g}% discount rule",
        "summary": reason,
        "payload": {
            "products": products,
            "discount_percent": float(discount_percent),
            "min_quantity": float(min_quantity or 1),
            "reason": reason,
        },
    }


def propose_restock_rule(items, reason):
    normalized_items = [
        {
            "product": item["product"],
            "min_qty": float(item["min_qty"]),
            "max_qty": float(item["max_qty"]),
            "qty_multiple": float(item.get("qty_multiple") or 1),
        }
        for item in items
    ]
    return {
        "action_type": "restock_rule",
        "title": "Create manual reordering rule",
        "summary": reason,
        "payload": {
            "items": normalized_items,
            "reason": reason,
        },
    }


DISPATCH = {
    "odoo_query": odoo_query,
    "sql_analytics": sql_analytics,
    "forecast_demand": forecast_demand,
    "simulate_discount_impact": simulate_discount_impact,
    "propose_discount_rule": propose_discount_rule,
    "propose_restock_rule": propose_restock_rule,
}


def run_tool(name: str, args: dict) -> str:
    try:
        result = DISPATCH[name](**args)
    except Exception as exc:  # surface errors back to the model so it can recover
        result = {"error": str(exc)}
    return json.dumps(result, default=str)
