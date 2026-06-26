"""Holdout backtest for the demand-forecast model.

Proves the forecasting is real, not decorative: for each product category with
enough history, fit the same seasonal exponential-smoothing model used by
``forecast_demand`` on all-but-the-last-N months, forecast those N months, and
compare against what actually happened. Reports MAPE and RMSE.

Run from backend/ (needs the seeded Postgres):
    python -m app.backtest_forecast                 # all categories, 6-month holdout
    python -m app.backtest_forecast --holdout 3     # 3-month holdout
    python -m app.backtest_forecast --json          # machine-readable
    python -m app.backtest_forecast --max-mape 25   # exit 1 if pooled MAPE > 25%

The ``mape``/``rmse`` helpers are pure and unit-tested in test_backtest_forecast.py.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Sequence

import pandas as pd
import statsmodels.api as sm
from sqlalchemy import text

from .tools import SQL_TIMEOUT_MS, _get_engine

# A full seasonal cycle is 12 months; the model needs >= 2 cycles to train.
MIN_TRAIN_MONTHS = 24
DEFAULT_HOLDOUT_MONTHS = 6


def mape(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Mean Absolute Percentage Error (%), skipping zero-actual points.

    Returns NaN when every actual value is zero (MAPE is undefined there).
    """
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length.")
    errors = [
        abs(a - p) / abs(a)
        for a, p in zip(actual, predicted)
        if a != 0
    ]
    if not errors:
        return float("nan")
    return sum(errors) / len(errors) * 100.0


def rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Root Mean Squared Error in the series' own units."""
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length.")
    if not actual:
        raise ValueError("cannot compute RMSE over an empty series.")
    squared = [(a - p) ** 2 for a, p in zip(actual, predicted)]
    return math.sqrt(sum(squared) / len(squared))


def _monthly_series(category: str) -> pd.Series:
    """Monthly units sold for a category, as a gap-filled month-start series."""
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
    if df.empty:
        return pd.Series(dtype=float)
    return df.set_index("month")["units"].astype(float).asfreq("MS").fillna(0)


def _categories_with_sales() -> list[str]:
    sql = text("""
        SELECT DISTINCT pc.name AS category
        FROM sale_order_line sol
        JOIN sale_order so       ON so.id = sol.order_id
        JOIN product_product pp  ON pp.id = sol.product_id
        JOIN product_template pt ON pt.id = pp.product_tmpl_id
        JOIN product_category pc ON pc.id = pt.categ_id
        WHERE so.state IN ('sale', 'done')
        ORDER BY pc.name
    """)
    with _get_engine().connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [str(row["category"]) for row in rows]


def backtest_category(category: str, holdout_months: int = DEFAULT_HOLDOUT_MONTHS) -> dict:
    """Fit on all-but-last-N months, forecast N, score against actuals."""
    series = _monthly_series(category)
    needed = MIN_TRAIN_MONTHS + holdout_months
    if len(series) < needed:
        return {
            "category": category,
            "skipped": True,
            "reason": f"need >= {needed} months of history, have {len(series)}",
        }

    train = series.iloc[:-holdout_months]
    test = series.iloc[-holdout_months:]
    model = sm.tsa.ExponentialSmoothing(
        train, trend="add", seasonal="add", seasonal_periods=12
    ).fit()
    forecast = model.forecast(holdout_months)

    actual = [float(v) for v in test.values]
    predicted = [float(v) for v in forecast.values]
    return {
        "category": category,
        "skipped": False,
        "holdout_months": holdout_months,
        "mape_pct": round(mape(actual, predicted), 2),
        "rmse": round(rmse(actual, predicted), 2),
        "actual": [round(v, 1) for v in actual],
        "predicted": [round(v, 1) for v in predicted],
    }


def backtest_all(holdout_months: int = DEFAULT_HOLDOUT_MONTHS) -> dict:
    """Backtest every eligible category and pool the errors for an overall score."""
    per_category = [backtest_category(c, holdout_months) for c in _categories_with_sales()]
    scored = [r for r in per_category if not r.get("skipped")]

    pooled_actual: list[float] = []
    pooled_predicted: list[float] = []
    for result in scored:
        pooled_actual.extend(result["actual"])
        pooled_predicted.extend(result["predicted"])

    overall = {
        "categories_scored": len(scored),
        "categories_skipped": len(per_category) - len(scored),
        "holdout_months": holdout_months,
    }
    if pooled_actual:
        overall["mape_pct"] = round(mape(pooled_actual, pooled_predicted), 2)
        overall["rmse"] = round(rmse(pooled_actual, pooled_predicted), 2)

    return {"overall": overall, "per_category": per_category}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Holdout backtest for forecast_demand.")
    parser.add_argument("--holdout", type=int, default=DEFAULT_HOLDOUT_MONTHS,
                        help="Number of trailing months to hold out and predict.")
    parser.add_argument("--category", help="Backtest only this category.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--max-mape", type=float,
                        help="Exit 1 if pooled MAPE exceeds this percentage.")
    args = parser.parse_args()

    if args.category:
        report = {"overall": {}, "per_category": [backtest_category(args.category, args.holdout)]}
        scored = [r for r in report["per_category"] if not r.get("skipped")]
        if scored:
            report["overall"] = {
                "categories_scored": len(scored),
                "holdout_months": args.holdout,
                "mape_pct": scored[0]["mape_pct"],
                "rmse": scored[0]["rmse"],
            }
    else:
        report = backtest_all(args.holdout)

    overall = report["overall"]
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"Forecast backtest ({args.holdout}-month holdout)")
        for result in report["per_category"]:
            if result.get("skipped"):
                print(f"  [skip] {result['category']}: {result['reason']}")
            else:
                print(f"  {result['category']}: MAPE {result['mape_pct']}%  RMSE {result['rmse']}")
        if "mape_pct" in overall:
            print(f"\nOverall (pooled over {overall['categories_scored']} categories): "
                  f"MAPE {overall['mape_pct']}%  RMSE {overall['rmse']}")

    if args.max_mape is not None and overall.get("mape_pct") is not None:
        return 0 if overall["mape_pct"] <= args.max_mape else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
