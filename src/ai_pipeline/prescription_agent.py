import logging
import sys
import os
from dotenv import load_dotenv
from google.generativeai import GenerativeModel
from src.database.mongodb import MongoDB
from src.utils.helpers import validate_translation, LANGUAGE_MAP
from src.input_processing.translation import translate_text

load_dotenv()

class UnicodeSafeStreamHandler(logging.StreamHandler):
    def __init__(self):
        super().__init__(stream=sys.stdout)
        if sys.stdout.encoding.lower() != "utf-8":
            self.stream = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        UnicodeSafeStreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    logger.info(f"Loaded GEMINI_API_KEY: {'Set' if gemini_api_key else 'Not set'}")
    if not gemini_api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")
    gemini_model = GenerativeModel("gemini-1.5-flash")
    logger.info("Gemini API initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Gemini API: {str(e)}")
    gemini_model = None

async def analyze_report(user_id: str, query: str) -> str:
    """
    Extract key information from a medical report using Gemini and provide simplified explanations.
    Args:
        user_id: User identifier
        query: Extracted text from report or prescription
    Returns:
        Translated response with extracted details and explanations
    """
    logger.info(f"Processing report for user {user_id}: {query}")
    mongodb = MongoDB()
    user_profile = mongodb.get_user(user_id)
    user_name = user_profile.get("name", "User")
    lang = user_profile.get("language", "en")

    if lang not in LANGUAGE_MAP:
        logger.warning(f"Invalid language {lang} for user {user_id}. Defaulting to English.")
        lang = "en"

    # Check for allergies
    allergies = user_profile.get("allergies", [])
    allergy_prompt = f"Note user allergies: {', '.join(allergies)}. Warn if medications may be contraindicated." if allergies else ""

    # Construct Gemini prompt for extraction and explanation
    prompt = (
        f"You are a health assistant helping {user_name}, an Indian user with limited medical knowledge. "
        f"The user provided a medical report: '{query}' in {LANGUAGE_MAP[lang]['name']} ({lang}). "
        f"{allergy_prompt} "
        "Extract the following in English, using simple terms:\n"
        "- Medications (e.g., Metformin, including dosage if mentioned).\n"
        "- Diagnoses or findings (e.g., pneumonia, hypertension).\n"
        "- Vitals or metrics (e.g., BP 140/90 mmHg, HbA1c 7%).\n"
        "For each medication, provide a short explanation of its purpose in plain language suitable for a local Indian user. "
        "Example: 'Metformin helps keep your blood sugar normal for diabetes.' "
        "Generate a concise response (under 150 words) in English, listing extracted details and explanations. "
        "If allergies are relevant, warn the user to consult a doctor. "
        "If no medications or details are found, say so. "
        "End with: 'Please consult your doctor for more details.' "
        "Do not diagnose or prescribe."
    )

    try:
        if not gemini_model:
            raise ValueError("Gemini API not initialized")
        response = gemini_model.generate_content(prompt)
        response_text = response.text.strip()
        logger.info(f"Gemini response for user {user_id}: {response_text[:100]}...")
    except Exception as e:
        logger.error(f"Gemini API error for user {user_id}: {str(e)}", exc_info=True)
        response_text = (
            f"Hello, {user_name}! I couldn't process your report '{query}'. "
            "Please share clear details (e.g., medicine names, test results) or upload a clearer document."
        )

    # Translate response
    try:
        translated_response = await translate_text(response_text, "en", lang)
        if validate_translation(translated_response, lang):
            logger.info(f"Translated response for user {user_id}: {translated_response[:100]}...")
            mongodb.save_interaction(user_id, "report", query, translated_response)
            return translated_response
        else:
            logger.warning(f"Translation validation failed for lang={lang}. Using English fallback.")
            mongodb.save_interaction(user_id, "report", query, response_text)
            return response_text
    except Exception as e:
        logger.error(f"Translation error for user {user_id}: {str(e)}", exc_info=True)
        mongodb.save_interaction(user_id, "report", query, response_text)
        return response_text