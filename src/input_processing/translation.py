import logging
import sys
import os
from google.cloud import translate_v2 as translate
from deep_translator import GoogleTranslator
from src.utils.helpers import validate_translation, LANGUAGE_MAP

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

async def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """
    Translate text from source language to target language using Google Cloud Translate.
    Fallback to deep-translator if Google Cloud fails.
    Args:
        text: Text to translate
        source_lang: Source language code (e.g., 'en')
        target_lang: Target language code (e.g., 'ml')
    Returns:
        Translated text
    """
    if not text or not isinstance(text, str):
        logger.warning(f"Invalid input text for translation: {text}")
        return text

    if target_lang not in LANGUAGE_MAP:
        logger.warning(f"Invalid target language: {target_lang}. Returning original text.")
        return text

    if source_lang == target_lang:
        logger.info(f"No translation needed for {source_lang} to {target_lang}: {text[:50]}...")
        return text

    # Add medical context only for translation, strip for output
    health_keywords = ["health", "fever", "headache", "diabetes", "cough", "pain"]
    context_text = (
        f"Translate this health-related text accurately into {LANGUAGE_MAP[target_lang]['name']}: {text}"
        if any(word in text.lower() for word in health_keywords)
        else text
    )

    try:
        client = translate.Client()
        result = client.translate(
            context_text,
            source_language=source_lang,
            target_language=target_lang
        )
        translated_text = result["translatedText"]
        # Strip context prefix if present
        prefix = f"Translate this health-related text accurately into {LANGUAGE_MAP[target_lang]['name']}: "
        if translated_text.startswith(prefix):
            translated_text = translated_text[len(prefix):]
        if validate_translation(translated_text, target_lang):
            logger.info(
                f"Google Cloud translated '{text[:50]}...' from {source_lang} to {target_lang}: {translated_text[:50]}..."
            )
            return translated_text
        else:
            logger.warning(f"Google Cloud translation validation failed for '{text[:50]}...' to {target_lang}. Trying fallback.")
            raise ValueError("Validation failed")
    except Exception as e:
        logger.warning(f"Google Cloud translation failed: {str(e)}. Falling back to deep-translator.")
        try:
            translated_text = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
            if validate_translation(translated_text, target_lang):
                logger.info(
                    f"Deep-translator translated '{text[:50]}...' from {source_lang} to {target_lang}: {translated_text[:50]}..."
                )
                return translated_text
            else:
                logger.warning(f"Deep-translator validation failed for '{text[:50]}...' to {target_lang}.")
                return text
        except Exception as e:
            logger.error(f"Deep-translator translation failed: {str(e)}")
            return text