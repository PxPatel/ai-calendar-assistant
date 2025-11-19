"""
Scheduling logic and conflict detection
Core service for finding available time slots and managing conflicts
"""
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional, Tuple
import pytz
import logging

from backend.schemas.calendar_event import CalendarEvent
import config


logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Service for finding available time slots and detecting conflicts
    """

    def __init__(self, timezone: str = None):
        """
        Initialize scheduler service

        Args:
            timezone: Timezone string (defaults to config.TIMEZONE)
        """
        self.timezone = timezone or config.TIMEZONE
        self.tz = pytz.timezone(self.timezone)
        self.work_hours_start = config.WORK_HOURS_START
        self.work_hours_end = config.WORK_HOURS_END

    def find_available_slots(
        self,
        events: List[CalendarEvent],
        start_date: datetime,
        end_date: datetime,
        min_duration_minutes: int = 30,
        include_weekends: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find available time slots between existing events

        Args:
            events: List of existing CalendarEvent objects
            start_date: Start of date range to search
            end_date: End of date range to search
            min_duration_minutes: Minimum slot duration to include
            include_weekends: Whether to include weekend slots

        Returns:
            List of available slots, each with 'start', 'end', 'duration_minutes'
        """
        logger.info(f"Finding available slots from {start_date.date()} to {end_date.date()}")

        available_slots = []

        # Ensure dates are timezone-aware
        if start_date.tzinfo is None:
            start_date = self.tz.localize(start_date)
        if end_date.tzinfo is None:
            end_date = self.tz.localize(end_date)

        # Filter to only FIXED events (flexible events can be moved)
        fixed_events = [e for e in events if not e.is_flexible]
        logger.info(f"Found {len(fixed_events)} fixed events out of {len(events)} total")

        # Iterate through each day
        current_date = start_date.date()
        end_date_only = end_date.date()

        while current_date <= end_date_only:
            # Skip weekends if requested
            if not include_weekends and current_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
                current_date += timedelta(days=1)
                continue

            # Get events for this day
            day_events = [
                e for e in fixed_events
                if e.start.date() == current_date
            ]

            # Sort events by start time
            day_events.sort(key=lambda e: e.start)

            # Find gaps in the day
            day_start = self.tz.localize(
                datetime.combine(current_date, time(self.work_hours_start, 0))
            )
            day_end = self.tz.localize(
                datetime.combine(current_date, time(self.work_hours_end, 0))
            )

            # Check if current time is in the past
            now = datetime.now(self.tz)
            if day_start < now:
                day_start = now

            # Find slots between events
            previous_end = day_start

            for event in day_events:
                # Gap between previous event end and current event start
                if event.start > previous_end:
                    slot_duration = (event.start - previous_end).total_seconds() / 60

                    if slot_duration >= min_duration_minutes:
                        available_slots.append({
                            'start': previous_end,
                            'end': event.start,
                            'duration_minutes': int(slot_duration)
                        })

                previous_end = max(previous_end, event.end)

            # Check for slot after last event until end of day
            if previous_end < day_end:
                slot_duration = (day_end - previous_end).total_seconds() / 60

                if slot_duration >= min_duration_minutes:
                    available_slots.append({
                        'start': previous_end,
                        'end': day_end,
                        'duration_minutes': int(slot_duration)
                    })

            current_date += timedelta(days=1)

        logger.info(f"Found {len(available_slots)} available slots")
        return available_slots

    def has_conflict(
        self,
        new_start: datetime,
        new_end: datetime,
        existing_events: List[CalendarEvent]
    ) -> Tuple[bool, Optional[CalendarEvent]]:
        """
        Check if a proposed event conflicts with existing events

        Args:
            new_start: Proposed event start time
            new_end: Proposed event end time
            existing_events: List of existing calendar events

        Returns:
            Tuple of (has_conflict: bool, conflicting_event: Optional[CalendarEvent])
        """
        # Only check against FIXED events (flexible events can be moved)
        fixed_events = [e for e in existing_events if not e.is_flexible]

        for event in fixed_events:
            # Check for overlap
            # Events overlap if: new_start < event.end AND new_end > event.start
            if new_start < event.end and new_end > event.start:
                logger.warning(f"Conflict detected with: {event.title}")
                return True, event

        return False, None

    def can_fit_duration(
        self,
        available_slots: List[Dict[str, Any]],
        duration_minutes: int,
        allow_split: bool = True
    ) -> Tuple[bool, int]:
        """
        Check if requested duration can fit in available slots

        Args:
            available_slots: List of available time slots
            duration_minutes: Required duration in minutes
            allow_split: Whether task can be split across multiple slots

        Returns:
            Tuple of (can_fit: bool, available_minutes: int)
        """
        if not allow_split:
            # Need a single slot that's >= duration
            max_slot = max((slot['duration_minutes'] for slot in available_slots), default=0)
            return max_slot >= duration_minutes, max_slot
        else:
            # Can use multiple slots
            total_available = sum(slot['duration_minutes'] for slot in available_slots)
            return total_available >= duration_minutes, total_available

    def format_slots_for_display(self, slots: List[Dict[str, Any]]) -> List[str]:
        """
        Format available slots for human-readable display

        Args:
            slots: List of slot dictionaries

        Returns:
            List of formatted strings
        """
        formatted = []

        for slot in slots:
            start = slot['start']
            end = slot['end']
            duration = slot['duration_minutes']

            # Format day
            day_str = start.strftime('%A, %b %d')

            # Format times
            start_time = start.strftime('%I:%M%p').lstrip('0').lower()
            end_time = end.strftime('%I:%M%p').lstrip('0').lower()

            formatted.append(
                f"{day_str}: {start_time}-{end_time} ({duration} min)"
            )

        return formatted

    def get_best_slots(
        self,
        available_slots: List[Dict[str, Any]],
        duration_minutes: int,
        priority: str = 'normal',
        preferred_time_of_day: str = 'any',
        allow_split: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Select the best available slots based on preferences

        Args:
            available_slots: List of available slots
            duration_minutes: Required duration
            priority: Priority level (low, normal, high, urgent)
            preferred_time_of_day: Time preference (morning, afternoon, evening, any)
            allow_split: Whether to split across multiple slots

        Returns:
            List of selected slots that best fit the requirements
        """
        if not available_slots:
            return []

        # Filter by time of day preference
        if preferred_time_of_day != 'any':
            filtered_slots = []
            for slot in available_slots:
                hour = slot['start'].hour

                if preferred_time_of_day == 'morning' and 6 <= hour < 12:
                    filtered_slots.append(slot)
                elif preferred_time_of_day == 'afternoon' and 12 <= hour < 17:
                    filtered_slots.append(slot)
                elif preferred_time_of_day == 'evening' and 17 <= hour < 22:
                    filtered_slots.append(slot)

            # If no slots match preference, use all slots
            if filtered_slots:
                available_slots = filtered_slots

        # Score slots based on priority and time
        scored_slots = []
        for slot in available_slots:
            score = 0

            # Prefer mornings for high priority tasks
            if priority in ['high', 'urgent']:
                if slot['start'].hour < 12:
                    score += 10
                elif slot['start'].hour < 14:
                    score += 5

            # Prefer larger contiguous blocks
            score += min(slot['duration_minutes'] / 30, 10)  # Max 10 points

            # Prefer earlier in the week
            weekday = slot['start'].weekday()
            score += (7 - weekday)  # Monday gets 6 points, Sunday gets 0

            scored_slots.append((score, slot))

        # Sort by score (descending)
        scored_slots.sort(key=lambda x: x[0], reverse=True)

        # Select slots to fill the duration
        selected_slots = []
        remaining_minutes = duration_minutes

        if not allow_split:
            # Find the best single slot that fits
            for score, slot in scored_slots:
                if slot['duration_minutes'] >= duration_minutes:
                    selected_slots.append(slot)
                    break
        else:
            # Fill with best slots until we have enough time
            for score, slot in scored_slots:
                if remaining_minutes <= 0:
                    break

                selected_slots.append(slot)
                remaining_minutes -= slot['duration_minutes']

        return selected_slots
