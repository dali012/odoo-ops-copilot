# backend/app/seed/__init__.py
"""Seed package orchestrator.

Usage:
    python -m app.seed                    # all phases in dependency order
    python -m app.seed --phase catalog    # one phase only

Phase dependency order:
    catalog -> sales -> purchase -> invoicing -> pos -> marketing

catalog must always run (or have run previously) before any phase that
needs product_ids or customer_ids.
"""
from __future__ import annotations

import argparse
import random
import sys

from .catalog import seed_catalog
from .invoicing import seed_invoicing
from .marketing import seed_marketing
from .pos import seed_pos
from .purchase import seed_purchase
from .sales import seed_sales
from .stock_levels import seed_stockout_signal

# stockout runs last: it zeroes one product's on-hand stock, and must do so
# after every phase that creates or consumes inventory (purchase, pos).
PHASE_ORDER = ["catalog", "sales", "purchase", "invoicing", "pos", "marketing", "stockout"]
# Phases that need catalog output (product_ids, customer_ids)
_CATALOG_CONSUMERS = {"sales", "purchase", "pos"}


def seed(phase: str | None = None) -> None:
    random.seed(42)

    if phase and phase not in PHASE_ORDER:
        print(f"Unknown phase '{phase}'. Valid: {', '.join(PHASE_ORDER)}", file=sys.stderr)
        sys.exit(1)

    phases = [phase] if phase else PHASE_ORDER

    # catalog always runs first if any downstream phase needs it
    catalog_result = None
    needs_catalog = phase is None or phase == "catalog" or phase in _CATALOG_CONSUMERS
    if needs_catalog:
        print("[seed] Running phase: catalog")
        catalog_result = seed_catalog()

    if "sales" in phases and catalog_result:
        print("[seed] Running phase: sales")
        seed_sales(catalog_result["product_ids"], catalog_result["customer_ids"])

    if "purchase" in phases and catalog_result:
        print("[seed] Running phase: purchase")
        seed_purchase(catalog_result["product_ids"])

    if "invoicing" in phases:
        print("[seed] Running phase: invoicing")
        seed_invoicing()

    if "pos" in phases and catalog_result:
        print("[seed] Running phase: pos")
        seed_pos(catalog_result["product_ids"], catalog_result["customer_ids"])

    if "marketing" in phases:
        print("[seed] Running phase: marketing")
        seed_marketing()

    if "stockout" in phases:
        print("[seed] Running phase: stockout")
        seed_stockout_signal()

    print("[seed] Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Odoo with realistic retail data.")
    parser.add_argument("--phase", choices=PHASE_ORDER, help="Run only this phase.")
    args = parser.parse_args()
    seed(args.phase)
