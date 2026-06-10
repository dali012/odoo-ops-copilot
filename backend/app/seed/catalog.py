# backend/app/seed/catalog.py
"""Seed product categories, products, and customers."""
from __future__ import annotations

from typing import Any

from ._base import get_or_create
from ..odoo_client import odoo

CATEGORIES = ["Outerwear", "Footwear", "Accessories", "Knitwear"]

PRODUCTS: dict[str, list[tuple[str, float]]] = {
    "Outerwear": [("Wool Coat", 180.0), ("Rain Jacket", 95.0), ("Padded Parka", 220.0)],
    "Footwear": [("Leather Boots", 140.0), ("Canvas Sneakers", 60.0), ("Suede Loafers", 110.0)],
    "Accessories": [("Leather Belt", 35.0), ("Wool Scarf", 28.0), ("Cap", 18.0)],
    "Knitwear": [("Cashmere Sweater", 130.0), ("Cotton Cardigan", 70.0), ("Merino Beanie", 25.0)],
}

CUSTOMERS = [
    {"name": "Aurora Retail",  "street": "14 Nord Street",       "city": "Oslo",      "phone": "+47 21 00 01 01"},
    {"name": "Borgo Shop",     "street": "Via Roma 22",           "city": "Milan",     "phone": "+39 02 1234 5678"},
    {"name": "Cala Boutique",  "street": "Carrer del Mar 5",      "city": "Barcelona", "phone": "+34 93 456 78 90"},
    {"name": "Dune Store",     "street": "12 Rue du Commerce",    "city": "Paris",     "phone": "+33 1 23 45 67 89"},
]


def seed_catalog() -> dict[str, Any]:
    """Create categories, storable products, customers.

    Returns:
        {
            "cat_ids":      {cat_name: product.category id},
            "product_ids":  {cat_name: [product.product id, ...]},
            "customer_ids": [res.partner id, ...],
        }
    """
    print("  [catalog] Seeding categories and products...")
    cat_ids: dict[str, int] = {}
    product_ids: dict[str, list[int]] = {}

    for cat in CATEGORIES:
        cat_ids[cat] = get_or_create(
            "product.category", [["name", "=", cat]], {"name": cat}
        )
        product_ids[cat] = []
        for name, price in PRODUCTS[cat]:
            tmpl_id = get_or_create(
                "product.template",
                [["name", "=", name]],
                {
                    "name": name,
                    "list_price": price,
                    "standard_price": round(price * 0.45, 2),
                    "categ_id": cat_ids[cat],
                    "sale_ok": True,
                    "purchase_ok": True,
                    "type": "product",  # storable - required for stock moves
                },
            )
            pp_ids = odoo.execute(
                "product.product", "search", [["product_tmpl_id", "=", tmpl_id]]
            )
            if pp_ids:
                product_ids[cat].append(int(pp_ids[0]))

    print("  [catalog] Seeding customers...")
    customer_ids: list[int] = []
    for c in CUSTOMERS:
        cid = get_or_create(
            "res.partner",
            [["name", "=", c["name"]]],
            {
                "name": c["name"],
                "customer_rank": 1,
                "street": c["street"],
                "city": c["city"],
                "phone": c["phone"],
            },
        )
        existing = odoo.search_read("res.partner", [["id", "=", cid]], ["street"])[0]
        if not existing.get("street"):
            odoo.execute("res.partner", "write", [cid], {
                "street": c["street"],
                "city": c["city"],
                "phone": c["phone"],
            })
        customer_ids.append(cid)

    print(
        f"  [catalog] {sum(len(v) for v in product_ids.values())} products across "
        f"{len(CATEGORIES)} categories, {len(customer_ids)} customers."
    )
    return {"cat_ids": cat_ids, "product_ids": product_ids, "customer_ids": customer_ids}
