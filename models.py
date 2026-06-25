"""
models.py — Core data classes and data-access managers for the Grocery Agent.

Persistence is backed by PostgreSQL via SQLAlchemy (see db.py). The public
interfaces (GroceryItem, Product, OrderHistory, ProductDatabase, Basket) are
kept identical to the previous JSON-backed implementation so the rest of the
app (app.py, agent.py) is unaffected.
"""

from dataclasses import dataclass
import difflib
from datetime import datetime

from sqlalchemy import func

from db import (
    SessionLocal,
    ProductRow,
    OrderRow,
    OrderItemRow,
    BasketItemRow,
)


@dataclass
class GroceryItem:
    """Represents a single grocery item with brand and quantity."""
    name: str
    brand: str
    quantity: int = 1
    unit: str = ""
    price: float = 0.0

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__annotations__.keys()}

    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data["name"],
            brand=data["brand"],
            quantity=data.get("quantity", cls.quantity),
            unit=data.get("unit", cls.unit),
            price=data.get("price", cls.price),
        )


@dataclass
class Product:
    """Represents an available product in the product database."""
    name: str
    brand: str
    unit: str
    price: float
    category: str = ""

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__annotations__.keys()}


class OrderHistory:
    """
    Loads and queries past order history from PostgreSQL.
    Used to determine a user's preferred brand for any item.
    """

    def __init__(self):
        self.orders = self._load()
        self._preprocessed_history = self._preprocess_history()

    def _load(self):
        """Load orders from the database into the legacy list-of-dicts shape."""
        with SessionLocal() as session:
            rows = session.query(OrderRow).order_by(OrderRow.date).all()
            orders = []
            for order in rows:
                orders.append(
                    {
                        "date": order.date.strftime("%Y-%m-%d"),
                        "items": [
                            {
                                "name": it.name,
                                "brand": it.brand,
                                "quantity": it.quantity,
                                "unit": it.unit,
                                "price": it.price,
                            }
                            for it in order.items
                        ],
                    }
                )
            return orders

    def _preprocess_history(self):
        """
        Pre-processes order history to store brand counts and item details.
        Structure: {item_name: {brand: {'count': int, 'item_details': GroceryItem, 'last_ordered': str}}}
        """
        preprocessed = {}
        for order in self.orders:
            for item_data in order.get("items", []):
                item_name_lower = item_data["name"].lower().strip()
                brand = item_data["brand"]

                if item_name_lower not in preprocessed:
                    preprocessed[item_name_lower] = {}

                order_date = order.get("date", "Unknown")
                if brand not in preprocessed[item_name_lower]:
                    preprocessed[item_name_lower][brand] = {
                        "count": 0,
                        "item_details": GroceryItem.from_dict(item_data),
                        "last_ordered": order_date,
                    }
                preprocessed[item_name_lower][brand]["count"] += 1
                if order_date > preprocessed[item_name_lower][brand]["last_ordered"]:
                    preprocessed[item_name_lower][brand]["last_ordered"] = order_date
        return preprocessed

    def get_most_ordered_brand(self, item_name):
        """Returns a GroceryItem representing the user's most-ordered brand."""
        item_name_lower = item_name.lower().strip()
        brand_data = self._preprocessed_history.get(item_name_lower)

        if not brand_data:
            return None

        top_brand = max(brand_data, key=lambda brand: brand_data[brand]["count"])
        return brand_data[top_brand]["item_details"]

    def get_last_ordered_date(self, item_name, brand):
        """Returns the date of the most recent purchase for this item/brand."""
        item_name_lower = item_name.lower().strip()
        brand_data = self._preprocessed_history.get(item_name_lower, {}).get(brand)
        if brand_data:
            return brand_data["last_ordered"]
        return None

    def get_order_count(self, item_name, brand):
        """Returns how many past orders included a specific brand."""
        item_name_lower = item_name.lower().strip()
        brand_data = self._preprocessed_history.get(item_name_lower)
        if brand_data and brand in brand_data:
            return brand_data[brand]["count"]
        return 0

    def get_proactive_suggestions(self, current_date_str="2025-03-30"):
        """
        Predicts items user might need based on purchase frequency.
        Logic: if (current_date - last_ordered) >= average_interval.
        """
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
        suggestions = []

        item_dates = {}
        for order in self.orders:
            date = datetime.strptime(order["date"], "%Y-%m-%d")
            for item in order.get("items", []):
                key = (item["name"].lower().strip(), item["brand"])
                if key not in item_dates:
                    item_dates[key] = []
                item_dates[key].append(date)

        for (name, brand), dates in item_dates.items():
            if len(dates) < 2:
                continue

            dates.sort()
            intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
            avg_interval = sum(intervals) / len(intervals)

            days_since_last = (current_date - dates[-1]).days

            if days_since_last >= avg_interval:
                item_details = self._preprocessed_history[name][brand]["item_details"]
                suggestions.append(item_details)

        return suggestions


