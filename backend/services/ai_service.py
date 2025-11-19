"""
AI Service
Orchestrates AI operations for intent parsing and scheduling
"""
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from backend.integrations.gemini_client import GeminiClient
from backend.schemas.user_intent import UserIntent
from backend.schemas.calendar_event import CalendarEvent
from backend.schemas.schedule_plan import SchedulePlan
from backend.prompts.intent_parser import (
    INTENT_PARSING_SYSTEM_PROMPT,
    build_intent_parsing_prompt
)
from backend.prompts.scheduler import (
    SCHEDULING_SYSTEM_PROMPT,
    build_scheduling_prompt
)
from backend.services.scheduler_service import SchedulerService
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

        # Initialize Scheduler Service
        self.scheduler_service = SchedulerService(timezone=config.TIMEZONE)

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

    def generate_schedule_plan(
        self,
        user_intent: UserIntent,
        calendar_events: List[CalendarEvent]
    ) -> SchedulePlan:
        """
        Generate an optimal scheduling plan using AI

        Args:
            user_intent: Parsed user intent
            calendar_events: Current calendar state

        Returns:
            SchedulePlan with scheduled time blocks

        Raises:
            Exception: If scheduling fails
        """
        logger.info(f"Generating schedule for: {user_intent.task_name} ({user_intent.duration_minutes} min)")

        import pytz
        tz = pytz.timezone(config.TIMEZONE)
        now = datetime.now(tz)

        # Calculate date range
        if user_intent.deadline:
            end_date = user_intent.deadline
        else:
            # Default to 7 days ahead
            end_date = now + timedelta(days=config.DEFAULT_DAYS_AHEAD)

        # Find available slots
        logger.info(f"Finding available slots from {now.date()} to {end_date.date()}")
        available_slots = self.scheduler_service.find_available_slots(
            events=calendar_events,
            start_date=now,
            end_date=end_date,
            min_duration_minutes=config.MIN_BLOCK_SIZE_MINUTES
        )

        if not available_slots:
            raise Exception(
                f"No available time slots found between now and {end_date.strftime('%B %d')}. "
                "Your calendar appears to be fully booked. Consider extending the deadline or moving some flexible events."
            )

        # Check if we can fit the requested duration
        can_fit, total_available = self.scheduler_service.can_fit_duration(
            available_slots=available_slots,
            duration_minutes=user_intent.duration_minutes,
            allow_split=user_intent.can_split
        )

        if not can_fit:
            if total_available == 0:
                raise Exception(
                    f"No available time found. Your calendar is completely booked until {end_date.strftime('%B %d')}."
                )
            elif total_available < user_intent.duration_minutes:
                hours_needed = user_intent.duration_minutes / 60
                hours_available = total_available / 60
                raise Exception(
                    f"Not enough time available. You requested {hours_needed:.1f} hours, "
                    f"but only {hours_available:.1f} hours are available before {end_date.strftime('%B %d')}. "
                    "Options: 1) Extend deadline, 2) Reduce duration, 3) Move flexible events"
                )

        # Get best slots based on preferences
        selected_slots = self.scheduler_service.get_best_slots(
            available_slots=available_slots,
            duration_minutes=user_intent.duration_minutes,
            priority=user_intent.priority,
            preferred_time_of_day=user_intent.preferred_time_of_day,
            allow_split=user_intent.can_split
        )

        if not selected_slots:
            raise Exception(
                "Could not find suitable time slots matching your preferences. "
                "Try adjusting your time-of-day preference or allowing the task to be split."
            )

        # Build prompt for AI
        prompt = build_scheduling_prompt(
            intent=user_intent,
            calendar_events=calendar_events,
            available_slots=selected_slots
        )

        # Get schedule from Gemini
        max_retries = 2
        for attempt in range(max_retries):
            try:
                logger.info(f"Asking AI to generate schedule (attempt {attempt + 1})...")

                response_json = self.gemini_client.generate_json(
                    prompt=prompt,
                    system_prompt=SCHEDULING_SYSTEM_PROMPT,
                    max_tokens=2000
                )

                logger.info(f"AI returned schedule plan: {response_json}")

                # Parse into SchedulePlan
                schedule_plan = SchedulePlan.from_dict(response_json)

                # Validate the plan
                is_valid, error_msg = schedule_plan.validate()
                if not is_valid:
                    logger.error(f"Schedule validation failed: {error_msg}")
                    if attempt < max_retries - 1:
                        logger.info("Retrying with validation error feedback...")
                        prompt += f"\n\nPREVIOUS ATTEMPT FAILED: {error_msg}\nPlease fix and try again."
                        continue
                    else:
                        raise Exception(f"Generated schedule is invalid: {error_msg}")

                # Check for conflicts with existing events
                for block in schedule_plan.scheduled_blocks:
                    start_dt, end_dt = block.to_datetime(self.scheduler_service.timezone)
                    has_conflict, conflicting_event = self.scheduler_service.has_conflict(
                        new_start=start_dt,
                        new_end=end_dt,
                        existing_events=calendar_events
                    )

                    if has_conflict:
                        logger.error(f"Conflict detected with: {conflicting_event.title}")
                        if attempt < max_retries - 1:
                            prompt += f"\n\nCONFLICT DETECTED: Your proposed block overlaps with {conflicting_event.title}. Select different slots."
                            continue
                        else:
                            raise Exception(
                                f"Generated schedule conflicts with existing event: {conflicting_event.title}"
                            )

                logger.info(f"Successfully generated valid schedule with {len(schedule_plan.scheduled_blocks)} blocks")
                return schedule_plan

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")

                if attempt < max_retries - 1:
                    continue
                else:
                    raise Exception(
                        f"Failed to generate schedule after {max_retries} attempts. "
                        f"Error: {str(e)[:200]}"
                    )

        raise Exception("Failed to generate schedule")

    def get_client_stats(self) -> dict:
        """Get statistics about AI client usage"""
        return self.gemini_client.get_stats()
