"""
User Intent Schema
Represents parsed user intent from natural language requests
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Literal


# Type definitions
ActionType = Literal['schedule_task', 'create_event', 'modify_event', 'delete_event', 'query_calendar']
PriorityLevel = Literal['low', 'normal', 'high', 'urgent']
TimePreference = Literal['morning', 'afternoon', 'evening', 'any']


@dataclass
class UserIntent:
    """
    Represents parsed user intent from natural language

    Attributes:
        action: Type of action requested (schedule_task, create_event, etc.)
        task_name: Name/title of the task or event
        duration_minutes: Duration in minutes (0 if not applicable)
        deadline: Deadline datetime (timezone-aware) if specified
        can_split: Whether task can be split into multiple blocks
        priority: Priority level (low, normal, high, urgent)
        preferred_time_of_day: Time preference (morning, afternoon, evening, any)
        specific_datetime: Specific date/time if user requested exact scheduling
        attendees: List of attendees for meetings
        notes: Additional notes or context
    """
    action: ActionType
    task_name: str
    duration_minutes: int = 0
    deadline: Optional[datetime] = None
    can_split: bool = True
    priority: PriorityLevel = 'normal'
    preferred_time_of_day: TimePreference = 'any'
    specific_datetime: Optional[datetime] = None
    attendees: Optional[list[str]] = None
    notes: Optional[str] = None

    def __post_init__(self):
        """Validate the intent after initialization"""
        # Validate duration if it's a task scheduling action
        if self.action in ['schedule_task', 'create_event']:
            if self.duration_minutes <= 0:
                raise ValueError(f"duration_minutes must be positive for {self.action}, got {self.duration_minutes}")

        # Validate deadline is in the future if specified
        if self.deadline and self.deadline < datetime.now(self.deadline.tzinfo):
            raise ValueError(f"deadline must be in the future, got {self.deadline}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'action': self.action,
            'task_name': self.task_name,
            'duration_minutes': self.duration_minutes,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'can_split': self.can_split,
            'priority': self.priority,
            'preferred_time_of_day': self.preferred_time_of_day,
            'specific_datetime': self.specific_datetime.isoformat() if self.specific_datetime else None,
            'attendees': self.attendees,
            'notes': self.notes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserIntent':
        """Create UserIntent from dictionary"""
        from dateutil import parser

        # Parse datetime fields if they exist
        if data.get('deadline'):
            data['deadline'] = parser.parse(data['deadline'])
        if data.get('specific_datetime'):
            data['specific_datetime'] = parser.parse(data['specific_datetime'])

        return cls(**data)

    def get_readable_summary(self) -> str:
        """Get human-readable summary of the intent"""
        parts = [f"Action: {self.action}"]
        parts.append(f"Task: {self.task_name}")

        if self.duration_minutes > 0:
            hours = self.duration_minutes // 60
            mins = self.duration_minutes % 60
            if hours > 0 and mins > 0:
                parts.append(f"Duration: {hours}h {mins}m")
            elif hours > 0:
                parts.append(f"Duration: {hours}h")
            else:
                parts.append(f"Duration: {mins}m")

        if self.deadline:
            parts.append(f"Deadline: {self.deadline.strftime('%Y-%m-%d %I:%M %p')}")

        if self.specific_datetime:
            parts.append(f"Scheduled for: {self.specific_datetime.strftime('%Y-%m-%d %I:%M %p')}")

        if self.priority != 'normal':
            parts.append(f"Priority: {self.priority}")

        if self.preferred_time_of_day != 'any':
            parts.append(f"Preferred time: {self.preferred_time_of_day}")

        if self.can_split:
            parts.append("Can be split into multiple blocks")

        if self.attendees:
            parts.append(f"Attendees: {', '.join(self.attendees)}")

        return " | ".join(parts)
