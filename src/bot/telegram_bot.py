import logging
import os
import sys
import re
import asyncio
import httpx
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from google.cloud import texttospeech
from src.database.mongodb import MongoDB
from src.utils.helpers import sanitize_text, validate_translation, LANGUAGE_MAP
from src.input_processing.asr import transcribe_audio
from src.input_processing.ocr import extract_text_from_image
from src.input_processing.translation import translate_text
from src.ai_pipeline.diet_agent import DietAgent

load_dotenv()

# Enable verbose logging for python-telegram-bot
logging.getLogger("telegram").setLevel(logging.DEBUG)
logging.getLogger("telegram.ext").setLevel(logging.DEBUG)


class UnicodeSafeStreamHandler(logging.StreamHandler):
    def __init__(self):
        super().__init__(stream=sys.stdout)
        if sys.stdout.encoding.lower() != "utf-8":
            self.stream = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        UnicodeSafeStreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"
DIAGNOSTIC_MODE = os.getenv("DIAGNOSTIC_MODE", "True").lower() == "true"

# Initialize DietAgent globally
diet_agent = DietAgent()


def check_dependencies():
    """Check if critical dependencies are installed."""
    try:
        import google.cloud.texttospeech
        import google.cloud.translate
        import pymongo
        import telegram
        logger.info(
            f"Dependencies installed: google-cloud-texttospeech, google-cloud-translate ({google.cloud.translate.__version__}), pymongo ({pymongo.__version__}), python-telegram-bot ({telegram.__version__})")
    except ImportError as e:
        logger.error(f"Missing dependency: {str(e)}. Please install required packages.")
        sys.exit(1)


def text_to_speech(text: str, lang: str, output_path: str) -> bool:
    try:
        client = texttospeech.TextToSpeechClient()
        speech_code = LANGUAGE_MAP.get(lang, {"speech_code": "en-IN"})["speech_code"]
        tts_lang_map = {
            "en-IN": "en-IN",
            "hi-IN": "hi-IN",
            "ta-IN": "ta-IN",
            "te-IN": "te-IN",
            "ml-IN": "ml-IN",
            "bn-IN": "bn-IN",
            "kn-IN": "kn-IN"
        }
        tts_lang = tts_lang_map.get(speech_code, "en-IN")

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=tts_lang,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        with open(output_path, "wb") as out:
            out.write(response.audio_content)
        logger.info(f"Generated audio file: {output_path}")
        return True
    except Exception as e:
        logger.error(f"Text-to-speech error: {str(e)}", exc_info=True)
        return False


