"""
app.py — Flask web application for the Grocery Agent.
"""

import os
import re
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from models import Basket, GroceryItem
from agent import GroceryAgent
from ocr_processor import OCRProcessor

load_dotenv()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

os.makedirs("uploads", exist_ok=True)
os.makedirs("data", exist_ok=True)

agent = GroceryAgent()
basket = Basket()
ocr = OCRProcessor()

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html", basket=basket.to_list(), total=basket.get_total())


@app.route("/search", methods=["POST"])
def search():
    """Search for items matching a query string."""
    data = request.get_json()
    raw_query = data.get("query", "").strip()
    if not raw_query:
        return jsonify({"error": "No query provided"}), 400

    # Natural Language: Handle "milk, eggs, and bread" (Point 4)
    multi_match = re.split(r',| and ', raw_query.lower())
    multi_match = [m.strip() for m in multi_match if m.strip()]
    
    if len(multi_match) > 1:
        results = agent.resolve_list(multi_match)
        return jsonify({"type": "multi_resolve", "results": results})

    # Single item logic
    query = multi_match[0]
    matches = agent.search_items(query)

    if len(matches) == 1:
        result = agent.resolve_item(matches[0])
        
        # Auto-add logic: Use historical preference if available, else first alternative
        item_to_add = None
        if result["suggested"]:
            item_to_add = GroceryItem.from_dict(result["suggested"])
        elif result["alternatives"]:
            # Default to quantity 1 for brand new items
            alt = result["alternatives"][0]
            item_to_add = GroceryItem(
                name=result["item"], brand=alt["brand"], price=alt["price"], unit=alt["unit"], quantity=1
            )

        if item_to_add:
            basket.add_item(item_to_add)
            return jsonify({
                "type": "resolved", "result": result, 
                "basket": basket.to_list(), "total": basket.get_total()
            })
        return jsonify({"type": "resolved", "result": result})
    elif len(matches) > 1:
        return jsonify({"type": "multiple", "matches": matches})
    else:
        return jsonify({"type": "not_found", "query": query})


@app.route("/resolve", methods=["POST"])
def resolve():
    """Resolve a specific item name to brand suggestion + alternatives."""
    data = request.get_json()
    item_name = data.get("item", "").strip()
    if not item_name:
        return jsonify({"error": "No item provided"}), 400
    result = agent.resolve_item(item_name)
    return jsonify(result)


@app.route("/upload", methods=["POST"])
def upload():
    """Handle image upload, run OCR, and resolve all detected items."""
    # Hardcoded path for testing as per user request
    filepath = "/Users/akshatmathur/Downloads/grocery_agent 2/IMG_0424.jpg"

    try:
        items = ocr.extract_items(filepath)
    except Exception as e:
        return jsonify({"error": f"OCR failed: {str(e)}"}), 500

    if not items:
        return jsonify({
            "error": "No items detected.",
            "details": "Tesseract or LLM returned an empty list. Check server console for raw OCR output.",
            "path_checked": filepath
        }), 400

    results = agent.resolve_list(items)

    # Auto-add items the user orders regularly
    auto_added = []
    manual = []
    for result in results:
        if result["auto_add"] and result["suggested"]:
            item = GroceryItem(
                name=result["item"],
                brand=result["suggested"]["brand"],
                quantity=result["suggested"].get("quantity", 1),
                unit=result["suggested"].get("unit", ""),
                price=result["suggested"].get("price", 0.0),
            )
            basket.add_item(item)
            auto_added.append(result)
        else:
            manual.append(result)

    return jsonify({
        "auto_added": auto_added,
        "manual": manual,
        "basket": basket.to_list(),
        "total": basket.get_total(),
    })


@app.route("/recommendations", methods=["GET"])
def recommendations():
    """Fetch proactive shopping suggestions based on history."""
    suggestions = agent.get_recommendations()
    return jsonify(suggestions)


@app.route("/basket/add", methods=["POST"])
def add_to_basket():
    """Add a resolved item to the basket."""
    data = request.get_json()
    item = GroceryItem(
        name=data["name"],
        brand=data["brand"],
        quantity=data.get("quantity", 1),
        unit=data.get("unit", ""),
        price=data.get("price", 0.0),
    )
    basket.add_item(item)
    return jsonify({"basket": basket.to_list(), "total": basket.get_total()})

@app.route("/basket/update", methods=["POST"])
def update_basket_quantity():
    """Adjust quantity (+) or (-) for an item already in the basket."""
    data = request.get_json()
    name = data.get("name")
    brand = data.get("brand")
    delta = data.get("delta", 0)
    basket.update_quantity(name, brand, delta)
    return jsonify({"basket": basket.to_list(), "total": basket.get_total()})

@app.route("/basket/remove", methods=["POST"])
def remove_from_basket():
    """Remove an item from the basket."""
    data = request.get_json()
    basket.remove_item(data["name"], data["brand"])
    return jsonify({"basket": basket.to_list(), "total": basket.get_total()})


@app.route("/basket/clear", methods=["POST"])
def clear_basket():
    """Empty the basket."""
    basket.clear()
    return jsonify({"basket": [], "total": 0.0})

@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    """Provide search suggestions for the dropdown."""
    q = request.args.get("q", "").lower()
    if not q:
        return jsonify([])
    suggestions = agent.product_db.search(q)
    return jsonify(suggestions)

if __name__ == "__main__":
    app.run(debug=True)
