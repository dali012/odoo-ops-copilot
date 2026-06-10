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
from .tools import _get_engine, forecast_demand

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
    category = str(row["category"])
    revenue = float(row["revenue"])
    normalized = normalize(response)
    passed = category.casefold() in normalized and contains_number_near(response, revenue, tolerance=5.0)
    return Grade(
        passed=passed,
        expected=f"{category} with ${revenue:,.0f} revenue",
        details=[f"answer numbers={extract_numbers(response)}"],
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


GRADERS: dict[str, Callable[[str], Grade]] = {
    "active_product_count": grade_active_product_count,
    "outerwear_forecast_next_month": grade_outerwear_forecast_next_month,
    "top_category_units_90d": grade_top_category_units_90d,
    "slowest_products_90d": grade_slowest_products_90d,
    "top_revenue_category_90d": grade_top_revenue_category_90d,
    "schema_sales_by_category": grade_schema_sales_by_category,
    "schema_units_revenue_fields": grade_schema_units_revenue_fields,
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
