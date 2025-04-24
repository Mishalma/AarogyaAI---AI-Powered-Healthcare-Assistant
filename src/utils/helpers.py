import re
import logging
from typing import Dict

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log", encoding="utf-8")]
)
logger = logging.getLogger(__name__)

LANGUAGE_MAP: Dict[str, Dict[str, str]] = {
    "en": {"name": "English", "speech_code": "en-US"},
    "hi": {"name": "हिन्दी", "speech_code": "hi-IN"},
    "ta": {"name": "தமிழ்", "speech_code": "ta-IN"},
    "te": {"name": "తెలుగు", "speech_code": "te-IN"},
    "ml": {"name": "മലയാളം", "speech_code": "ml-IN"},
    "bn": {"name": "বাংলা", "speech_code": "bn-IN"},
    "kn": {"name": "ಕನ್ನಡ", "speech_code": "kn-IN"},
}

# General health-related keywords for validation
HEALTH_KEYWORDS = {
    "en": ["health", "fever", "headache", "diabetes", "cough", "pain", "allergy", "blood", "heart", "infection"],
    "hi": ["स्वास्थ्य", "बुखार", "सिरदर्द", "मधुमेह", "खांसी", "दर्द", "एलर्जी", "रक्त", "हृदय", "संक्रमण"],
    "ta": ["ஆரோக்கியம்", "காய்ச்சல்", "தலைவலி", "நீரிழிவு", "இருமல்", "வலி", "ஒவ்வாமை", "இரத்தம்", "இதயம்", "தொற்று"],
    "te": ["ఆరోగ్యం", "జ్వరం", "తలనొప్పి", "డయాబెటిస్", "దగ్గు", "నొప్పి", "అలెర్జీ", "రక్తం", "గుండె", "సంక్రమణం"],
    "ml": ["ആരോഗ്യം", "പനി", "തലവേദന", "പ്രമേഹം", "കഫം", "വേദന", "അലർജി", "രക്തം", "ഹൃദയം", "അണുബാധ"],
    "bn": ["স্বাস্থ্য", "জ্বর", "মাথাব্যথা", "ডায়াবেটিস", "কাশি", "ব্যথা", "অ্যালার্জি", "রক্ত", "হৃদয়", "সংক্রমণ"],
    "kn": ["ಆರೋಗ್ಯ", "ಜ್ವರ", "ತಲೆನೋವು", "ಮಧುಮೇಹ", "ಕೆಮ್ಮು", "ನೋವು", "ಅಲರ್ಜಿ", "ರಕ್ತ", "ಹೃದಯ", "ಸೋಂಕು"],
}

def sanitize_text(text: str) -> str:
    """Remove special characters and normalize text."""
    if not isinstance(text, str):
        logger.warning(f"Invalid text input for sanitization: {text}")
        return ""
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()

def validate_translation(text: str, lang: str) -> bool:
    """Validate if translated text is non-empty and matches language."""
    if not text or not isinstance(text, str) or len(text.strip()) < 2:
        logger.warning(f"Translation validation failed: Empty or too short text for lang={lang}")
        return False

    # Skip medical validation for setup prompts
    setup_prompts = ["name", "age", "set up", "ready", "provide"]
    if any(prompt in text.lower() for prompt in setup_prompts):
        logger.info(f"Skipping medical validation for setup prompt: {text[:50]}...")
        # Check language-specific characters (except for English)
        if lang != "en":
            if lang == "hi" and not any(0x0900 <= ord(c) <= 0x097F for c in text):
                logger.warning(f"Translation validation failed: No Hindi characters for lang={lang}")
                return False
            if lang == "ta" and not any(0x0B80 <= ord(c) <= 0x0BFF for c in text):
                logger.warning(f"Translation validation failed: No Tamil characters for lang={lang}")
                return False
            if lang == "te" and not any(0x0C00 <= ord(c) <= 0x0C7F for c in text):
                logger.warning(f"Translation validation failed: No Telugu characters for lang={lang}")
                return False
            if lang == "ml" and not any(0x0D00 <= ord(c) <= 0x0D7F for c in text):
                logger.warning(f"Translation validation failed: No Malayalam characters for lang={lang}")
                return False
            if lang == "bn" and not any(0x0980 <= ord(c) <= 0x09FF for c in text):
                logger.warning(f"Translation validation failed: No Bengali characters for lang={lang}")
                return False
            if lang == "kn" and not any(0x0C80 <= ord(c) <= 0x0CFF for c in text):
                logger.warning(f"Translation validation failed: No Kannada characters for lang={lang}")
                return False
        return True

    # Validate health-related translations
    if lang in HEALTH_KEYWORDS and any(term in text.lower() for term in HEALTH_KEYWORDS["en"]):
        if not any(term in text for term in HEALTH_KEYWORDS[lang]):
            logger.warning(f"Translation validation failed: No relevant health keywords for lang={lang}")
            return False

    # Check language-specific characters for non-English languages
    if lang != "en":
        if lang == "hi" and not any(0x0900 <= ord(c) <= 0x097F for c in text):
            logger.warning(f"Translation validation failed: No Hindi characters for lang={lang}")
            return False
        if lang == "ta" and not any(0x0B80 <= ord(c) <= 0x0BFF for c in text):
            logger.warning(f"Translation validation failed: No Tamil characters for lang={lang}")
            return False
        if lang == "te" and not any(0x0C00 <= ord(c) <= 0x0C7F for c in text):
            logger.warning(f"Translation validation failed: No Telugu characters for lang={lang}")
            return False
        if lang == "ml" and not any(0x0D00 <= ord(c) <= 0x0D7F for c in text):
            logger.warning(f"Translation validation failed: No Malayalam characters for lang={lang}")
            return False
        if lang == "bn" and not any(0x0980 <= ord(c) <= 0x09FF for c in text):
            logger.warning(f"Translation validation failed: No Bengali characters for lang={lang}")
            return False
        if lang == "kn" and not any(0x0C80 <= ord(c) <= 0x0CFF for c in text):
            logger.warning(f"Translation validation failed: No Kannada characters for lang={lang}")
            return False

    return True