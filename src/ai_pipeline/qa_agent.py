import logging
import sys
import os
import re
from dotenv import load_dotenv
from google.generativeai import GenerativeModel
from src.database.mongodb import MongoDB
from src.utils.helpers import sanitize_text, validate_translation, LANGUAGE_MAP
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

if os.name == "nt":
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

async def process_query(user_id: str, query: str, is_audio: bool = False) -> str:
    """
    Process a medical-related query using Gemini API with an AI doctor theme.
    Args:
        user_id: User identifier
        query: Sanitized user query
        is_audio: Whether the response should be prepared for audio output
    Returns:
        Translated response text
    """
    logger.info(f"Processing query for user {user_id}: {query} (is_audio={is_audio})")
    mongodb = MongoDB()
    user_profile = mongodb.get_user(user_id)
    user_name = user_profile.get("name", "there")
    lang = user_profile.get("language", "en")
    age = user_profile.get("age", None)
    allergies = user_profile.get("allergies", [])

    if lang not in LANGUAGE_MAP:
        logger.warning(f"Invalid language {lang} for user {user_id}. Defaulting to English.")
        lang = "en"

    # Detect allergies in query (e.g., "I'm allergic to penicillin")
    query_allergies = []
    allergy_pattern = r"(?:allergic to|allergy to)\s*([\w\s,]+)"
    match = re.search(allergy_pattern, query.lower())
    if match:
        query_allergies = [allergy.strip() for allergy in match.group(1).split(",") if allergy.strip()]
        allergies.extend(query_allergies)
        allergies = list(set(allergies))  # Remove duplicates
        mongodb.save_user({"user_id": user_id, "language": lang, "name": user_name, "age": age, "allergies": allergies})
        logger.info(f"Detected allergies in query for user {user_id}: {query_allergies}")

    # Retrieve recent interactions for context
    try:
        recent_interaction = mongodb.db.interactions.find_one(
            {"user_id": user_id, "input_type": "query"},
            sort=[("timestamp", -1)]
        ) if mongodb.db else None
        context = recent_interaction["query"] + " -> " + recent_interaction["response"] if recent_interaction else ""
    except Exception as e:
        logger.error(f"Error fetching recent interaction for user {user_id}: {str(e)}")
        context = ""

    # Prepare user context
    user_context = []
    if age is not None:
        user_context.append(f"Patient age: {age} years.")
    if allergies:
        user_context.append(f"Patient allergies: {', '.join(allergies)}. Provide warnings if relevant.")
    user_context_str = " ".join(user_context) if user_context else ""

    # Construct AI doctor-themed prompt
    prompt = (
        f"Hello, {user_name}, I'm your AI doctor, here to guide you with clear and safe health advice. "
        f"You asked: '{query}' in {LANGUAGE_MAP[lang]['name']}. "
        f"{user_context_str} "
        f"Previous discussion (if relevant): '{context}' "
        "Provide a concise, empathetic response in simple English (under 150 words) tailored for an Indian patient. "
        "Address the query (e.g., causes, symptoms, prevention, or general advice) using clear, non-technical terms. "
        "If the query involves medications or allergies, include safety warnings and recommend consulting a doctor. "
        "For unclear queries, politely ask for more details. "
        "Do not diagnose or prescribe. "
        "End with: 'Please see a doctor for personalized advice. Have more questions? I'm here to help!'"
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
            f"Hello, {user_name}, I'm sorry, but I couldn't process your query '{query}' right now. "
            "Please share more details or try again later."
        )

    # Translate response
    try:
        translated_response = await translate_text(response_text, "en", lang)
        if validate_translation(translated_response, lang):
            logger.info(f"Translated response for user {user_id}: {translated_response[:100]}...")
        else:
            logger.warning(f"Translation validation failed for lang={lang}. Using English fallback.")
            translated_response = response_text
    except Exception as e:
        logger.error(f"Translation error for user {user_id}: {str(e)}", exc_info=True)
        translated_response = response_text

    # Store interaction
    try:
        mongodb.save_interaction(user_id, "query", query, translated_response, is_audio=is_audio)
        logger.info(f"Saved query interaction for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving interaction for user {user_id}: {str(e)}")

    return translated_response