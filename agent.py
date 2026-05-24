"""
agent.py — GroceryAgent orchestrates item resolution.

This is the "agent" logic: given an item name, it consults order history
to find the user's preferred brand, then fetches alternatives from the
product database.
"""

from models import OrderHistory, ProductDatabase, GroceryItem
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate


class GroceryAgent:
    """
    Resolves grocery item names into brand-specific products
    based on the user's order history.
    """

    def __init__(self):
        self.order_history = OrderHistory()
        self.product_db = ProductDatabase()
        self.llm = ChatGoogleGenerativeAI(model="ggemini-2.5-flash-lite", temperature=0)
        
    AUTO_ADD_THRESHOLD = 3  # Orders needed to auto-populate basket

    def resolve_item(self, item_name: str) -> dict:
        """
        Given a generic item name (e.g. 'butter'), returns:
        - suggested: user's historically preferred brand
        - alternatives: all other available products
        - order_count: how many times they've ordered the suggestion
        - auto_add: True if order_count >= AUTO_ADD_THRESHOLD
        """
        item_name = item_name.lower().strip()

        # If the name provided is actually a brand, map it to the item category
        if item_name not in self.product_db.products:
            for key, products in self.product_db.products.items():
                for p in products:
                    if item_name == p['brand'].lower():
                        item_name = key
                        break

        suggested = self.order_history.get_most_ordered_brand(item_name)
        alternatives = self.product_db.get_alternatives(item_name)
        order_count = 0
        last_ordered = None

        if suggested:
            order_count = self.order_history.get_order_count(
                item_name, suggested.brand
            )
            last_ordered = self.order_history.get_last_ordered_date(item_name, suggested.brand)
            alternatives = [p for p in alternatives if p.brand != suggested.brand]

        auto_add = suggested is not None and order_count >= self.AUTO_ADD_THRESHOLD

        return {
            "item": item_name,
            "suggested": suggested.to_dict() if suggested else None,
            "alternatives": [p.to_dict() for p in alternatives],
            "order_count": order_count,
            "auto_add": auto_add,
            "last_ordered": last_ordered
        }

    def resolve_list(self, items: list) -> list:
        """Resolve a list of item names at once (used after OCR)."""
        results = []
        for item in items:
            if item.strip():
                results.append(self.resolve_item(item))
        return results

    def search_items(self, query: str) -> list:
        """Uses an LLM to identify the actual items being requested."""
        query_clean = query.lower().strip()

        # Optimization: Bypass LLM for simple queries (1-2 words) that match our local DB
        if len(query_clean.split()) <= 2:
            matches = self.product_db.search(query_clean)
            # Filter for valid category keys in our database
            valid_keys = [m for m in matches if m.lower() in self.product_db.products]
            if valid_keys:
                return valid_keys

        prompt = ChatPromptTemplate.from_template(
            "The user said: '{query}'. Extract the core grocery items or brands they want to find. "
            "Return ONLY the item names separated by commas. If no items are found, return 'None'."
        )
        
        chain = prompt | self.llm
        response = chain.invoke({"query": query})
        
        if "none" in response.content.lower():
            return []
            
        extracted_items = [i.strip() for i in response.content.split(",")]
        
        # Search for all extracted items and flatten the results
        all_matches = []
        for item in extracted_items:
            matches = self.product_db.search(item)
            # Keep only valid item keys (categories) for resolution logic
            valid_keys = [m for m in matches if m.lower() in self.product_db.products]
            all_matches.extend(valid_keys)
        return list(dict.fromkeys(all_matches))

    def get_recommendations(self):
        """Get items predicted by the history engine."""
        return [s.to_dict() for s in self.order_history.get_proactive_suggestions()]
