import logging
import os
from typing import Optional, Dict, Any
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError, OperationFailure

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self):
        """Initialize MongoDB connection."""
        try:
            mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.db = self.client["aarogyaai"]
            self.users = self.db["users"]
            self.interactions = self.db["interactions"]
            self.prompt_cache = self.db["prompt_cache"]
            self.prompts = self.db["prompts"]
            self._create_indexes()
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}", exc_info=True)
            self.db = None

    def _create_indexes(self):
        """Create necessary indexes for MongoDB collections."""
        try:
            # Users collection: unique index on user_id
            self.users.create_index([("user_id", ASCENDING)], unique=True, name="user_id_unique")
            logger.info("Unique index on users.user_id created or already exists")
        except OperationFailure as e:
            logger.info(f"Unique index on users.user_id already exists: {str(e)}")

        try:
            # Interactions collection: compound index on user_id and timestamp
            self.interactions.create_index(
                [("user_id", ASCENDING), ("timestamp", ASCENDING)],
                name="user_id_timestamp"
            )
            logger.info("Compound index on interactions.user_id,timestamp created or already exists")
        except OperationFailure as e:
            logger.info(f"Compound index on interactions.user_id,timestamp already exists: {str(e)}")

        try:
            # Interactions collection: index on input_type
            self.interactions.create_index([("input_type", ASCENDING)], name="input_type")
            logger.info("Index on interactions.input_type created or already exists")
        except OperationFailure as e:
            logger.info(f"Index on interactions.input_type already exists: {str(e)}")

        try:
            # Interactions collection: TTL index on timestamp
            try:
                self.interactions.drop_index("timestamp_1")
                logger.info("Dropped existing timestamp_1 index")
            except OperationFailure as e:
                if "index not found" in str(e):
                    logger.info("No timestamp_1 index to drop")
                else:
                    logger.error(f"Failed to drop timestamp_1 index: {str(e)}")
            self.interactions.create_index(
                [("timestamp", ASCENDING)],
                name="timestamp_1",
                expireAfterSeconds=604800  # 7 days
            )
            logger.info("TTL index on interactions.timestamp created with 7-day expiry")
        except OperationFailure as e:
            logger.error(f"Failed to create timestamp TTL index: {str(e)}")

        try:
            # Prompt cache collection: unique index on key
            self.prompt_cache.create_index([("key", ASCENDING)], unique=True, name="key_1")
            logger.info("Unique index on prompt_cache.key created or already exists")
        except OperationFailure as e:
            logger.info(f"Unique index on prompt_cache.key already exists: {str(e)}")

    def save_user(self, user_data: Dict[str, Any]) -> bool:
        """Save or update user data in the users collection."""
        if self.db is None:
            logger.error("No database connection")
            return False
        try:
            user_id = user_data.get("user_id")
            if not user_id:
                logger.error("No user_id provided in user_data")
                return False
            self.users.update_one(
                {"user_id": user_id},
                {"$set": user_data},
                upsert=True
            )
            logger.info(f"Saved user data for {user_id}")
            return True
        except PyMongoError as e:
            logger.error(f"Error saving user data: {str(e)}", exc_info=True)
            return False

    def get_user(self, user_id: str) -> Dict[str, Any]:
        """Retrieve user data by user_id."""
        if self.db is None:
            logger.error("No database connection")
            return {}
        try:
            user = self.users.find_one({"user_id": user_id})
            return user or {}
        except PyMongoError as e:
            logger.error(f"Error retrieving user {user_id}: {str(e)}", exc_info=True)
            return {}

    def save_interaction(
        self,
        user_id: str,
        input_type: str,
        input_text: str,
        response: str,
        language: str,
        is_audio: bool = False,
        pdf_path: Optional[str] = None
    ) -> bool:
        """Save interaction data to the interactions collection."""
        if self.db is None:
            logger.error("No database connection")
            return False
        try:
            from datetime import datetime
            interaction = {
                "user_id": user_id,
                "input_type": input_type,
                "input_text": input_text,
                "response": response,
                "language": language,
                "is_audio": is_audio,
                "pdf_path": pdf_path,
                "timestamp": datetime.utcnow()
            }
            self.interactions.insert_one(interaction)
            logger.info(f"Saved interaction for user {user_id}, type: {input_type}")
            return True
        except PyMongoError as e:
            logger.error(f"Error saving interaction for user {user_id}: {str(e)}", exc_info=True)
            return False

    def get_diet_plan_prompt(self, language: str) -> Optional[Dict[str, Any]]:
        """Retrieve diet plan prompt for the specified language."""
        if self.db is None:
            logger.error("No database connection")
            return None
        try:
            prompt = self.prompts.find_one({"type": "diet_plan", "language": language})
            return prompt
        except PyMongoError as e:
            logger.error(f"Error retrieving diet plan prompt for language {language}: {str(e)}", exc_info=True)
            return None

    def cache_response(self, key: str, response: Dict[str, Any]) -> bool:
        """Cache a response in the prompt_cache collection."""
        if self.db is None:
            logger.error("No database connection")
            return False
        if not key:
            logger.error("Cannot cache response with null or empty key")
            return False
        try:
            from datetime import datetime
            self.prompt_cache.update_one(
                {"key": key},
                {"$set": {"response": response, "timestamp": datetime.utcnow()}},
                upsert=True
            )
            logger.info(f"Cached response for key {key}")
            return True
        except PyMongoError as e:
            logger.error(f"Error caching response for key {key}: {str(e)}", exc_info=True)
            return False

    def get_cached_response(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached response by key."""
        if self.db is None:
            logger.error("No database connection")
            return None
        try:
            cached = self.prompt_cache.find_one({"key": key})
            return cached.get("response") if cached else None
        except PyMongoError as e:
            logger.error(f"Error retrieving cached response for key {key}: {str(e)}", exc_info=True)
            return None

    def close(self):
        """Close the MongoDB connection."""
        if hasattr(self, "client"):
            self.client.close()
            logger.info("MongoDB connection closed")