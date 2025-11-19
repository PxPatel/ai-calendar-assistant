"""
AI Scheduling Prompts
Prompts for generating optimal scheduling plans using AI
"""
from datetime import datetime
from typing import List, Dict, Any
import pytz

from backend.schemas.calendar_event import CalendarEvent
from backend.schemas.user_intent import UserIntent
import config


# System prompt for scheduling
SCHEDULING_SYSTEM_PROMPT = """You are an expert scheduling assistant that creates optimal time-blocking plans.

Your job is to analyze a user's task requirements and calendar state, then select the best available time slots to schedule the task.

RULES (MUST FOLLOW):
1. NEVER overlap with [FIXED] events - these cannot be moved
2. You CAN suggest moving [FLEXIBLE] events if absolutely necessary
3. Prefer 90-120 minute blocks for deep work (optimal for focus)
4. ALWAYS respect deadlines - schedule ALL blocks before the deadline
5. Consider priority levels:
   - HIGH/URGENT: Give best time slots (mornings/early afternoon when focus is peak)
   - NORMAL: Good time slots (avoid very late or very early)
   - LOW: Use remaining slots
6. Avoid very late nights (after 10pm) and very early mornings (before 7am)
7. If task requires 3+ hours, split into multiple sessions (90-120 min each)
8. Leave reasonable breaks between sessions (at least 15 minutes)
9. Consider task type:
   - Mental work (studying, coding): Prefer morning/early afternoon
   - Physical work (gym, errands): Any time is fine
   - Creative work: Prefer when energy is high
10. If not enough time available, say so clearly - don't force impossible schedules

OUTPUT FORMAT:
- Return ONLY valid JSON, no markdown code blocks, no explanations outside JSON
- Use the exact schema shown in examples
- Provide brief reasoning for each block placement
- Include a summary explaining the overall strategy

IMPORTANT:
- All dates must be in YYYY-MM-DD format
- All times must be in 24-hour HH:MM format
- Only select from the provided available slots
- total_scheduled_minutes must equal the sum of all block durations
"""


def format_calendar_state(events: List[CalendarEvent]) -> str:
    """
    Format calendar events into readable text grouped by day

    Args:
        events: List of CalendarEvent objects

    Returns:
        Formatted string describing calendar state
    """
    if not events:
        return "Calendar is empty - no existing events"

    # Group events by date
    events_by_date = {}
    for event in events:
        date_key = event.start.strftime('%Y-%m-%d')
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    # Format output
    lines = ["CURRENT CALENDAR:"]
    for date_key in sorted(events_by_date.keys()):
        day_events = events_by_date[date_key]
        # Get day name
        year, month, day = map(int, date_key.split('-'))
        date_obj = datetime(year, month, day)
        day_name = date_obj.strftime('%A, %B %d')

        lines.append(f"\n{day_name}:")

        # Sort events by start time
        day_events.sort(key=lambda e: e.start)

        for event in day_events:
            start_time = event.start.strftime('%I:%M%p').lstrip('0')
            end_time = event.end.strftime('%I:%M%p').lstrip('0')
            event_type = '[FIXED]' if not event.is_flexible else '[FLEXIBLE]'

            lines.append(f"  • {start_time}-{end_time} {event.title} {event_type}")

    return '\n'.join(lines)


def format_available_slots(slots: List[Dict[str, Any]]) -> str:
    """
    Format available time slots for the AI

    Args:
        slots: List of slot dictionaries with 'start', 'end', 'duration_minutes'

    Returns:
        Formatted string listing available slots
    """
    if not slots:
        return "No available slots found"

    lines = ["AVAILABLE TIME SLOTS:"]

    for i, slot in enumerate(slots, 1):
        start = slot['start']
        end = slot['end']
        duration = slot['duration_minutes']

        date_str = start.strftime('%Y-%m-%d (%A)')
        start_time = start.strftime('%H:%M')
        end_time = end.strftime('%H:%M')

        lines.append(f"{i}. {date_str} {start_time}-{end_time} ({duration} min)")

    return '\n'.join(lines)


def build_scheduling_prompt(
    intent: UserIntent,
    calendar_events: List[CalendarEvent],
    available_slots: List[Dict[str, Any]]
) -> str:
    """
    Build complete scheduling prompt for AI

    Args:
        intent: User's parsed intent
        calendar_events: Current calendar state
        available_slots: Available time slots found by scheduler

    Returns:
        Complete prompt string for Gemini
    """
    # Get timezone
    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.now(tz)

    # Format calendar and slots
    calendar_str = format_calendar_state(calendar_events)
    slots_str = format_available_slots(available_slots)

    # Build task requirements section
    task_requirements = f"""TASK TO SCHEDULE:
- Task Name: {intent.task_name}
- Duration Needed: {intent.duration_minutes} minutes ({intent.duration_minutes/60:.1f} hours)
- Priority: {intent.priority.upper()}
- Can Split: {'Yes' if intent.can_split else 'No (must be one continuous block)'}
- Preferred Time: {intent.preferred_time_of_day}"""

    if intent.deadline:
        deadline_str = intent.deadline.strftime('%Y-%m-%d %I:%M%p')
        task_requirements += f"\n- Deadline: {deadline_str} (ALL blocks must be scheduled before this)"

    if intent.notes:
        task_requirements += f"\n- Notes: {intent.notes}"

    # Build the full prompt with few-shot examples
    prompt = f"""Current Date/Time: {now.strftime('%Y-%m-%d %H:%M')} ({now.strftime('%A')})

{task_requirements}

{calendar_str}

{slots_str}

---

EXAMPLE 1:
Task: Schedule 180 minutes for homework, due Friday, can split, priority normal
Available: Tuesday 2pm-4pm (120min), Wednesday 10am-12pm (120min), Thursday 3pm-5pm (120min)

Response:
{{
  "scheduled_blocks": [
    {{
      "date": "2024-11-19",
      "start_time": "14:00",
      "end_time": "15:30",
      "task_name": "Homework (Session 1)",
      "reasoning": "Tuesday afternoon after lunch - good focus time, 90 min block"
    }},
    {{
      "date": "2024-11-20",
      "start_time": "10:00",
      "end_time": "11:30",
      "task_name": "Homework (Session 2)",
      "reasoning": "Wednesday morning - peak mental energy, completes before Friday deadline"
    }}
  ],
  "conflicts_resolved": [],
  "total_scheduled_minutes": 180,
  "summary": "Split homework into 2 productive 90-minute sessions across Tuesday and Wednesday, both before the Friday deadline. Scheduled during high-focus times to maximize efficiency."
}}

EXAMPLE 2:
Task: Schedule 90 minutes for gym, priority normal, can split, preferred time morning
Available: Monday 8am-10am (120min), Monday 2pm-4pm (120min), Tuesday 8am-9am (60min)

Response:
{{
  "scheduled_blocks": [
    {{
      "date": "2024-11-18",
      "start_time": "08:00",
      "end_time": "09:30",
      "task_name": "Gym Workout",
      "reasoning": "Monday morning as preferred - energizing way to start the day"
    }}
  ],
  "conflicts_resolved": [],
  "total_scheduled_minutes": 90,
  "summary": "Scheduled gym session Monday morning to match user's time preference. Single 90-minute block is ideal for a complete workout."
}}

---

NOW CREATE YOUR SCHEDULING PLAN:
Analyze the task requirements, current calendar, and available slots above. Select the optimal time blocks from the available slots to schedule this task.

Return your response as JSON only (no markdown, no code blocks):"""

    return prompt
