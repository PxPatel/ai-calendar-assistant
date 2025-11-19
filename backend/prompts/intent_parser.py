"""
Intent Parsing Prompts
Prompts for parsing user's natural language into structured UserIntent
"""
from datetime import datetime, timedelta
import pytz
import config


# System prompt for intent parsing
INTENT_PARSING_SYSTEM_PROMPT = """You are an intelligent calendar assistant that parses user requests into structured JSON.

Your job is to understand natural language scheduling requests and extract:
1. Action type (schedule_task, create_event, modify_event, delete_event, query_calendar)
2. Task/event name
3. Duration in minutes
4. Deadline (if mentioned)
5. Whether the task can be split into multiple blocks
6. Priority level (low, normal, high, urgent)
7. Time preferences (morning, afternoon, evening, any)
8. Specific datetime (if user requests exact time)
9. Attendees (for meetings)

IMPORTANT RULES:
- Return ONLY valid JSON, no markdown, no explanations, no code blocks
- All datetime values must be in ISO 8601 format with timezone
- If duration is not specified, estimate based on task type:
  - Homework/assignments: 120 minutes (2 hours)
  - Meetings: 30 minutes
  - Study sessions: 90 minutes
  - Exercise/gym: 60 minutes
  - Quick tasks: 30 minutes
- Priority defaults to "normal" unless explicitly stated
- can_split defaults to true for tasks over 90 minutes, false for meetings
- If deadline is relative (e.g., "by Friday"), convert to absolute datetime
- For "schedule_task": used when user wants AI to find time slots
- For "create_event": used when user specifies exact date/time
- Current date and time context will be provided in the user message

Output JSON schema:
{
  "action": "schedule_task" | "create_event" | "modify_event" | "delete_event" | "query_calendar",
  "task_name": "string",
  "duration_minutes": number,
  "deadline": "ISO 8601 datetime or null",
  "can_split": boolean,
  "priority": "low" | "normal" | "high" | "urgent",
  "preferred_time_of_day": "morning" | "afternoon" | "evening" | "any",
  "specific_datetime": "ISO 8601 datetime or null",
  "attendees": ["email1", "email2"] or null,
  "notes": "string or null"
}
"""


def build_intent_parsing_prompt(user_message: str) -> str:
    """
    Build the complete intent parsing prompt with examples

    Args:
        user_message: User's natural language request

    Returns:
        Complete prompt with context and examples
    """
    # Get current datetime with timezone
    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.now(tz)
    current_time_str = now.strftime('%Y-%m-%d %I:%M %p %Z')

    # Day of week for relative date calculations
    current_day = now.strftime('%A')

    prompt = f"""Current date and time: {current_time_str} ({current_day})

Parse the following user request into structured JSON:

FEW-SHOT EXAMPLES:

User: "Schedule 3 hours for my CS homework due Friday"
Output:
{{
  "action": "schedule_task",
  "task_name": "CS homework",
  "duration_minutes": 180,
  "deadline": "{get_next_weekday_iso(now, 'Friday', end_of_day=True)}",
  "can_split": true,
  "priority": "normal",
  "preferred_time_of_day": "any",
  "specific_datetime": null,
  "attendees": null,
  "notes": null
}}

User: "Add a meeting with Prof. Smith tomorrow at 2pm for 30 minutes"
Output:
{{
  "action": "create_event",
  "task_name": "Meeting with Prof. Smith",
  "duration_minutes": 30,
  "deadline": null,
  "can_split": false,
  "priority": "normal",
  "preferred_time_of_day": "any",
  "specific_datetime": "{get_tomorrow_at_time(now, 14, 0)}",
  "attendees": null,
  "notes": null
}}

User: "I need 5 hours for my AI project before Monday, high priority"
Output:
{{
  "action": "schedule_task",
  "task_name": "AI project",
  "duration_minutes": 300,
  "deadline": "{get_next_weekday_iso(now, 'Monday', end_of_day=False)}",
  "can_split": true,
  "priority": "high",
  "preferred_time_of_day": "any",
  "specific_datetime": null,
  "attendees": null,
  "notes": null
}}

User: "Block 2 hours for gym this week, preferably mornings"
Output:
{{
  "action": "schedule_task",
  "task_name": "Gym",
  "duration_minutes": 120,
  "deadline": "{get_end_of_week(now)}",
  "can_split": true,
  "priority": "normal",
  "preferred_time_of_day": "morning",
  "specific_datetime": null,
  "attendees": null,
  "notes": null
}}

User: "Study for finals tomorrow"
Output:
{{
  "action": "schedule_task",
  "task_name": "Study for finals",
  "duration_minutes": 120,
  "deadline": "{get_end_of_tomorrow(now)}",
  "can_split": true,
  "priority": "high",
  "preferred_time_of_day": "any",
  "specific_datetime": null,
  "attendees": null,
  "notes": null
}}

NOW PARSE THIS REQUEST:
User: "{user_message}"
Output:"""

    return prompt


# Helper functions for generating example datetimes
def get_next_weekday_iso(current_dt: datetime, target_day: str, end_of_day: bool = False) -> str:
    """Get next occurrence of a weekday in ISO format"""
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    current_weekday = current_dt.weekday()
    target_weekday = days.index(target_day)

    days_ahead = (target_weekday - current_weekday) % 7
    if days_ahead == 0:
        days_ahead = 7  # Next week if it's the same day

    target_date = current_dt + timedelta(days=days_ahead)

    if end_of_day:
        target_date = target_date.replace(hour=23, minute=59, second=0, microsecond=0)
    else:
        target_date = target_date.replace(hour=9, minute=0, second=0, microsecond=0)

    return target_date.isoformat()


def get_tomorrow_at_time(current_dt: datetime, hour: int, minute: int) -> str:
    """Get tomorrow at specific time in ISO format"""
    tomorrow = current_dt + timedelta(days=1)
    target_dt = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target_dt.isoformat()


def get_end_of_week(current_dt: datetime) -> str:
    """Get end of current week (Sunday 11:59pm) in ISO format"""
    days_until_sunday = (6 - current_dt.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7

    end_of_week = current_dt + timedelta(days=days_until_sunday)
    end_of_week = end_of_week.replace(hour=23, minute=59, second=0, microsecond=0)
    return end_of_week.isoformat()


def get_end_of_tomorrow(current_dt: datetime) -> str:
    """Get end of tomorrow in ISO format"""
    tomorrow = current_dt + timedelta(days=1)
    end_of_tomorrow = tomorrow.replace(hour=23, minute=59, second=0, microsecond=0)
    return end_of_tomorrow.isoformat()
