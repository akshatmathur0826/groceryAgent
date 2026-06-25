"""
seed_db.py — Initialise the PostgreSQL schema and seed it from the JSON files.

Idempotent: tables are created if missing, and reference data (products and
order history) is only inserted when the corresponding tables are empty, so
re-running will not duplicate rows. The basket is left untouched (it is runtime
state, not seed data).
"""

import json
import os
from datetime import datetime

from db import (
    engine,
    init_db,
    wait_for_db,
    SessionLocal,
    ProductRow,
    OrderRow,
    OrderItemRow,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_json(filename, default):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def seed_products(session):
    if session.query(ProductRow).count() > 0:
        print("products table already populated; skipping product seed")
        return
    products = _load_json("products.json", {})
    count = 0
    for name, entries in products.items():
        for p in entries:
            session.add(
                ProductRow(
                    name=name,
                    brand=p["brand"],
                    unit=p.get("unit", ""),
                    price=p.get("price", 0.0),
                    category=p.get("category", ""),
                )
            )
            count += 1
    session.commit()
    print(f"seeded {count} products")


def seed_orders(session):
    if session.query(OrderRow).count() > 0:
        print("orders table already populated; skipping order seed")
        return
    orders = _load_json("order_history.json", [])
    count = 0
    for order in orders:
        order_row = OrderRow(date=datetime.strptime(order["date"], "%Y-%m-%d").date())
        for item in order.get("items", []):
            order_row.items.append(
                OrderItemRow(
                    name=item["name"],
                    brand=item["brand"],
                    quantity=item.get("quantity", 1),
                    unit=item.get("unit", ""),
                    price=item.get("price", 0.0),
                )
            )
        session.add(order_row)
        count += 1
    session.commit()
    print(f"seeded {count} orders")


def main():
    wait_for_db()
    init_db()
    with SessionLocal() as session:
        seed_products(session)
        seed_orders(session)
    print("database ready")


if __name__ == "__main__":
    main()
