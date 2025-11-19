"""
Calendar Event Schema
Represents a calendar event with support for flexible/fixed classification
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import pytz


@dataclass
class CalendarEvent:
    """
    Represents a calendar event

    Attributes:
        id: Unique identifier from Google Calendar
        title: Event title/summary
        start: Start datetime (timezone-aware)
        end: End datetime (timezone-aware)
        description: Event description
        is_flexible: Whether event can be rescheduled (determined by [FIXED]/[FLEXIBLE] tags)
        event_type: Type classification (e.g., 'work', 'class', 'personal')
    """
    id: str
    title: str
    start: datetime
    end: datetime
    description: Optional[str] = None
    is_flexible: bool = False
    event_type: Optional[str] = None

    @property
    def duration_minutes(self) -> int:
        """Calculate duration in minutes"""
        delta = self.end - self.start
        return int(delta.total_seconds() / 60)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'title': self.title,
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
            'description': self.description,
            'is_flexible': self.is_flexible,
            'event_type': self.event_type,
            'duration_minutes': self.duration_minutes
        }

    @classmethod
    def from_google_event(cls, google_event: Dict[str, Any], timezone: str = 'America/New_York') -> 'CalendarEvent':
        """
        Create CalendarEvent from Google Calendar API response

        Args:
            google_event: Event dict from Google Calendar API
            timezone: Default timezone if event doesn't specify one

        Returns:
            CalendarEvent instance
        """
        from dateutil import parser

        # Extract basic info
        event_id = google_event.get('id', '')
        title = google_event.get('summary', 'Untitled Event')
        description = google_event.get('description', '')

        # Parse datetime - handle both all-day and timed events
        start_data = google_event.get('start', {})
        end_data = google_event.get('end', {})

        tz = pytz.timezone(timezone)

        # Check if it's an all-day event
        if 'date' in start_data:
            # All-day event - parse date and set to midnight
            start_dt = parser.parse(start_data['date'])
            end_dt = parser.parse(end_data['date'])
            # Make timezone-aware
            start_dt = tz.localize(start_dt.replace(hour=0, minute=0, second=0))
            end_dt = tz.localize(end_dt.replace(hour=23, minute=59, second=59))
        else:
            # Timed event - parse datetime
            start_dt = parser.parse(start_data.get('dateTime', ''))
            end_dt = parser.parse(end_data.get('dateTime', ''))

            # Ensure timezone-aware
            if start_dt.tzinfo is None:
                start_dt = tz.localize(start_dt)
            if end_dt.tzinfo is None:
                end_dt = tz.localize(end_dt)

        # Determine if flexible based on description tags
        is_flexible = False
        if description:
            desc_lower = description.lower()
            if '[flexible]' in desc_lower:
                is_flexible = True
            elif '[fixed]' in desc_lower:
                is_flexible = False

        # Extract event type if specified in description
        event_type = None
        if description:
            if '[work]' in description.lower():
                event_type = 'work'
            elif '[class]' in description.lower():
                event_type = 'class'
            elif '[personal]' in description.lower():
                event_type = 'personal'

        return cls(
            id=event_id,
            title=title,
            start=start_dt,
            end=end_dt,
            description=description,
            is_flexible=is_flexible,
            event_type=event_type
        )