class ProductDatabase:
    """
    Loads the product catalogue from PostgreSQL.
    Provides search and alternatives lookup.

    `self.products` retains the legacy shape: {item_name: [ {brand, unit, price, category}, ... ]}
    so that callers (e.g. agent.py) can keep iterating it directly.
    """

    def __init__(self):
        self.products = self._load()

    def _load(self):
        """Load product catalogue from the database into the legacy dict shape."""
        catalogue = {}
        with SessionLocal() as session:
            rows = session.query(ProductRow).order_by(ProductRow.id).all()
            for row in rows:
                catalogue.setdefault(row.name, []).append(
                    {
                        "brand": row.brand,
                        "unit": row.unit,
                        "price": row.price,
                        "category": row.category,
                    }
                )
        return catalogue

    def get_alternatives(self, item_name):
        """Returns all available products for a given item name."""
        key = item_name.lower().strip()
        entries = self.products.get(key, [])
        return [
            Product(key, p["brand"], p["unit"], p["price"], p.get("category", ""))
            for p in entries
        ]

    def search(self, query):
        """Returns item names and brand names that partially match the query."""
        q = query.lower().strip()
        matches = []

        for key in self.products:
            if q in key:
                matches.append(key)

        for key, items in self.products.items():
            for item in items:
                brand = item["brand"]
                if q in brand.lower():
                    matches.append(brand)
                    matches.append(key)

        if not matches:
            matches = difflib.get_close_matches(q, self.products.keys(), n=3, cutoff=0.6)

        return list(dict.fromkeys(matches))


class Basket:
    """
    The user's current shopping basket, persisted in PostgreSQL.
    """

    def __init__(self):
        # No in-memory caching: every operation reads/writes the database so
        # state stays consistent across requests and processes.
        pass

    def _all_rows(self, session):
        return session.query(BasketItemRow).order_by(BasketItemRow.id).all()

    def add_item(self, item: GroceryItem):
        """Add item to basket; increment quantity if already present."""
        with SessionLocal() as session:
            existing = (
                session.query(BasketItemRow)
                .filter(func.lower(BasketItemRow.name) == item.name.lower())
                .filter(BasketItemRow.brand == item.brand)
                .first()
            )
            if existing:
                existing.quantity += item.quantity
            else:
                session.add(
                    BasketItemRow(
                        name=item.name,
                        brand=item.brand,
                        quantity=item.quantity,
                        unit=item.unit,
                        price=item.price,
                    )
                )
            session.commit()

    def update_quantity(self, item_name, brand, delta):
        """Adjust the quantity of an item in the basket."""
        with SessionLocal() as session:
            existing = (
                session.query(BasketItemRow)
                .filter(func.lower(BasketItemRow.name) == item_name.lower())
                .filter(BasketItemRow.brand == brand)
                .first()
            )
            if not existing:
                return False
            existing.quantity += delta
            if existing.quantity <= 0:
                session.delete(existing)
            session.commit()
            return True

    def remove_item(self, item_name, brand):
        """Remove an item from basket by name and brand."""
        with SessionLocal() as session:
            (
                session.query(BasketItemRow)
                .filter(func.lower(BasketItemRow.name) == item_name.lower())
                .filter(BasketItemRow.brand == brand)
                .delete(synchronize_session=False)
            )
            session.commit()

    def clear(self):
        """Empty the basket."""
        with SessionLocal() as session:
            session.query(BasketItemRow).delete(synchronize_session=False)
            session.commit()

    def get_total(self):
        """Return total price of all items in basket."""
        with SessionLocal() as session:
            rows = self._all_rows(session)
            return round(sum(r.price * r.quantity for r in rows), 2)

    def to_list(self):
        with SessionLocal() as session:
            rows = self._all_rows(session)
            return [
                {
                    "name": r.name,
                    "brand": r.brand,
                    "quantity": r.quantity,
                    "unit": r.unit,
                    "price": r.price,
                }
                for r in rows
            ]
