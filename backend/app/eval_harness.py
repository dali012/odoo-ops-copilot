"""Golden-question eval harness for the Odoo Ops Copilot agent.

Run from backend/:
    python -m app.eval_harness

The suite calls the real agent, computes expected answers from the live Odoo
Postgres data, and grades responses with deterministic checks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import text

from .agent import chat
from .tools import (
    _get_engine,
    forecast_demand,
    inventory_aging,
    margin_analysis,
    simulate_discount_impact,
    stockout_risk,
    supplier_scorecard,
)

DEFAULT_CASES_PATH = Path(__file__).resolve().parents[1] / "evals" / "golden_questions.json"


@dataclass
class Grade:
    passed: bool
    expected: str
    details: list[str]


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def extract_numbers(text_value: str) -> list[float]:
    return [float(match) for match in re.findall(r"(?<!\w)-?\d+(?:\.\d+)?", text_value.replace(",", ""))]


def contains_number_near(response: str, expected: float, tolerance: float) -> bool:
    return any(abs(number - expected) <= tolerance for number in extract_numbers(response))


def query_one(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    with _get_engine().connect() as conn:
        row = conn.execute(text(sql), params or {}).mappings().first()
    if row is None:
        return {}
    return dict(row)


def query_all(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with _get_engine().connect() as conn:
        rows = conn.execute(text(sql), params or {}).mappings().all()
    return [dict(row) for row in rows]


def grade_active_product_count(response: str) -> Grade:
    row = query_one("SELECT COUNT(*) AS count FROM product_template WHERE active = true")
    expected_count = int(row["count"])
    passed = contains_number_near(response, expected_count, tolerance=0)
    return Grade(
        passed=passed,
        expected=f"{expected_count} active products",
        details=[f"answer numbers={extract_numbers(response)}"],
    )


def grade_outerwear_forecast_next_month(response: str) -> Grade:
    result = forecast_demand("Outerwear", 1)
    if "error" in result:
        return Grade(False, "forecast_demand should succeed", [str(result["error"])])

    forecast = result["forecast"][0]
    units = float(forecast["units"])
    month = str(forecast["month"])[:7]
    month_name = datetime.strptime(str(forecast["month"])[:10], "%Y-%m-%d").strftime("%B %Y")
    normalized = normalize(response)
    passed = (
        "outerwear" in normalized
        and contains_number_near(response, units, tolerance=1.0)
        and (
            month in response
            or month.replace("-", "/") in response
            or month_name.casefold() in normalized
            or "next month" in normalized
        )
    )
    return Grade(
        passed=passed,
        expected=f"Outerwear forecast {units} units for {month}",
        details=[f"answer numbers={extract_numbers(response)}"],
    )


def grade_top_category_units_90d(response: str) -> Grade:
    row = query_one(
        """
        SELECT pc.name AS category, SUM(sol.product_uom_qty)::float AS units
        FROM sale_order_line sol
        JOIN sale_order so ON so.id = sol.order_id
        JOIN product_product pp ON pp.id = sol.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        JOIN product_category pc ON pc.id = pt.categ_id
        WHERE so.state IN ('sale', 'done')
          AND so.date_order >= now() - interval '90 days'
        GROUP BY pc.name
        ORDER BY units DESC
        LIMIT 1
        """
    )
    if not row:
        return Grade(False, "no sales data in last 90 days", ["query returned no rows"])
    category = str(row["category"])
    units = float(row["units"])
    normalized = normalize(response)
    passed = category.casefold() in normalized and contains_number_near(response, units, tolerance=1.0)
    return Grade(
        passed=passed,
        expected=f"{category} with {units:g} units",
        details=[f"answer numbers={extract_numbers(response)}"],
    )


def grade_slowest_products_90d(response: str) -> Grade:
    rows = query_all(
        """
        SELECT COALESCE(pt.name->>'en_US', pt.name::text) AS product,
               SUM(sol.product_uom_qty)::float AS units
        FROM sale_order_line sol
        JOIN sale_order so ON so.id = sol.order_id
        JOIN product_product pp ON pp.id = sol.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        WHERE so.state IN ('sale', 'done')
          AND so.date_order >= now() - interval '90 days'
        GROUP BY pt.name
        ORDER BY units ASC, pt.name ASC
        LIMIT 3
        """
    )
    if not rows:
        return Grade(False, "no sales data in last 90 days", ["query returned no rows"])
    expected_products = [str(row["product"]) for row in rows]
    normalized = normalize(response)
    missing = [product for product in expected_products if product.casefold() not in normalized]
    return Grade(
        passed=not missing,
        expected=", ".join(expected_products),
        details=[f"missing={missing or 'none'}"],
    )


def grade_top_revenue_category_90d(response: str) -> Grade:
    row = query_one(
        """
        SELECT pc.name AS category,
               SUM(sol.product_uom_qty * sol.price_unit)::float AS revenue
        FROM sale_order_line sol
        JOIN sale_order so ON so.id = sol.order_id
        JOIN product_product pp ON pp.id = sol.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        JOIN product_category pc ON pc.id = pt.categ_id
        WHERE so.state IN ('sale', 'done')
          AND so.date_order >= now() - interval '90 days'
        GROUP BY pc.name
        ORDER BY revenue DESC
        LIMIT 1
        """
    )
    if not row:
        return Grade(False, "no sales data in last 90 days", ["query returned no rows"])
    category = str(row["category"])
    revenue = float(row["revenue"])
    normalized = normalize(response)
    # Use 1% relative tolerance so agents that round large revenues still pass.
    tolerance = max(5.0, revenue * 0.01)
    passed = category.casefold() in normalized and contains_number_near(response, revenue, tolerance=tolerance)
    return Grade(
        passed=passed,
        expected=f"{category} with ${revenue:,.0f} revenue",
        details=[f"answer numbers={extract_numbers(response)}", f"tolerance={tolerance:.2f}"],
    )


def grade_schema_sales_by_category(response: str) -> Grade:
    normalized = normalize(response)
    required_terms = [
        "sale_order_line",
        "sale_order",
        "product_product",
        "product_template",
        "product_category",
        "order_id",
        "product_id",
        "product_tmpl_id",
        "categ_id",
    ]
    forbidden_terms = [
        "from orders",
        "join orders",
        "from order_lines",
        "join order_lines",
        "from products",
        "join products",
        "from categories",
        "join categories",
    ]
    missing = [term for term in required_terms if term not in normalized]
    forbidden = [term for term in forbidden_terms if term in normalized]
    return Grade(
        passed=not missing and not forbidden,
        expected="sale_order_line -> sale_order -> product_product -> product_template -> product_category with correct join keys",
        details=[f"missing={missing or 'none'}", f"forbidden={forbidden or 'none'}"],
    )


def grade_schema_units_revenue_fields(response: str) -> Grade:
    normalized = normalize(response)
    required_terms = ["product_uom_qty", "price_unit", "date_order"]
    missing = [term for term in required_terms if term not in normalized]
    has_revenue_formula = "product_uom_qty" in normalized and "price_unit" in normalized
    return Grade(
        passed=not missing and has_revenue_formula,
        expected="units=product_uom_qty, revenue=product_uom_qty * price_unit, order date=date_order",
        details=[f"missing={missing or 'none'}"],
    )


def grade_stockout_risk_top_critical(response: str) -> Grade:
    result = stockout_risk(days_of_history=90, risk_days_threshold=30, limit=5)
    rows = result.get("rows", [])
    urgent = [r for r in rows if r.get("urgency") in ("out_of_stock", "critical")]
    if not urgent:
        urgent = rows  # fall back to any at-risk row
    if not urgent:
        return Grade(False, "stockout_risk returned no at-risk rows", ["tool returned no data"])
    top_product = str(urgent[0]["product"])
    urgency_label = str(urgent[0].get("urgency", "unknown"))
    normalized = normalize(response)
    passed = top_product.casefold() in normalized
    return Grade(
        passed=passed,
        expected=f"Top at-risk product: {top_product} (urgency: {urgency_label})",
        details=[f"top_product={top_product!r}", f"urgency={urgency_label}"],
    )


def grade_inventory_aging_top_dead_stock(response: str) -> Grade:
    result = inventory_aging(days_threshold=60, limit=1)
    rows = result.get("rows", [])
    if not rows:
        # No dead stock in the DB — agent should correctly acknowledge clean inventory.
        normalized = normalize(response)
        clean_report = any(
            phrase in normalized
            for phrase in (
                "no dead stock", "no products", "no stale", "no items",
                "all items", "all products", "good news", "healthy", "clean",
                "no stock", "none",
            )
        )
        return Grade(
            passed=clean_report,
            expected="No dead stock present — agent should report all items sold within 60 days",
            details=["tool returned no rows; verified agent acknowledged clean inventory"],
        )
    top_product = str(rows[0]["product"])
    stock_value = float(rows[0].get("stock_value") or 0)
    normalized = normalize(response)
    passed = top_product.casefold() in normalized
    return Grade(
        passed=passed,
        expected=f"{top_product} (${stock_value:,.2f} stock value, 60+ days unsold)",
        details=[f"top_product={top_product!r}"],
    )


def grade_margin_top_category_gross_profit(response: str) -> Grade:
    result = margin_analysis(group_by="category")
    rows = result.get("rows", [])
    if not rows:
        return Grade(False, "margin_analysis returned no rows", ["no confirmed sales in period"])
    # Results are ordered by gross_profit DESC — first row is the winner.
    top_category = str(rows[0]["name"])
    gross_profit = float(rows[0].get("gross_profit") or 0)
    normalized = normalize(response)
    passed = top_category.casefold() in normalized
    return Grade(
        passed=passed,
        expected=f"{top_category} with ${gross_profit:,.2f} gross profit",
        details=[f"top_category={top_category!r}"],
    )


def grade_supplier_top_by_spend(response: str) -> Grade:
    result = supplier_scorecard(months=6)
    rows = result.get("rows", [])
    if not rows:
        return Grade(False, "supplier_scorecard returned no rows", ["no purchase orders in last 6 months"])
    top_supplier = str(rows[0]["supplier"])
    total_spend = float(rows[0].get("total_spend") or 0)
    normalized = normalize(response)
    passed = top_supplier.casefold() in normalized
    return Grade(
        passed=passed,
        expected=f"{top_supplier} with ${total_spend:,.2f} spend",
        details=[f"top_supplier={top_supplier!r}"],
    )


def grade_simulate_discount_wool_coat(response: str) -> Grade:
    result = simulate_discount_impact(["Wool Coat"], 20.0, horizon_days=90)
    products = result.get("products", [])
    if not products:
        return Grade(False, "simulate_discount_impact found no Wool Coat product", ["product name not matched"])
    p = products[0]
    sim_revenue = float(p["simulated_revenue"])
    rev_delta = float(p["revenue_delta"])
    normalized = normalize(response)
    # Accept either the delta or the simulated total; 5% relative tolerance for rounding.
    has_figure = any([
        contains_number_near(response, abs(rev_delta), tolerance=max(1.0, abs(rev_delta) * 0.05)),
        contains_number_near(response, sim_revenue, tolerance=max(1.0, sim_revenue * 0.05)),
    ])
    passed = "wool coat" in normalized and has_figure and (
        "margin" in normalized or "revenue" in normalized or "profit" in normalized
    )
    return Grade(
        passed=passed,
        expected=f"Wool Coat simulated_revenue=${sim_revenue:,.2f}, revenue_delta=${rev_delta:+,.2f}",
        details=[f"answer numbers={extract_numbers(response)}"],
    )


GRADERS: dict[str, Callable[[str], Grade]] = {
    "active_product_count": grade_active_product_count,
    "outerwear_forecast_next_month": grade_outerwear_forecast_next_month,
    "top_category_units_90d": grade_top_category_units_90d,
    "slowest_products_90d": grade_slowest_products_90d,
    "top_revenue_category_90d": grade_top_revenue_category_90d,
    "schema_sales_by_category": grade_schema_sales_by_category,
    "schema_units_revenue_fields": grade_schema_units_revenue_fields,
    "stockout_risk_top_critical": grade_stockout_risk_top_critical,
    "inventory_aging_top_dead_stock": grade_inventory_aging_top_dead_stock,
    "margin_top_category_gross_profit": grade_margin_top_category_gross_profit,
    "supplier_top_by_spend": grade_supplier_top_by_spend,
    "simulate_discount_wool_coat": grade_simulate_discount_wool_coat,
}


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        cases = json.load(file)
    if not isinstance(cases, list):
        raise ValueError("Eval cases file must contain a JSON array.")
    return cases


def run_eval_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case["id"])
    question = str(case["question"])
    grader_name = str(case["grader"])
    grader = GRADERS[grader_name]

    started = time.perf_counter()
    answer = chat(question)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    grade = grader(answer)

    return {
        "id": case_id,
        "question": question,
        "passed": grade.passed,
        "expected": grade.expected,
        "details": grade.details,
        "answer": answer,
        "elapsed_ms": elapsed_ms,
    }


def print_result(result: dict[str, Any], verbose: bool) -> None:
    status = "PASS" if result["passed"] else "FAIL"
    print(f"[{status}] {result['id']} ({result['elapsed_ms']} ms)")
    print(f"  expected: {result['expected']}")
    for detail in result["details"]:
        print(f"  {detail}")
    if verbose or not result["passed"]:
        print("  answer:")
        print("    " + str(result["answer"]).replace("\n", "\n    "))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run golden-question evals against the agent.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--case-id", action="append", help="Run only the named case ID. Can be repeated.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--verbose", action="store_true", help="Print every full agent answer.")
    parser.add_argument("--fail-under", type=float, default=1.0, help="Minimum pass rate required for exit 0.")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if args.case_id:
        allowed = set(args.case_id)
        cases = [case for case in cases if case["id"] in allowed]
    if not cases:
        raise ValueError("No eval cases selected.")

    results = [run_eval_case(case) for case in cases]
    passed = sum(1 for result in results if result["passed"])
    pass_rate = passed / len(results)
    summary = {
        "passed": passed,
        "total": len(results),
        "pass_rate": pass_rate,
        "results": results,
    }

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(f"Agent eval pass rate: {passed}/{len(results)} ({pass_rate:.0%})")
        for result in results:
            print_result(result, args.verbose)

    return 0 if pass_rate >= args.fail_under else 1


if __name__ == "__main__":
    sys.exit(main())
