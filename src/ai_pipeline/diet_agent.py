import logging
import os
from typing import Optional, Tuple
from src.database.mongodb import MongoDB
from src.utils.pdf_generator import generate_pdf
from google.cloud import translate_v2 as translate
from google.generativeai import GenerativeModel
import google.generativeai as genai
import hashlib
import json
import re
import time

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class DietAgent:
    def __init__(self):
        """Initialize the DietAgent with necessary configurations."""
        self.mongodb = MongoDB()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            raise ValueError("GEMINI_API_KEY is required")
        genai.configure(api_key=api_key)
        self.model = GenerativeModel("gemini-1.5-pro")
        self.translate_client = translate.Client()

    def normalize_condition(self, condition: str) -> str:
        """Normalize condition names to handle typos and variations."""
        condition = condition.lower().strip()
        condition_map = {
            "diabetics": "diabetes",
            "diabetic": "diabetes",
            "hypertensions": "hypertension",
            "high blood pressure": "hypertension",
            "cholestrol": "cholesterol",
            "high cholesterol": "cholesterol"
        }
        return condition_map.get(condition, condition)

    async def generate_diet_plan(
        self,
        user_id: str,
        input_text: str,
        is_medical_report: bool = False,
        condition: Optional[str] = None,
        dietary_preference: Optional[str] = None
    ) -> Tuple[dict, Optional[str]]:
        """Generate a structured diet plan as a dictionary."""
        logger.info(
            f"Processing diet query for user {user_id}: {input_text}, "
            f"is_medical_report={is_medical_report}, condition={condition}, "
            f"dietary_preference={dietary_preference}"
        )

        user_profile = self.mongodb.get_user(user_id)
        language = user_profile.get("language", "en")
        age = user_profile.get("age")
        allergies = user_profile.get("allergies", [])
        name = user_profile.get("name", "User")

        if condition:
            condition = self.normalize_condition(condition)

        cache_key = hashlib.md5(
            f"{user_id}_{input_text}_{condition}_{language}".encode()
        ).hexdigest()

        cached_response = self.mongodb.get_cached_response(cache_key)
        if cached_response:
            logger.info(f"Returning cached diet plan for user {user_id}, cache_key: {cache_key}")
            return cached_response["diet_plan"], cached_response.get("pdf_path")

        prompt_template = self.mongodb.get_diet_plan_prompt(language)
        if not prompt_template:
            logger.warning(f"No diet plan prompt found for language {language}, falling back to default")
            prompt_template = {
                "template": (
                    "You are a professional dietitian. Create a detailed, personalized 7-day diet plan for a {age}-year-old "
                    "named {name} with the following details:\n"
                    "- Health condition: {condition}\n"
                    "- Allergies: {allergies}\n"
                    "- Input: {input_text}\n"
                    "{dietary_prompt}"
                    "Return the plan as a JSON object wrapped in triple backticks (```json\n...\n```) with the following structure:\n"
                    "```json\n"
                    "{{\n"
                    "  \"days\": {{\n"
                    "    \"1\": [\n"
                    "      {{\"time\": \"07:00-08:00\", \"type\": \"Breakfast\", \"details\": \"Description of meal\"}},\n"
                    "      {{\"time\": \"10:00-11:00\", \"type\": \"Snack\", \"details\": \"Description of snack\"}},\n"
                    "      ...\n"
                    "    ],\n"
                    "    \"2\": [...],\n"
                    "    ...\n"
                    "  }},\n"
                    "  \"notes\": \"General dietary advice\"\n"
                    "}}\n"
                    "```\n"
                    "Ensure the response contains only the JSON object inside the backticks, with no additional text. "
                    "The plan must be culturally appropriate for {language} speakers (e.g., include Kerala-specific foods like dosa, sambar for Malayalam) and avoid allergens. "
                    "If the input is a medical report, extract relevant health conditions and create a balanced diet plan."
                )
            }

        dietary_prompt = "" if is_medical_report else f"- Dietary preference: {dietary_preference or 'not specified'}\n"
        prompt = prompt_template["template"].format(
            age=age or "unknown",
            name=name,
            condition=condition or "none",
            allergies=", ".join(allergies) if allergies else "none",
            input_text=input_text,
            language=language,
            dietary_prompt=dietary_prompt
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.debug(f"Attempt {attempt + 1} to call Gemini API for user {user_id}")
                response = self.model.generate_content(prompt)
                response_text = response.text.strip()
                logger.debug(f"Raw Gemini response for user {user_id}: {response_text}")

                if not response_text:
                    logger.error(f"Empty response from Gemini for user {user_id} on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return {"error": "Empty response from Gemini"}, None

                # Extract JSON from backticks if present
                json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(1).strip()
                else:
                    json_text = response_text

                # Parse JSON
                try:
                    diet_plan = json.loads(json_text)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON diet plan for user {user_id}: {str(e)}. Raw response: {response_text}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return {"error": "Invalid diet plan format"}, None

                # Validate diet plan structure
                if not isinstance(diet_plan, dict) or "days" not in diet_plan or "notes" not in diet_plan:
                    logger.error(f"Malformed diet plan for user {user_id}: Missing days or notes. Raw response: {response_text}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return {"error": "Invalid diet plan structure"}, None

                # Translate if needed
                if language != "en":
                    for day, meals in diet_plan["days"].items():
                        for meal in meals:
                            meal["details"] = self.translate_client.translate(
                                meal["details"], source_language="en", target_language=language
                            )["translatedText"]
                            meal["type"] = self.translate_client.translate(
                                meal["type"], source_language="en", target_language=language
                            )["translatedText"]
                    diet_plan["notes"] = self.translate_client.translate(
                        diet_plan["notes"], source_language="en", target_language=language
                    )["translatedText"]

                # Generate PDF
                user_info = {"name": name, "age": age or "Unknown", "condition": condition or "None"}
                pdf_path = await generate_pdf(
                    diet_plan,
                    f"Diet_Plan_{user_id}.pdf",
                    language=language,
                    user_info=user_info
                )
                logger.info(f"Generated diet plan PDF for user {user_id}: {pdf_path}")

                if pdf_path:
                    self.mongodb.cache_response(cache_key, {"diet_plan": diet_plan, "pdf_path": pdf_path})
                    self.mongodb.save_interaction(
                        user_id=user_id,
                        input_type="diet",
                        input_text=input_text,
                        response=json.dumps(diet_plan),
                        language=language,
                        pdf_path=pdf_path
                    )
                else:
                    logger.error(f"PDF generation failed for user {user_id}")
                    return {"error": "Failed to generate PDF"}, None

                return diet_plan, pdf_path
            except Exception as e:
                logger.error(f"Error generating diet plan for user {user_id} on attempt {attempt + 1}: {str(e)}", exc_info=True)
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return {"error": "Failed to generate diet plan"}, None

    def close(self):
        """Close MongoDB connection."""
        self.mongodb.close()