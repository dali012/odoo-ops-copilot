# backend/app/seed/marketing.py
"""Seed draft email marketing campaigns."""
from __future__ import annotations

from ._base import SEED_PREFIX
from ..odoo_client import odoo

CAMPAIGNS = [
    {
        "category": "Outerwear",
        "subject": "[Outerwear] - New arrivals this season",
        "body_html": (
            "<p>Stay warm this season with our premium outerwear collection. "
            "Our bestselling <b>Wool Coat</b> is back in stock in new colours. "
            "Order yours today.</p>"
        ),
    },
    {
        "category": "Footwear",
        "subject": "[Footwear] - New arrivals this season",
        "body_html": (
            "<p>Step into style with our latest footwear arrivals. "
            "Our iconic <b>Leather Boots</b> are the season's must-have. "
            "Limited quantities available.</p>"
        ),
    },
    {
        "category": "Accessories",
        "subject": "[Accessories] - New arrivals this season",
        "body_html": (
            "<p>Complete your look with our new accessories range. "
            "From belts to scarves, including our cosy <b>Wool Scarf</b>. "
            "Perfect gifts for every occasion.</p>"
        ),
    },
    {
        "category": "Knitwear",
        "subject": "[Knitwear] - New arrivals this season",
        "body_html": (
            "<p>Elevate your wardrobe with our luxury knitwear collection. "
            "Our <b>Cashmere Sweater</b> is the definition of comfort and style. "
            "Explore the full range now.</p>"
        ),
    },
]


def seed_marketing() -> tuple[int, int]:
    """Create 4 draft email campaigns, one per product category.

    Returns:
        (created_count, skipped_count)
    """
    model_ids = odoo.execute("ir.model", "search", [["model", "=", "res.partner"]], limit=1)
    if not model_ids:
        print("  [marketing] ir.model for res.partner not found; skipping.")
        return 0, 0
    model_id = int(model_ids[0])

    all_customers_domain = str([["customer_rank", ">", 0]])
    created_count = 0
    skipped_count = 0

    for campaign in CAMPAIGNS:
        name_ref = f"{SEED_PREFIX}:campaign:{campaign['category'].lower()}"
        existing = odoo.execute("mailing.mailing", "search", [["name", "=", name_ref]], limit=1)
        if existing:
            skipped_count += 1
            continue

        odoo.execute("mailing.mailing", "create", {
            "name": name_ref,
            "subject": campaign["subject"],
            "body_html": campaign["body_html"],
            "mailing_model_id": model_id,
            "mailing_domain": all_customers_domain,
            "state": "draft",
        })
        created_count += 1

    print(f"  [marketing] Created {created_count} campaigns, skipped {skipped_count} existing.")
    return created_count, skipped_count
