# Grocery Agent

Grocery Agent is a smart shopping assistant designed to streamline the grocery ordering process. It leverages Google's Gemini 1.5 Flash model for multimodal OCR (extracting items from handwritten lists) and provides personalized recommendations based on past purchase frequency.

## Features

-   **OCR List Processing:** Upload images of handwritten or printed grocery lists. The agent uses Gemini 1.5 Flash to transcribe items accurately.
-   **Natural Language Search:** Supports complex queries like "milk, eggs, and bread" to quickly resolve multiple items at once.
-   **Order History & Predictive Suggestions:** Analyzes your past shopping habits to predict when you might run out of essentials and suggests restocking them.
-   **Brand Preference Tracking:** Automatically suggests your most-ordered brand for any given item.
-   **Basket Management:** Full CRUD operations for a shopping basket, persisted via JSON for local storage.
-   **Product Database:** A searchable catalogue of available products with fuzzy matching support.

## Tech Stack

-   **Backend:** Python, Flask
-   **AI/LLM:** LangChain, Google Generative AI (Gemini 1.5 Flash)
-   **Image Processing:** Pillow (PIL)
-   **Data Persistence:** JSON-based local storage

## Project Structure

-   `app.py`: The Flask web application containing the routing logic and API endpoints.
-   `models.py`: Core data classes (`GroceryItem`, `Product`) and managers for `OrderHistory`, `ProductDatabase`, and `Basket`.
-   `ocr_processor.py`: Handles image optimization and integration with Gemini for OCR transcription.
-   `agent.py`: (Implicit) Orchestrates the logic between search, resolution, and history.
-   `data/`: Directory containing JSON files for products, order history, and the current basket.
-   `uploads/`: Temporary storage for uploaded images.

## Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd GroceryAgent
    ```

2.  **Create a virtual environment and install dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install flask python-dotenv langchain-google-genai pillow
    ```

3.  **Configure Environment Variables:**
    Create a `.env` file in the root directory and add your Google API Key:
    ```env
    GOOGLE_API_KEY=your_gemini_api_key_here
    ```

4.  **Prepare Data:**
    Ensure `data/products.json` and `data/order_history.json` exist with valid data to enable searching and recommendations.

5.  **Run the application:**
    ```bash
    python app.py
    ```
    The app will be available at `http://127.0.0.1:5000`.

## Usage

-   **Search:** Use the search bar to find items or enter a comma-separated list.
-   **Upload:** Use the upload feature to process a photo of a physical grocery list.
-   **Recommendations:** Check the recommendations section for proactive restock suggestions.
-   **Basket:** Manage quantities and items in your basket before "checking out."
