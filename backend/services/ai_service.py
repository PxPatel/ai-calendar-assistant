"""
AI Service
Orchestrates AI operations for intent parsing and scheduling
"""
from typing import Optional
import logging

from backend.integrations.gemini_client import GeminiClient
from backend.schemas.user_intent import UserIntent
from backend.prompts.intent_parser import (
    INTENT_PARSING_SYSTEM_PROMPT,
    build_intent_parsing_prompt
)
import config


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AIService:
    """
    AI Service for calendar assistant

    Handles intent parsing and AI-powered scheduling
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """
        Initialize AI service

        Args:
            api_key: Gemini API key (defaults to config.GOOGLE_GEMINI_API_KEY)
            model_name: Model name (defaults to config.GOOGLE_GEMINI_MODEL)
        """
        self.api_key = api_key or config.GOOGLE_GEMINI_API_KEY
        self.model_name = model_name or config.GOOGLE_GEMINI_MODEL

        if not self.api_key:
            raise ValueError(
                "Gemini API key not found. Please set GOOGLE_GEMINI_API_KEY in .env file"
            )

        # Initialize Gemini client
        self.gemini_client = GeminiClient(
            api_key=self.api_key,
            model_name=self.model_name
        )

        logger.info(f"AI Service initialized with model: {self.model_name}")

    def parse_user_intent(self, user_message: str) -> UserIntent:
        """
        Parse user's natural language request into structured UserIntent

        Args:
            user_message: User's natural language request

        Returns:
            UserIntent object with parsed information

        Raises:
            Exception: If parsing fails after retries
        """
        logger.info(f"Parsing user intent: {user_message[:100]}...")

        # Build the prompt
        prompt = build_intent_parsing_prompt(user_message)

        # Try to get JSON response from Gemini
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Get JSON response from Gemini
                response_json = self.gemini_client.generate_json(
                    prompt=prompt,
                    system_prompt=INTENT_PARSING_SYSTEM_PROMPT,
                    max_tokens=1000
                )

                logger.info(f"Parsed intent JSON: {response_json}")

                # Convert JSON to UserIntent object
                intent = UserIntent.from_dict(response_json)

                logger.info(f"Successfully parsed intent: {intent.action} - {intent.task_name}")
                return intent

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    logger.info("Retrying intent parsing...")
                    continue
                else:
                    # Return a default "query" intent on failure
                    logger.error(f"Failed to parse intent after {max_retries} attempts")
                    raise Exception(
                        f"Failed to parse your request. Please try rephrasing. Error: {str(e)[:100]}"
                    )

    def get_client_stats(self) -> dict:
        """Get statistics about AI client usage"""
        return self.gemini_client.get_stats()
