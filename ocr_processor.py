"""
ocr_processor.py — Extracts grocery item names from uploaded images.

Uses pytesseract (Tesseract OCR) to read text from images.
Works best with printed or clearly handwritten lists.
"""

import os
import base64
import io
from PIL import Image
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

class OCRProcessor:
    """Handles image-to-text extraction for grocery lists."""

    def __init__(self):
        # Initialize the LLM for structured extraction
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)

    def extract_items(self, image_path: str) -> list:
        """
        Opens an image file and extracts a list of grocery item names.
        Returns a list of clean item name strings.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Optimize image: Resize to max 1024px to save API tokens and quota
        img = Image.open(image_path)
        img.thumbnail((1024, 1024))
        
        buffered = io.BytesIO()
        # Convert to RGB if necessary (e.g. for PNGs with alpha) and save as JPEG
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(buffered, format="JPEG", quality=85)
        image_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # Use multimodal message to process the image directly
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": "Transcribe the grocery items from this handwritten list. Ignore numbers. Return ONLY a comma-separated list of items (e.g. milk, eggs, bread).",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                },
            ]
        )

        response = self.llm.invoke([message])
        content = response.content.lower().strip()

        if not content or "none" in content:
            return []

        return [i.strip() for i in content.split(",") if i.strip()]

if __name__ == "__main__":
    # Direct execution for testing with the specific image
    processor = OCRProcessor()
    print(f"Extracted Items: {processor.extract_items('/Users/akshatmathur/Downloads/grocery_agent 2/IMG_0424.jpg')}")
