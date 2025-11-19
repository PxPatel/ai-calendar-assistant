"""
Google Calendar API Integration
Handles authentication and interaction with Google Calendar API
"""
import os
import pickle
from datetime import datetime, timedelta
from typing import List, Optional
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

from backend.schemas.calendar_event import CalendarEvent
import config


# Scopes required for Google Calendar access
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Suppress googleapiclient discovery cache warnings
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)


class GoogleCalendarClient:
    """
    Google Calendar API wrapper

    Handles OAuth authentication and calendar operations
    """

    def __init__(self, credentials_file: str = None, token_file: str = None):
        """
        Initialize the Google Calendar client

        Args:
            credentials_file: Path to credentials.json (default from config)
            token_file: Path to token.pickle (default from config)
        """
        self.credentials_file = credentials_file or config.CREDENTIALS_FILE
        self.token_file = token_file or config.TOKEN_FILE
        self.creds: Optional[Credentials] = None
        self.service = None
        self.timezone = config.TIMEZONE

    def authenticate(self) -> bool:
        """
        Authenticate with Google Calendar API using OAuth

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Check if token.pickle exists
            if os.path.exists(self.token_file):
                with open(self.token_file, 'rb') as token:
                    self.creds = pickle.load(token)

            # If credentials are invalid or don't exist, refresh or get new ones
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    # Refresh expired credentials
                    self.creds.refresh(Request())
                else:
                    # Get new credentials via OAuth flow
                    if not os.path.exists(self.credentials_file):
                        raise FileNotFoundError(
                            f"Credentials file not found: {self.credentials_file}\n"
                            f"Please download credentials.json from Google Cloud Console"
                        )

                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES
                    )
                    self.creds = flow.run_local_server(port=0)

                # Save credentials for future use
                with open(self.token_file, 'wb') as token:
                    pickle.dump(self.creds, token)

            # Build the service (cache_discovery=False to suppress warnings)
            self.service = build('calendar', 'v3', credentials=self.creds, cache_discovery=False)
            return True

        except FileNotFoundError as e:
            print(f"Error: {e}")
            return False
        except Exception as e:
            print(f"Authentication error: {e}")
            return False

    def get_events(
        self,
        days_ahead: int = 7,
        calendar_id: str = 'primary',
        max_results: int = 100
    ) -> List[CalendarEvent]:
        """
        Fetch upcoming events from Google Calendar

        Args:
            days_ahead: Number of days to fetch events for
            calendar_id: Calendar ID (default 'primary' for main calendar)
            max_results: Maximum number of events to return

        Returns:
            List of CalendarEvent objects
        """
        if not self.service:
            if not self.authenticate():
                raise Exception("Failed to authenticate with Google Calendar")

        try:
            # Calculate time range
            tz = pytz.timezone(self.timezone)
            now = datetime.now(tz)
            time_min = now.isoformat()
            time_max = (now + timedelta(days=days_ahead)).isoformat()

            # Fetch events from Google Calendar API
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            google_events = events_result.get('items', [])

            # Parse events into our CalendarEvent schema
            calendar_events = []
            for event in google_events:
                try:
                    parsed_event = self.parse_event(event)
                    calendar_events.append(parsed_event)
                except Exception as e:
                    print(f"Error parsing event {event.get('id')}: {e}")
                    continue

            return calendar_events

        except HttpError as error:
            print(f"An error occurred: {error}")
            return []
        except Exception as e:
            print(f"Error fetching events: {e}")
            return []

    def parse_event(self, google_event: dict) -> CalendarEvent:
        """
        Parse Google Calendar event into CalendarEvent schema

        Args:
            google_event: Raw event dict from Google Calendar API

        Returns:
            CalendarEvent object
        """
        return CalendarEvent.from_google_event(google_event, timezone=self.timezone)

    def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        description: str = '',
        attendees: List[str] = None,
        calendar_id: str = 'primary'
    ) -> Optional[CalendarEvent]:
        """
        Create a new event in Google Calendar

        Args:
            title: Event title
            start: Start datetime (timezone-aware)
            end: End datetime (timezone-aware)
            description: Event description
            attendees: List of attendee email addresses
            calendar_id: Calendar ID to create event in

        Returns:
            Created CalendarEvent or None if failed
        """
        if not self.service:
            if not self.authenticate():
                raise Exception("Failed to authenticate with Google Calendar")

        try:
            event_body = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start.isoformat(),
                    'timeZone': self.timezone,
                },
                'end': {
                    'dateTime': end.isoformat(),
                    'timeZone': self.timezone,
                },
            }

            # Add attendees if provided
            if attendees:
                event_body['attendees'] = [{'email': email} for email in attendees]

            # Create the event
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()

            return self.parse_event(event)

        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
        except Exception as e:
            print(f"Error creating event: {e}")
            return None

    def delete_event(self, event_id: str, calendar_id: str = 'primary') -> bool:
        """
        Delete an event from Google Calendar

        Args:
            event_id: ID of the event to delete
            calendar_id: Calendar ID

        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            if not self.authenticate():
                raise Exception("Failed to authenticate with Google Calendar")

        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            return True

        except HttpError as error:
            print(f"An error occurred: {error}")
            return False
        except Exception as e:
            print(f"Error deleting event: {e}")
            return False

    def create_events_from_plan(
        self,
        schedule_plan,  # SchedulePlan object
        user_intent,  # UserIntent object
        calendar_id: str = 'primary'
    ) -> dict:
        """
        Create multiple calendar events from a SchedulePlan

        Args:
            schedule_plan: SchedulePlan with time blocks
            user_intent: Original user intent for context
            calendar_id: Calendar ID to create events in

        Returns:
            Dictionary with 'created_ids', 'failed_blocks', 'success_count'
        """
        from backend.schemas.schedule_plan import SchedulePlan, ScheduleBlock
        from backend.schemas.user_intent import UserIntent

        if not self.service:
            if not self.authenticate():
                raise Exception("Failed to authenticate with Google Calendar")

        created_ids = []
        failed_blocks = []

        for i, block in enumerate(schedule_plan.scheduled_blocks, 1):
            try:
                # Convert block times to datetime
                start_dt, end_dt = block.to_datetime(self.timezone)

                # Build description
                total_blocks = len(schedule_plan.scheduled_blocks)
                description_parts = [
                    "[FLEXIBLE]",  # Mark as flexible so we can reschedule if needed
                    f"\nPart {i} of {total_blocks}",
                    f"Task: {user_intent.task_name}",
                    f"Priority: {user_intent.priority.upper()}",
                ]

                if user_intent.deadline:
                    description_parts.append(
                        f"Deadline: {user_intent.deadline.strftime('%Y-%m-%d %I:%M%p')}"
                    )

                if block.reasoning:
                    description_parts.append(f"\n💡 {block.reasoning}")

                if user_intent.notes:
                    description_parts.append(f"\nNotes: {user_intent.notes}")

                description = "\n".join(description_parts)

                # Create event
                event_body = {
                    'summary': block.task_name,
                    'description': description,
                    'start': {
                        'dateTime': start_dt.isoformat(),
                        'timeZone': self.timezone,
                    },
                    'end': {
                        'dateTime': end_dt.isoformat(),
                        'timeZone': self.timezone,
                    },
                    'colorId': '10',  # Green color for flexible events
                }

                # Add attendees if specified
                if user_intent.attendees:
                    event_body['attendees'] = [{'email': email} for email in user_intent.attendees]

                # Insert event
                event = self.service.events().insert(
                    calendarId=calendar_id,
                    body=event_body
                ).execute()

                created_ids.append(event.get('id'))
                print(f"✓ Created event: {block.task_name} on {block.date}")

            except Exception as e:
                print(f"✗ Failed to create event for {block.date} {block.start_time}: {e}")
                failed_blocks.append({
                    'block': block,
                    'error': str(e)
                })

        return {
            'created_ids': created_ids,
            'failed_blocks': failed_blocks,
            'success_count': len(created_ids),
            'total_blocks': len(schedule_plan.scheduled_blocks)
        }
