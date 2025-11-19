"""
Schedule Plan Schema
Represents AI-generated scheduling plans with time blocks
"""
from dataclasses import dataclass
from datetime import datetime, time
from typing import List, Optional, Dict, Any
import pytz


@dataclass
class ScheduleBlock:
    """
    Represents a single scheduled time block

    Attributes:
        date: Date in YYYY-MM-DD format
        start_time: Start time in HH:MM 24-hour format
        end_time: End time in HH:MM 24-hour format
        task_name: Name/title of the task
        reasoning: Optional AI reasoning for this scheduling choice
    """
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    task_name: str
    reasoning: Optional[str] = None

    @property
    def duration_minutes(self) -> int:
        """Calculate duration in minutes from start_time to end_time"""
        start_hour, start_min = map(int, self.start_time.split(':'))
        end_hour, end_min = map(int, self.end_time.split(':'))

        start_total_mins = start_hour * 60 + start_min
        end_total_mins = end_hour * 60 + end_min

        return end_total_mins - start_total_mins

    def to_datetime(self, timezone: str = 'America/New_York') -> tuple[datetime, datetime]:
        """
        Convert date + time strings to timezone-aware datetime objects

        Args:
            timezone: Timezone string (e.g., 'America/New_York')

        Returns:
            Tuple of (start_datetime, end_datetime)
        """
        tz = pytz.timezone(timezone)

        # Parse date
        year, month, day = map(int, self.date.split('-'))

        # Parse start time
        start_hour, start_min = map(int, self.start_time.split(':'))
        start_dt = datetime(year, month, day, start_hour, start_min)
        start_dt = tz.localize(start_dt)

        # Parse end time
        end_hour, end_min = map(int, self.end_time.split(':'))
        end_dt = datetime(year, month, day, end_hour, end_min)
        end_dt = tz.localize(end_dt)

        return start_dt, end_dt

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'date': self.date,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'task_name': self.task_name,
            'reasoning': self.reasoning,
            'duration_minutes': self.duration_minutes
        }


@dataclass
class SchedulePlan:
    """
    Represents a complete scheduling plan with multiple blocks

    Attributes:
        scheduled_blocks: List of ScheduleBlock objects
        conflicts_resolved: List of conflict resolution notes
        total_scheduled_minutes: Total duration across all blocks
        summary: Optional summary/explanation of the plan
    """
    scheduled_blocks: List[ScheduleBlock]
    conflicts_resolved: List[str] = None
    total_scheduled_minutes: int = 0
    summary: Optional[str] = None

    def __post_init__(self):
        """Calculate total scheduled minutes if not provided"""
        if self.conflicts_resolved is None:
            self.conflicts_resolved = []

        if self.total_scheduled_minutes == 0:
            self.total_scheduled_minutes = sum(
                block.duration_minutes for block in self.scheduled_blocks
            )

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate the schedule plan

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if we have any blocks
        if not self.scheduled_blocks:
            return False, "Schedule plan has no blocks"

        # Check if total duration matches sum of blocks
        calculated_total = sum(block.duration_minutes for block in self.scheduled_blocks)
        if calculated_total != self.total_scheduled_minutes:
            return False, f"Total scheduled minutes mismatch: {self.total_scheduled_minutes} vs {calculated_total}"

        # Check for overlapping blocks
        for i, block1 in enumerate(self.scheduled_blocks):
            for block2 in self.scheduled_blocks[i+1:]:
                # If same date, check for time overlap
                if block1.date == block2.date:
                    start1_hour, start1_min = map(int, block1.start_time.split(':'))
                    end1_hour, end1_min = map(int, block1.end_time.split(':'))
                    start2_hour, start2_min = map(int, block2.start_time.split(':'))
                    end2_hour, end2_min = map(int, block2.end_time.split(':'))

                    start1 = start1_hour * 60 + start1_min
                    end1 = end1_hour * 60 + end1_min
                    start2 = start2_hour * 60 + start2_min
                    end2 = end2_hour * 60 + end2_min

                    # Check overlap
                    if not (end1 <= start2 or end2 <= start1):
                        return False, f"Blocks overlap on {block1.date}: {block1.task_name} and {block2.task_name}"

        return True, None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'scheduled_blocks': [block.to_dict() for block in self.scheduled_blocks],
            'conflicts_resolved': self.conflicts_resolved,
            'total_scheduled_minutes': self.total_scheduled_minutes,
            'summary': self.summary
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SchedulePlan':
        """Create SchedulePlan from dictionary"""
        blocks = [
            ScheduleBlock(**block_data)
            for block_data in data.get('scheduled_blocks', [])
        ]

        return cls(
            scheduled_blocks=blocks,
            conflicts_resolved=data.get('conflicts_resolved', []),
            total_scheduled_minutes=data.get('total_scheduled_minutes', 0),
            summary=data.get('summary')
        )

    def get_readable_summary(self) -> str:
        """Get human-readable summary of the schedule"""
        if not self.scheduled_blocks:
            return "No time blocks scheduled"

        lines = [f"=Å Scheduled {len(self.scheduled_blocks)} time block(s):"]

        for i, block in enumerate(self.scheduled_blocks, 1):
            # Format date nicely
            year, month, day = map(int, block.date.split('-'))
            date_obj = datetime(year, month, day)
            day_name = date_obj.strftime('%A, %b %d')

            # Format times
            start_hour, start_min = map(int, block.start_time.split(':'))
            end_hour, end_min = map(int, block.end_time.split(':'))

            # Convert to 12-hour format
            start_period = 'AM' if start_hour < 12 else 'PM'
            start_display_hour = start_hour if start_hour <= 12 else start_hour - 12
            if start_display_hour == 0:
                start_display_hour = 12

            end_period = 'AM' if end_hour < 12 else 'PM'
            end_display_hour = end_hour if end_hour <= 12 else end_hour - 12
            if end_display_hour == 0:
                end_display_hour = 12

            time_range = f"{start_display_hour}:{start_min:02d}{start_period} - {end_display_hour}:{end_min:02d}{end_period}"

            lines.append(f"  {i}. {day_name} @ {time_range} ({block.duration_minutes} min)")
            if block.reasoning:
                lines.append(f"     =¡ {block.reasoning}")

        if self.summary:
            lines.append(f"\n{self.summary}")

        return '\n'.join(lines)