async def trigger_n8n_workflow(user_id: str, chat_id: str, prompt: str):
    """Trigger n8n workflow to send text prompt."""
    n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/diet-plan-text")
    payload = {
        "user_id": user_id,
        "chat_id": chat_id,
        "prompt": prompt
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(n8n_webhook_url, json=payload)
            response.raise_for_status()
            logger.info(f"Triggered n8n workflow for user {user_id}: {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to trigger n8n workflow for user {user_id}: {str(e)}", exc_info=True)


async def route_query(user_id: str, text: str, input_type: str) -> str:
    """Placeholder for routing general queries."""
    logger.warning(f"Placeholder route_query called for user {user_id}, text: {text}, type: {input_type}")
    return "This feature is under development. Please use /dietplan for diet-related requests."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    logger.info(f"Start command received from user {user_id}")
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Entering start handler for user {user_id}, update: {update.to_dict()}")
    mongodb = MongoDB()
    if mongodb.db is None:
        logger.error(f"Database connection failed for user {user_id}")
        await update.message.reply_text("Sorry, we're experiencing database issues. Please try again later.")
        return

    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Fetching user profile for {user_id}")
    user_profile = mongodb.get_user(user_id)
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] User profile: {user_profile}")
    if user_profile.get("language") and user_profile.get("name") and "age" in user_profile and user_profile.get(
            "allergies") is not None:
        lang = user_profile.get("language", "en")
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Translating welcome message for lang {lang}")
        prompt = await translate_text(
            f"Welcome back, {user_profile['name']}! Select an option or use /dietplan for diet options:",
            "en", lang
        ) or f"Welcome back, {user_profile['name']}! Select an option or use /dietplan for diet options:"
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Sending welcome message to {user_id}: {prompt}")
        keyboard = [
            [InlineKeyboardButton("Queries", callback_data="action_queries")],
            [InlineKeyboardButton("Prediction", callback_data="action_prediction")],
            [InlineKeyboardButton("Diet Plan", callback_data="action_diet_plan")],
            [InlineKeyboardButton("Prescription", callback_data="action_prescription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(prompt, reply_markup=reply_markup)
        return

    keyboard = [
        [InlineKeyboardButton(LANGUAGE_MAP[lang]["name"], callback_data=f"lang_{lang}")]
        for lang in LANGUAGE_MAP
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Sending language selection to {user_id}")
    await update.message.reply_text("Welcome to AarogyaAI! Please select your language:", reply_markup=reply_markup)


async def diet_plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    logger.info(f"Diet plan command received from user {user_id}")
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Entering diet_plan_command for user {user_id}, update: {update.to_dict()}")

    mongodb = MongoDB()
    if mongodb.db is None:
        logger.error(f"Database connection failed for user {user_id}")
        await update.message.reply_text("Sorry, we're experiencing database issues. Please try again later.")
        return

    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Fetching user profile for {user_id}")
    user_profile = mongodb.get_user(user_id)
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] User profile: {user_profile}")
    if not user_profile.get("language"):
        logger.error(f"No language set for user {user_id}")
        await update.message.reply_text("Please start with /start to select your language.")
        return
    lang = user_profile.get("language", "en")
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Language for user {user_id}: {lang}")

    prompt = await translate_text(
        "Please reply with: 1 for Medical Report, 2 for Specific Condition, 3 for General Diet",
        "en", lang
    ) or "Please reply with: 1 for Medical Report, 2 for Specific Condition, 3 for General Diet"
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Diet plan prompt: {prompt}")
    try:
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Saving awaiting_diet_plan_choice state for user {user_id}")
        mongodb.save_user({"user_id": user_id, "awaiting_diet_plan_choice": True})
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Sending diet plan prompt to user {user_id}")
        await update.message.reply_text(prompt)
        logger.info(f"Successfully sent diet plan prompt to user {user_id}")
    except Exception as e:
        logger.error(f"Telegram API error sending diet plan prompt to user {user_id}: {str(e)}", exc_info=True)
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Triggering n8n fallback for user {user_id}")
        await trigger_n8n_workflow(user_id, str(update.message.chat_id), prompt)
        await update.message.reply_text("Prompt sent via backup system. Please check or try again.")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Raw update received: {update.to_dict()}")
    query = update.callback_query
    try:
        await query.answer()
        logger.info(f"Answered callback query for user {query.from_user.id}, data: {query.data}")
    except Exception as e:
        logger.error(f"Error answering callback query: {str(e)}", exc_info=True)
        return

    user_id = str(query.from_user.id)
    data = query.data
    logger.info(f"Button clicked by {user_id}: {data}")
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Entering button handler for user {user_id}, data: {data}")

    try:
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Initializing MongoDB for user {user_id}")
        mongodb = MongoDB()
        if mongodb.db is None:
            logger.error(f"Database connection failed for user {user_id}")
            await query.message.reply_text("Sorry, we're experiencing database issues. Please try again later.")
            return

        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Fetching user profile for {user_id}")
        user_profile = mongodb.get_user(user_id)
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] User profile for {user_id}: {user_profile}")
        if not user_profile.get("language"):
            logger.error(f"No language set for user {user_id}")
            await query.message.reply_text("Please start with /start to select your language.")
            return
        lang = user_profile.get("language", "en")
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Language for user {user_id}: {lang}")

        if data.startswith("lang_"):
            if DIAGNOSTIC_MODE:
                logger.debug(f"[DIAGNOSTIC] Processing language selection: {data}")
            lang = data.split("_")[1]
            if lang not in LANGUAGE_MAP:
                logger.error(f"Invalid language selected by {user_id}: {lang}")
                await query.message.reply_text("Invalid language selected. Please try again.")
                return
            user_data = {
                "user_id": user_id,
                "language": lang,
                "awaiting_name": True,
                "awaiting_age": False,
                "awaiting_allergies": False
            }
            if DIAGNOSTIC_MODE:
                logger.debug(f"[DIAGNOSTIC] Saving user data: {user_data}")
            mongodb.save_user(user_data)
            logger.info(f"Language set to {lang} for user {user_id}")
            prompt = await translate_text(
                "Please provide your name (1-50 characters).", "en", lang
            ) or "Please provide your name (1-50 characters)."
            await query.message.reply_text(prompt)

        elif data.startswith("action_"):
            action = data.split("_")[1]
            if DIAGNOSTIC_MODE:
                logger.debug(f"[DIAGNOSTIC] Processing action: {action}")
            if action == "queries":
                prompt = await translate_text(
                    "Please enter your health-related query.", "en", lang
                ) or "Please enter your health-related query."
                await query.message.reply_text(prompt)
            elif action == "prediction":
                prompt = await translate_text(
                    "Prediction feature is not available yet. Please try another option.", "en", lang
                ) or "Prediction feature is not available yet. Please try another option."
                await query.message.reply_text(prompt)
            elif action == "diet_plan":
                logger.info(f"Processing diet_plan action for user {user_id}")
                if DIAGNOSTIC_MODE:
                    logger.debug(f"[DIAGNOSTIC] Entering diet_plan handler for user {user_id}")
                prompt = await translate_text(
                    "Please reply with: 1 for Medical Report, 2 for Specific Condition, 3 for General Diet",
                    "en", lang
                ) or "Please reply with: 1 for Medical Report, 2 for Specific Condition, 3 for General Diet"
                if DIAGNOSTIC_MODE:
                    logger.debug(f"[DIAGNOSTIC] Diet plan prompt: {prompt}")
                try:
                    if DIAGNOSTIC_MODE:
                        logger.debug(f"[DIAGNOSTIC] Saving awaiting_diet_plan_choice state for user {user_id}")
                    mongodb.save_user({"user_id": user_id, "awaiting_diet_plan_choice": True})
                    if DIAGNOSTIC_MODE:
                        logger.debug(f"[DIAGNOSTIC] Sending diet plan prompt to user {user_id}")
                    await query.message.reply_text(prompt)
                    logger.info(f"Successfully sent diet plan prompt to user {user_id}")
                except Exception as e:
                    logger.error(f"Telegram API error sending diet plan prompt to user {user_id}: {str(e)}",
                                 exc_info=True)
                    if DIAGNOSTIC_MODE:
                        logger.debug(f"[DIAGNOSTIC] Triggering n8n fallback for user {user_id}")
                    await trigger_n8n_workflow(user_id, str(query.message.chat_id), prompt)
                    await query.message.reply_text("Prompt sent via backup system. Please check or try again.")
            elif action == "prescription":
                prompt = await translate_text(
                    "Prescription feature is not available yet. Please try another option.", "en", lang
                ) or "Prescription feature is not available yet. Please try another option."
                await query.message.reply_text(prompt)
    except Exception as e:
        logger.error(f"Unexpected error in button handler for user {user_id}: {str(e)}", exc_info=True)
        error_msg = await translate_text(
            "❌ Error processing your request. Please try again.", "en", lang
        ) or "❌ Error processing your request. Please try again."
        await query.message.reply_text(error_msg)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Entering handle_text for user {user_id}, update: {update.to_dict()}")
    mongodb = MongoDB()
    if mongodb.db is None:
        logger.error(f"Database connection failed for user {user_id}")
        await update.message.reply_text("Sorry, we're experiencing database issues. Please try again later.")
        return

    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Fetching user profile for {user_id}")
    user_profile = mongodb.get_user(user_id)
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] User profile: {user_profile}")
    text = update.message.text.strip()
    lang = user_profile.get("language", "en")
    logger.debug(f"Received text from {user_id}: {text}, lang: {lang}")

    if not user_profile.get("language"):
        logger.error(f"No language set for {user_id}")
        await update.message.reply_text("Please start with /start to select your language.")
        return

    if user_profile.get("awaiting_diet_plan_choice"):
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Processing diet plan choice: {text}")
        if text in ["1", "2", "3"]:
            try:
                if text == "1":
                    prompt = await translate_text(
                        "Please upload your medical report (PDF or image).", "en", lang
                    ) or "Please upload your medical report (PDF or image)."
                    mongodb.save_user({
                        "user_id": user_id,
                        "awaiting_diet_report": True,
                        "awaiting_diet_plan_choice": False
                    })
                    await update.message.reply_text(prompt)
                elif text == "2":
                    prompt = await translate_text(
                        "Please specify a condition (e.g., diabetes, hypertension, cholesterol).",
                        "en", lang
                    ) or "Please specify a condition (e.g., diabetes, hypertension, cholesterol)."
                    mongodb.save_user({
                        "user_id": user_id,
                        "awaiting_diet_condition": True,
                        "awaiting_diet_plan_choice": False
                    })
                    await update.message.reply_text(prompt)
                elif text == "3":
                    logger.info(f"Generating general diet plan for user {user_id}")
                    response, pdf_path = await diet_agent.generate_diet_plan(user_id, "general diet plan",
                                                                             is_medical_report=False)
                    if pdf_path and os.path.exists(pdf_path):
                        try:
                            with open(pdf_path, "rb") as pdf_file:
                                await update.message.reply_document(document=pdf_file,
                                                                    filename=f"Diet_Plan_{user_id}.pdf")
                            logger.info(f"Sent diet plan PDF to user {user_id}: {pdf_path}")
                        except Exception as e:
                            logger.error(f"Failed to send PDF to user {user_id}: {str(e)}", exc_info=True)
                            error_msg = await translate_text(
                                "❌ Error sending diet plan PDF. Please try again.", "en", lang
                            ) or "❌ Error sending diet plan PDF. Please try again."
                            await update.message.reply_text(error_msg)
                        finally:
                            if os.path.exists(pdf_path):
                                try:
                                    os.remove(pdf_path)
                                    logger.debug(f"Removed temporary PDF: {pdf_path}")
                                except Exception as e:
                                    logger.error(f"Failed to remove PDF {pdf_path}: {str(e)}")
                    else:
                        error_msg = await translate_text(
                            "❌ Failed to generate diet plan PDF. Please try again.", "en", lang
                        ) or "❌ Failed to generate diet plan PDF. Please try again."
                        await update.message.reply_text(error_msg)
                    mongodb.save_interaction(user_id, "diet", "general diet plan", response, lang, is_audio=False,
                                             pdf_path=pdf_path)
                    mongodb.save_user({"user_id": user_id, "awaiting_diet_plan_choice": False})
            except Exception as e:
                logger.error(f"Error processing diet plan choice {text} for user {user_id}: {str(e)}", exc_info=True)
                error_msg = await translate_text(
                    "❌ Error processing your choice. Please try again.", "en", lang
                ) or "❌ Error processing your choice. Please try again."
                await update.message.reply_text(error_msg)
        else:
            prompt = await translate_text(
                "Invalid choice. Please reply with: 1 for Medical Report, 2 for Specific Condition, 3 for General Diet",
                "en", lang
            ) or "Invalid choice. Please reply with: 1 for Medical Report, 2 for Specific Condition, 3 for General Diet"
            await update.message.reply_text(prompt)
        return

    if user_profile.get("awaiting_name"):
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Processing name input: {text}")
        if not re.match(r'^[a-zA-Z\s]{1,50}$', text):
            logger.debug(f"Invalid name provided by {user_id}: {text}")
            prompt = await translate_text(
                "Please provide a valid name (1-50 characters, letters only).",
                "en", lang
            ) or "Please provide a valid name (1-50 characters, letters only)."
            await update.message.reply_text(prompt)
            return
        user_data = {
            "user_id": user_id,
            "language": lang,
            "name": text,
            "awaiting_name": False,
            "awaiting_age": True
        }
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Saving user data: {user_data}")
        mongodb.save_user(user_data)
        logger.info(f"Name set to {text} for user {user_id}")
        prompt = await translate_text(
            "Thank you! Please provide your age (0-120).", "en", lang
        ) or "Thank you! Please provide your age (0-120)."
        await update.message.reply_text(prompt)

    elif user_profile.get("awaiting_age"):
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Processing age input: {text}")
        try:
            age = int(text)
            if not 0 <= age <= 120:
                raise ValueError("Age out of range")
            user_data = {
                "user_id": user_id,
                "language": lang,
                "name": user_profile.get("name"),
                "age": age,
                "awaiting_age": False,
                "awaiting_allergies": True
            }
            if DIAGNOSTIC_MODE:
                logger.debug(f"[DIAGNOSTIC] Saving user data: {user_data}")
            mongodb.save_user(user_data)
            logger.info(f"Age set to {age} for user {user_id}")
            prompt = await translate_text(
                "Thank you! Do you have any allergies (e.g., penicillin)? If none, say 'None'.",
                "en", lang
            ) or "Thank you! Do you have any allergies (e.g., penicillin)? If none, say 'None'."
            await update.message.reply_text(prompt)
        except ValueError as e:
            logger.debug(f"Invalid age provided by {user_id}: {text}, error: {str(e)}")
            prompt = await translate_text(
                "Please provide a valid age (0-120, numbers only).", "en", lang
            ) or "Please provide a valid age (0-120, numbers only)."
            await update.message.reply_text(prompt)

    elif user_profile.get("awaiting_allergies"):
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Processing allergies input: {text}")
        allergies = []
        if text.lower() != "none":
            allergies = [
                allergy.strip().lower() for allergy in text.split(",")
                if allergy.strip() and len(allergy.strip()) <= 50 and re.match(r'^[a-zA-Z\s]+$', allergy.strip())
            ]
        user_data = {
            "user_id": user_id,
            "language": lang,
            "name": user_profile.get("name"),
            "age": user_profile.get("age"),
            "allergies": allergies,
            "awaiting_allergies": False
        }
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Saving user data: {user_data}")
        mongodb.save_user(user_data)
        logger.info(f"Allergies set to {allergies} for user {user_id}")
        prompt = await translate_text(
            f"Thank you, {user_profile.get('name', 'User')}! Select an option or use /dietplan for diet options:",
            "en", lang
        ) or f"Thank you, {user_profile.get('name', 'User')}! Select an option or use /dietplan for diet options:"
        keyboard = [
            [InlineKeyboardButton("Queries", callback_data="action_queries")],
            [InlineKeyboardButton("Prediction", callback_data="action_prediction")],
            [InlineKeyboardButton("Diet Plan", callback_data="action_diet_plan")],
            [InlineKeyboardButton("Prescription", callback_data="action_prescription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(prompt, reply_markup=reply_markup)

    elif user_profile.get("awaiting_diet_condition"):
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Processing diet condition: {text}")
        logger.info(f"Generating diet plan for condition '{text}' for user {user_id}")
        try:
            response, pdf_path = await diet_agent.generate_diet_plan(user_id, text, is_medical_report=False,
                                                                     condition=text)
            if pdf_path and os.path.exists(pdf_path):
                try:
                    with open(pdf_path, "rb") as pdf_file:
                        await update.message.reply_document(document=pdf_file, filename=f"Diet_Plan_{user_id}.pdf")
                    logger.info(f"Sent diet plan PDF to user {user_id}: {pdf_path}")
                except Exception as e:
                    logger.error(f"Failed to send PDF to user {user_id}: {str(e)}", exc_info=True)
                    error_msg = await translate_text(
                        "❌ Error sending diet plan PDF. Please try again.", "en", lang
                    ) or "❌ Error sending diet plan PDF. Please try again."
                    await update.message.reply_text(error_msg)
                finally:
                    if os.path.exists(pdf_path):
                        try:
                            os.remove(pdf_path)
                            logger.debug(f"Removed temporary PDF: {pdf_path}")
                        except Exception as e:
                            logger.error(f"Failed to remove PDF {pdf_path}: {str(e)}")
            else:
                error_msg = await translate_text(
                    "❌ Failed to generate diet plan PDF. Please try again.", "en", lang
                ) or "❌ Failed to generate diet plan PDF. Please try again."
                await update.message.reply_text(error_msg)
            mongodb.save_interaction(user_id, "diet", text, response, lang, is_audio=False, pdf_path=pdf_path)
            mongodb.save_user({"user_id": user_id, "awaiting_diet_condition": False})
        except Exception as e:
            logger.error(f"Error generating diet plan for condition '{text}' for user {user_id}: {str(e)}",
                         exc_info=True)
            error_msg = await translate_text(
                "❌ Error generating diet plan. Please try again.", "en", lang
            ) or "❌ Error generating diet plan. Please try again."
            await update.message.reply_text(error_msg)

    else:
        if DIAGNOSTIC_MODE:
            logger.debug(f"[DIAGNOSTIC] Routing general query: {text}")
        sanitized_text = sanitize_text(text)
        logger.debug(f"Routing query for {user_id}: {sanitized_text}")
        try:
            response = await route_query(user_id, sanitized_text, input_type="query")
            translated_response = await translate_text(response, "en", lang) or response
            logger.debug(f"Sending query response to {user_id}: {translated_response[:100]}...")

            if isinstance(response, tuple):
                translated_response, pdf_path = response
                if pdf_path and os.path.exists(pdf_path):
                    try:
                        with open(pdf_path, "rb") as pdf_file:
                            await update.message.reply_document(document=pdf_file, filename=f"Diet_Plan_{user_id}.pdf")
                        logger.info(f"Sent diet plan PDF to user {user_id}: {pdf_path}")
                    except Exception as e:
                        logger.error(f"Failed to send PDF to user {user_id}: {str(e)}", exc_info=True)
                        error_msg = await translate_text(
                            "❌ Error sending diet plan PDF. Please try again.", "en", lang
                        ) or "❌ Error sending diet plan PDF. Please try again."
                        await update.message.reply_text(error_msg)
                    finally:
                        if os.path.exists(pdf_path):
                            try:
                                os.remove(pdf_path)
                                logger.debug(f"Removed temporary PDF: {pdf_path}")
                            except Exception as e:
                                logger.error(f"Failed to remove PDF {pdf_path}: {str(e)}")
                else:
                    await send_long_message(update.message, translated_response)
            else:
                await send_long_message(update.message, translated_response)

            mongodb.save_interaction(user_id, "query", sanitized_text, translated_response, lang, is_audio=False)
        except Exception as e:
            logger.error(f"Query processing error for user {user_id}: {str(e)}", exc_info=True)
            error_msg = await translate_text(
                "Sorry, an error occurred. Please try again.", "en", lang
            ) or "Sorry, an error occurred. Please try again."
            await update.message.reply_text(error_msg)


async def send_long_message(message: Update.message, text: str, max_length: int = 4096):
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Sending long message: {text[:100]}...")
    if not isinstance(text, str):
        logger.error(f"Expected string for send_long_message, got {type(text)}: {text}")
        text = "❌ Error processing message. Please try again."
    if len(text) <= max_length:
        await message.reply_text(text)
    else:
        parts = [text[i: i + max_length] for i in range(0, len(text), max_length)]
        for part in parts:
            await message.reply_text(part)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Entering handle_document for user {user_id}, update: {update.to_dict()}")
    mongodb = MongoDB()
    if mongodb.db is None:
        logger.error(f"Database connection failed for user {user_id}")
        await update.message.reply_text("Sorry, we're experiencing database issues. Please try again later.")
        return

    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Fetching user profile for {user_id}")
    user_profile = mongodb.get_user(user_id)
    lang = user_profile.get("language", "en")
    logger.debug(f"Received document from {user_id}, lang: {lang}")

    if not user_profile.get("language") or user_profile.get("awaiting_name") or user_profile.get(
            "awaiting_age") or user_profile.get("awaiting_allergies"):
        logger.error(f"Setup incomplete for {user_id}: {user_profile}")
        await update.message.reply_text("Please complete setup with /start.")
        return

    document = update.message.document
    file = await context.bot.get_file(document.file_id)
    file_path = f"temp_{document.file_id}{Path(document.file_name).suffix}"
    try:
        await file.download_to_drive(file_path)
        logger.info(f"Downloaded document for user {user_id}: {file_path}")
        extracted_text = extract_text_from_image(file_path)  # Note: Should be extract_text_from_pdf for PDFs
        if not extracted_text:
            logger.warning(f"No text extracted from document for {user_id}: {file_path}")
            error_msg = await translate_text(
                "❌ No text found in document. Please upload a valid medical report.", "en", lang
            ) or "❌ No text found in document. Please upload a valid medical report."
            await update.message.reply_text(error_msg)
            return
        logger.info(f"Extracted text for user {user_id}: {extracted_text[:100]}...")

        # Extract condition (placeholder logic, replace with actual condition extraction)
        condition = extract_condition_from_text(extracted_text)

        # Generate diet plan directly without dietary preference prompt
        response, pdf_path = await diet_agent.generate_diet_plan(
            user_id=user_id,
            input_text=extracted_text,
            is_medical_report=True,
            condition=condition,
            dietary_preference=None
        )

        if pdf_path and os.path.exists(pdf_path):
            try:
                with open(pdf_path, "rb") as pdf_file:
                    await update.message.reply_document(
                        document=pdf_file,
                        filename=f"Diet_Plan_{user_id}.pdf",
                        caption=None
                    )
                logger.info(f"Sent diet plan PDF to user {user_id}: {pdf_path}")
            except Exception as e:
                logger.error(f"Failed to send PDF to user {user_id}: {str(e)}", exc_info=True)
                error_msg = await translate_text(
                    "❌ Error sending diet plan PDF. Please try again.", "en", lang
                ) or "❌ Error sending diet plan PDF. Please try again."
                await update.message.reply_text(error_msg)
            finally:
                if os.path.exists(pdf_path):
                    try:
                        os.remove(pdf_path)
                        logger.debug(f"Removed temporary PDF: {pdf_path}")
                    except Exception as e:
                        logger.error(f"Failed to remove PDF {pdf_path}: {str(e)}")
        else:
            error_msg = await translate_text(
                "❌ Failed to generate diet plan PDF. Please try again.", "en", lang
            ) or "❌ Failed to generate diet plan PDF. Please try again."
            await update.message.reply_text(error_msg)

        mongodb.save_interaction(
            user_id=user_id,
            input_type="diet",
            input_text=extracted_text,
            response=response,
            language=lang,
            is_audio=False,
            pdf_path=pdf_path
        )
        mongodb.save_user({
            "user_id": user_id,
            "pending_report_text": None,
            "awaiting_diet_report": False
        })
    except Exception as e:
        logger.error(f"Document processing error for user {user_id}: {str(e)}", exc_info=True)
        error_msg = await translate_text(
            "❌ Error processing document. Please try again.", "en", lang
        ) or "❌ Error processing document. Please try again."
        await update.message.reply_text(error_msg)
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.debug(f"Removed temporary file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to remove file {file_path}: {str(e)}")


def extract_condition_from_text(text: str) -> str:
    """Placeholder for extracting condition from report text."""
    # Implement actual condition extraction logic (e.g., regex, NLP)
    logger.warning(f"Placeholder extract_condition_from_text called")
    if "diabetes" in text.lower():
        return "diabetes"
    return None  # Replace with actual logic


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Entering handle_voice for user {user_id}, update: {update.to_dict()}")
    mongodb = MongoDB()
    if mongodb.db is None:
        logger.error(f"Database connection failed for user {user_id}")
        await update.message.reply_text("Sorry, we're experiencing database issues. Please try again later.")
        return

    if DIAGNOSTIC_MODE:
        logger.debug(f"[DIAGNOSTIC] Fetching user profile for {user_id}")
    user_profile = mongodb.get_user(user_id)
    lang = user_profile.get("language", "en")
    logger.debug(f"Received voice from {user_id}, lang: {lang}")

    if not user_profile.get("language") or user_profile.get("awaiting_name") or user_profile.get(
            "awaiting_age") or user_profile.get("awaiting_allergies"):
        logger.error(f"Setup incomplete for {user_id}: {user_profile}")
        await update.message.reply_text("Please complete setup with /start.")
        return

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    file_path = f"temp_{voice.file_id}.oga"
    audio_path = f"temp_response_{user_id}.mp3"
    logger.info(f"Received voice message from user {user_id}, language: {lang}")
    try:
        await file.download_to_drive(file_path)
        logger.info(f"Downloaded voice file to {file_path}")
        transcribed_text = transcribe_audio(file_path, lang)
        if not transcribed_text:
            logger.warning(f"Transcription failed for voice message from user {user_id}")
            error_msg = await translate_text(
                "❌ Could not transcribe voice message. Please try again.", "en", lang
            ) or "❌ Could not transcribe voice message. Please try again."
            await update.message.reply_text(error_msg)
            return
        sanitized_text = sanitize_text(transcribed_text)
        logger.debug(f"Transcribed voice query for {user_id}: {sanitized_text}")
        response = await route_query(user_id, sanitized_text, input_type="query")
        translated_response = await translate_text(response, "en", lang) or response

        if text_to_speech(translated_response, lang, audio_path):
            try:
                with open(audio_path, "rb") as audio_file:
                    await update.message.reply_voice(voice=audio_file)
                logger.info(f"Sent audio response to user {user_id}")
                mongodb.save_interaction(user_id, "query", sanitized_text, translated_response, lang, is_audio=True)
            except Exception as e:
                logger.error(f"Failed to send audio response to user {user_id}: {str(e)}", exc_info=True)
                await send_long_message(update.message, translated_response)
                mongodb.save_interaction(user_id, "query", sanitized_text, translated_response, lang, is_audio=False)
        else:
            await send_long_message(update.message, translated_response)
            mongodb.save_interaction(user_id, "query", sanitized_text, translated_response, lang, is_audio=False)
    except Exception as e:
        logger.error(f"Voice message processing error for user {user_id}: {str(e)}", exc_info=True)
        error_msg = await translate_text(
            "❌ Error processing voice message. Please try again.", "en", lang
        ) or "❌ Error processing voice message. Please try again."
        await update.message.reply_text(error_msg)
    finally:
        for path in [file_path, audio_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.debug(f"Removed temporary file: {path}")
                except Exception as e:
                    logger.error(f"Failed to remove file {path}: {str(e)}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}", exc_info=True)


async def polling_monitor(application: Application):
    """Periodically check and restart polling if stalled."""
    while True:
        await asyncio.sleep(300)  # Check every 5 minutes
        logger.debug("[DIAGNOSTIC] Checking polling status")
        try:
            # Test Telegram API connectivity
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/getMe")
                response.raise_for_status()
                logger.debug("[DIAGNOSTIC] Telegram API is responsive")
        except Exception as e:
            logger.error(f"[DIAGNOSTIC] Polling check failed: {str(e)}", exc_info=True)
            logger.info("[DIAGNOSTIC] Restarting polling")
            application.stop_running()
            application.start()


def main():
    check_dependencies()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    logger.info(f"Loaded TELEGRAM_BOT_TOKEN: {'Set' if token else 'Not set'}")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        return
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("dietplan", diet_plan_command))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_error_handler(error_handler)
    application.job_queue.run_repeating(lambda ctx: polling_monitor(application), interval=300)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()