"""
models.py — Core data classes for the Grocery Agent.
Advanced concepts: Classes & Objects, File I/O
"""

from dataclasses import dataclass, field
import difflib
import json
import os
from collections import Counter
from datetime import datetime


@dataclass
class GroceryItem:
    """Represents a single grocery item with brand and quantity."""
    name: str
    brand: str
    quantity: int = 1
    unit: str = ""
    price: float = 0.0

    def to_dict(self):
        # dataclasses.asdict(self) could also be used, but self.__dict__ is simpler for direct field access
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
    Loads and queries past order history from a JSON file.
    Used to determine a user's preferred brand for any item.
    """

    def __init__(self, filepath="data/order_history.json"):
        self.filepath = filepath
        self.orders = self._load()
        self._preprocessed_history = self._preprocess_history()

    def _load(self):
        """Load orders from JSON file — File I/O."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                return json.load(f)
        return []

    def _preprocess_history(self):
        """
        Pre-processes order history to store brand counts and item details efficiently.
        Structure: {item_name: {brand: {'count': int, 'item_details': GroceryItem}}}
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
                        'count': 0,
                        'item_details': GroceryItem.from_dict(item_data),
                        'last_ordered': order_date
                    }
                preprocessed[item_name_lower][brand]['count'] += 1
                # Update last_ordered if this order is more recent
                if order_date > preprocessed[item_name_lower][brand]['last_ordered']:
                    preprocessed[item_name_lower][brand]['last_ordered'] = order_date
        return preprocessed

    def get_most_ordered_brand(self, item_name):
        """Returns a GroceryItem representing the user's most-ordered brand."""
        item_name_lower = item_name.lower().strip()
        brand_data = self._preprocessed_history.get(item_name_lower)

        if not brand_data:
            return None
        
        # Find the brand with the highest count
        top_brand = max(brand_data, key=lambda brand: brand_data[brand]['count'])
        return brand_data[top_brand]['item_details']

    def get_last_ordered_date(self, item_name, brand):
        """Returns the date of the most recent purchase for this item/brand."""
        item_name_lower = item_name.lower().strip()
        brand_data = self._preprocessed_history.get(item_name_lower, {}).get(brand)
        if brand_data:
            return brand_data['last_ordered']
        return None

    def get_order_count(self, item_name, brand):
        """Returns how many past orders included a specific brand."""
        item_name_lower = item_name.lower().strip()
        brand_data = self._preprocessed_history.get(item_name_lower)
        if brand_data and brand in brand_data:
            return brand_data[brand]['count']
        return 0

    def get_proactive_suggestions(self, current_date_str="2025-03-30"):
        """
        Predicts items user might need based on purchase frequency.
        Logic: if (current_date - last_ordered) >= average_interval.
        """
        current_date = datetime.strptime(current_date_str, "%Y-%m-%d")
        suggestions = []
        
        # Track purchase dates for each unique item/brand combo
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
            intervals = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
            avg_interval = sum(intervals) / len(intervals)
            
            days_since_last = (current_date - dates[-1]).days
            
            # If we are at or past the average restock time
            if days_since_last >= avg_interval:
                item_details = self._preprocessed_history[name][brand]['item_details']
                suggestions.append(item_details)
                
        return suggestions


class ProductDatabase:
    """
    Loads the local product catalogue from a JSON file.
    Provides search and alternatives lookup.
    """

    def __init__(self, filepath="data/products.json"):
        self.filepath = filepath
        self.products = self._load()

    def _load(self):
        """Load product catalogue from JSON file — File I/O."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                return json.load(f)
        return {}

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

        # 1. Check item names (keys)
        for key in self.products:
            if q in key:
                matches.append(key)
        
        # 2. Check brands within those items
        for key, items in self.products.items():
            for item in items:
                brand = item['brand']
                if q in brand.lower():
                    matches.append(brand)
                    matches.append(key)

        if not matches:
            # Fuzzy matching fallback
            matches = difflib.get_close_matches(q, self.products.keys(), n=3, cutoff=0.6)
        
        # Deduplicate while preserving order
        return list(dict.fromkeys(matches))


class Basket:
    """
    The user's current shopping basket.
    Persists to disk after every change.
    """

    def __init__(self, filepath="data/basket.json"):
        self.filepath = filepath
        self.items = self._load()

    def _load(self):
        """Load basket from JSON file — File I/O."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                return [GroceryItem.from_dict(i) for i in json.load(f)]
        return []

    def _save(self):
        """Persist basket to JSON file — File I/O."""
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump([i.to_dict() for i in self.items], f, indent=2)

    def add_item(self, item: GroceryItem):
        """Add item to basket; increment quantity if already present."""
        for existing in self.items:
            if (
                existing.name.lower() == item.name.lower()
                and existing.brand == item.brand
            ):
                existing.quantity += item.quantity
                self._save()
                return
        self.items.append(item)
        self._save()

    def update_quantity(self, item_name, brand, delta):
        """Adjust the quantity of an item in the basket."""
        for i, existing in enumerate(self.items):
            if (
                existing.name.lower() == item_name.lower()
                and existing.brand == brand
            ):
                existing.quantity += delta
                if existing.quantity <= 0:
                    self.items.pop(i)
                self._save()
                return True
        # If item not found and delta is positive, we could potentially add it, 
        # but for this UI it's safer to just return False.
        return False

    def remove_item(self, item_name, brand):
        """Remove an item from basket by name and brand."""
        self.items = [
            i
            for i in self.items
            if not (i.name.lower() == item_name.lower() and i.brand == brand)
        ]
        self._save()

    def clear(self):
        """Empty the basket."""
        self.items = []
        self._save()

    def get_total(self):
        """Return total price of all items in basket."""
        return round(sum(i.price * i.quantity for i in self.items), 2)

    def to_list(self):
        return [i.to_dict() for i in self.items]
