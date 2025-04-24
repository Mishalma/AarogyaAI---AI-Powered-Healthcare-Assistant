import logging
import sys
from src.ai_pipeline.qa_agent import process_query
from src.ai_pipeline.diet_agent import generate_diet_plan
from src.ai_pipeline.prescription_agent import analyze_report
from src.utils.helpers import LANGUAGE_MAP

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

async def route_query(user_id: str, query: str, input_type: str) -> str:
    """
    Route user query to appropriate agent based on content.
    Args:
        user_id: User identifier
        query: User query
        input_type: Input type (text, voice, document)
    Returns:
        Response text
    """
    try:
        logger.info(f"Routing query for user {user_id}: type={input_type}, query={query}")
        query_lower = query.lower()

        if any(keyword in query_lower for keyword in ["diet", "nutrition", "food", "meal"]):
            logger.info(f"Routing query to diet_agent for user {user_id}")
            return await generate_diet_plan(user_id, query)
        elif any(keyword in query_lower for keyword in ["report", "medical", "prescription", "lab", "x-ray", "scan"]):
            logger.info(f"Routing query to prescription_agent for user {user_id}")
            return await analyze_report(user_id, query)
        else:
            logger.info(f"Routing query to qa_agent for user {user_id}")
            return await process_query(user_id, query)
    except Exception as e:
        logger.error(f"Error routing query for user {user_id}: {str(e)}", exc_info=True)
        return "Sorry, I couldn't process your request. Please try again."