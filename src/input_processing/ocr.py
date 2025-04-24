import logging
import os
from pathlib import Path
import pytesseract
from PIL import Image
from pdf2image import convert_from_path

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Configure Tesseract path
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    logger.error(f"Tesseract not found at: {TESSERACT_PATH}")
    raise FileNotFoundError(f"Tesseract not found at: {TESSERACT_PATH}")


def extract_text_from_image(file_path: str) -> str:
    """Extract text from an image or PDF file using Tesseract OCR."""
    try:
        file_ext = Path(file_path).suffix.lower()
        images = []

        if file_ext == ".pdf":
            # Convert PDF to images
            images = convert_from_path(file_path)
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp"]:
            # Open single image
            images = [Image.open(file_path)]
        else:
            logger.error(f"Unsupported file format: {file_ext}")
            return ""

        # Extract text from each image
        extracted_text = []
        for img in images:
            text = pytesseract.image_to_string(img, lang="eng+mal+hin+tam+tel+ben+kan")
            extracted_text.append(text.strip())
            img.close()

        # Combine text from all pages
        result = "\n".join(extracted_text)
        if not result:
            logger.warning(f"No text extracted from {file_path}")
            return ""

        logger.info(f"Extracted text from {file_path}: {result[:100]}...")
        return result

    except Exception as e:
        logger.error(f"OCR error for {file_path}: {str(e)}")
        return ""