"""
AI Calendar Assistant - Streamlit Web App
Main UI for the intelligent scheduling assistant
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pytz

from backend.integrations.google_calendar import GoogleCalendarClient
from backend.services.ai_service import AIService
import config


# Configure the page
st.set_page_config(
    page_title="AI Calendar Assistant",
    page_icon="📅",
    layout="wide"
)


# Initialize session state
def init_session_state():
    """Initialize Streamlit session state variables"""
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    if 'calendar_events' not in st.session_state:
        st.session_state.calendar_events = []

    if 'calendar_client' not in st.session_state:
        st.session_state.calendar_client = None

    if 'ai_service' not in st.session_state:
        st.session_state.ai_service = None

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    # Phase 2: Scheduling state
    if 'proposed_schedule' not in st.session_state:
        st.session_state.proposed_schedule = None

    if 'current_intent' not in st.session_state:
        st.session_state.current_intent = None

    if 'awaiting_confirmation' not in st.session_state:
        st.session_state.awaiting_confirmation = False


def initialize_clients():
    """Initialize Google Calendar and AI Service clients"""
    try:
        # Initialize Google Calendar client
        if st.session_state.calendar_client is None:
            st.session_state.calendar_client = GoogleCalendarClient()

        # Initialize AI Service
        if st.session_state.ai_service is None:
            st.session_state.ai_service = AIService()

        return True
    except Exception as e:
        st.error(f"Error initializing clients: {e}")
        return False


def authenticate_calendar():
    """Authenticate with Google Calendar"""
    if not st.session_state.authenticated:
        try:
            with st.spinner("Authenticating with Google Calendar..."):
                success = st.session_state.calendar_client.authenticate()
                if success:
                    st.session_state.authenticated = True
                    st.success("✅ Successfully authenticated with Google Calendar!")
                    return True
                else:
                    st.error("❌ Failed to authenticate. Please check your credentials.json file.")
                    return False
        except Exception as e:
            st.error(f"Authentication error: {e}")
            return False
    return True


def load_calendar_events():
    """Load events from Google Calendar"""
    try:
        with st.spinner("Loading calendar events..."):
            events = st.session_state.calendar_client.get_events(
                days_ahead=config.DEFAULT_DAYS_AHEAD
            )
            st.session_state.calendar_events = events
            return events
    except Exception as e:
        st.error(f"Error loading calendar events: {e}")
        return []


def get_calendar_email():
    """Get the primary calendar email address"""
    try:
        if st.session_state.calendar_client and st.session_state.calendar_client.service:
            calendar_list = st.session_state.calendar_client.service.calendarList().get(
                calendarId='primary'
            ).execute()
            return calendar_list.get('id', None)
    except Exception as e:
        print(f"Error getting calendar email: {e}")
    return None


def display_calendar_view():
    """Display calendar events in the left column"""
    st.header("📅 Your Calendar")

    # View toggle and refresh button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        view_mode = st.selectbox(
            "View",
            ["Embedded", "Table"],
            label_visibility="collapsed",
            key="calendar_view_mode"
        )
    with col2:
        if st.button("🔄 Refresh"):
            load_calendar_events()
            st.rerun()

    # Display embedded calendar or table based on view mode
    if view_mode == "Embedded":
        # Get calendar email/ID
        calendar_email = get_calendar_email()

        if calendar_email:
            # Construct Google Calendar embed URL
            # Use simple mode with current week view
            embed_url = f"https://calendar.google.com/calendar/embed?src={calendar_email}&mode=WEEK&showTitle=0&showNav=1&showDate=1&showPrint=0&showTabs=0&showCalendars=0&showTz=0"

            # Display embedded calendar
            st.components.v1.iframe(
                src=embed_url,
                height=config.CALENDAR_EMBED_HEIGHT,
                scrolling=True
            )
            st.caption("🔵 Your Google Calendar (Week View)")
        else:
            st.warning("⚠️ Unable to load embedded calendar. Showing table view instead.")
            display_calendar_table()
    else:
        display_calendar_table()


def display_calendar_table():
    """Display calendar events as a table"""
    if not st.session_state.calendar_events:
        st.info("No upcoming events found. Click 'Refresh' to load events.")
    else:
        # Prepare data for display
        event_data = []
        for event in st.session_state.calendar_events:
            event_data.append({
                'Date': event.start.strftime('%Y-%m-%d'),
                'Time': f"{event.start.strftime('%I:%M %p')} - {event.end.strftime('%I:%M %p')}",
                'Title': event.title,
                'Duration': f"{event.duration_minutes} min",
                'Type': '🔴 Fixed' if not event.is_flexible else '🟢 Flexible'
            })

        # Create DataFrame
        df = pd.DataFrame(event_data)

        # Display as table
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True
        )

        st.caption(f"Showing {len(event_data)} events for the next {config.DEFAULT_DAYS_AHEAD} days")


def display_chat_interface():
    """Display chat interface in the right column"""
    st.header("💬 AI Scheduling Assistant")

    # Example prompts
    with st.expander("💡 Example Prompts"):
        st.markdown("""
        **Schedule Tasks** (AI finds optimal times):
        - "Schedule 3 hours for my CS homework due Friday"
        - "I need 5 hours for my AI project before Monday, high priority"
        - "Block 2 hours for gym this week, preferably mornings"

        **Create Events** (specific date/time):
        - "Add a meeting with Prof. Smith tomorrow at 2pm for 30 minutes"
        - "Create a dentist appointment next Tuesday at 10am for 1 hour"

        **Query Calendar**:
        - "When am I free today?"
        - "Show me my schedule for this week"
        """)

    # Show confirmation buttons if awaiting user confirmation
    if st.session_state.awaiting_confirmation and st.session_state.proposed_schedule:
        st.info("⏳ Awaiting your confirmation to create these events...")

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("✅ Create These Events", type="primary", use_container_width=True):
                handle_create_events()
        with col2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.awaiting_confirmation = False
                st.session_state.proposed_schedule = None
                st.session_state.current_intent = None
                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': "Schedule cancelled. Feel free to make a new request!"
                })
                st.rerun()

    # Chat history display
    chat_container = st.container()
    with chat_container:
        if st.session_state.chat_history:
            for message in st.session_state.chat_history:
                role = message.get('role', 'user')
                content = message.get('content', '')

                if role == 'user':
                    st.chat_message("user").write(content)
                else:
                    st.chat_message("assistant").write(content)
        else:
            st.info("👋 Hello! I'm your AI calendar assistant. Type a scheduling request below to get started.")

    # Chat input (disabled if awaiting confirmation)
    user_input = st.chat_input(
        "Type your scheduling request...",
        disabled=st.session_state.awaiting_confirmation
    )

    if user_input:
        # Add user message to chat history
        st.session_state.chat_history.append({
            'role': 'user',
            'content': user_input
        })

        # Process the request
        try:
            with st.spinner("Understanding your request..."):
                # Parse intent using AI
                intent = st.session_state.ai_service.parse_user_intent(user_input)
                st.session_state.current_intent = intent

            # For schedule_task action, generate schedule
            if intent.action == 'schedule_task':
                with st.spinner("Finding optimal time slots..."):
                    schedule_plan = st.session_state.ai_service.generate_schedule_plan(
                        user_intent=intent,
                        calendar_events=st.session_state.calendar_events
                    )

                    st.session_state.proposed_schedule = schedule_plan

                # Create response with proposed schedule
                response = f"""✅ **I found optimal times for your task!**

{schedule_plan.get_readable_summary()}

---
**Total Time**: {schedule_plan.total_scheduled_minutes} minutes ({schedule_plan.total_scheduled_minutes/60:.1f} hours)

Click **"Create These Events"** above to add them to your calendar, or **"Cancel"** to try again."""

                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': response
                })

                # Set awaiting confirmation
                st.session_state.awaiting_confirmation = True

            elif intent.action == 'create_event':
                # For create_event with specific datetime
                with st.spinner("Creating your event..."):
                    import pytz
                    tz = pytz.timezone(config.TIMEZONE)

                    # Use specific_datetime if provided, otherwise use deadline
                    event_start = intent.specific_datetime
                    if not event_start:
                        st.session_state.chat_history.append({
                            'role': 'assistant',
                            'content': "❌ I need a specific date and time to create an event. Please specify when you want this event (e.g., 'tomorrow at 2pm')."
                        })
                        st.rerun()
                        return

                    # Calculate end time
                    from datetime import timedelta
                    event_end = event_start + timedelta(minutes=intent.duration_minutes)

                    # Check for conflicts
                    scheduler = st.session_state.ai_service.scheduler_service
                    has_conflict, conflicting_event = scheduler.has_conflict(
                        new_start=event_start,
                        new_end=event_end,
                        existing_events=st.session_state.calendar_events
                    )

                    if has_conflict:
                        response = f"""⚠️ **Conflict detected!**

Your requested time conflicts with:
- **{conflicting_event.title}** ({conflicting_event.start.strftime('%I:%M%p')} - {conflicting_event.end.strftime('%I:%M%p')})

Would you like me to:
1. Find a different time slot for this event?
2. Move the conflicting event (if it's flexible)?

Please rephrase your request or try a different time."""
                    else:
                        # No conflict - create the event directly
                        result = st.session_state.calendar_client.create_event(
                            title=intent.task_name,
                            start=event_start,
                            end=event_end,
                            description=f"Priority: {intent.priority}\n{intent.notes or ''}",
                            attendees=intent.attendees
                        )

                        if result:
                            response = f"""✅ **Event created successfully!**

**{intent.task_name}**
- **When**: {event_start.strftime('%A, %B %d at %I:%M%p')}
- **Duration**: {intent.duration_minutes} minutes

The event has been added to your Google Calendar."""

                            # Refresh calendar
                            load_calendar_events()
                        else:
                            response = "❌ Failed to create the event. Please try again."

                    st.session_state.chat_history.append({
                        'role': 'assistant',
                        'content': response
                    })

            elif intent.action == 'query_calendar':
                # Query calendar for availability or information
                response = f"""📅 **Calendar Query**

{intent.get_readable_summary()}

Currently showing events for the next {config.DEFAULT_DAYS_AHEAD} days.

You have {len(st.session_state.calendar_events)} upcoming events."""

                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': response
                })

            else:
                # For other actions (modify_event, delete_event), show parsed intent
                response = f"""✅ **I understood your request:**

{intent.get_readable_summary()}

---
📋 **Parsed Details:**
- **Action**: {intent.action}
- **Task**: {intent.task_name}
"""

                if intent.duration_minutes > 0:
                    response += f"- **Duration**: {intent.duration_minutes} minutes\n"

                if intent.deadline:
                    response += f"- **Deadline**: {intent.deadline.strftime('%Y-%m-%d %I:%M %p')}\n"

                if intent.specific_datetime:
                    response += f"- **Scheduled for**: {intent.specific_datetime.strftime('%Y-%m-%d %I:%M %p')}\n"

                response += "\n*This action type is coming soon! For now, use schedule_task or create_event.*"

                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': response
                })

        except Exception as e:
            error_message = f"❌ Sorry, I couldn't process your request:\n\n{str(e)}\n\nPlease try rephrasing or use one of the example prompts above."
            st.session_state.chat_history.append({
                'role': 'assistant',
                'content': error_message
            })

        # Rerun to update chat display
        st.rerun()


def handle_create_events():
    """Handle creation of events from proposed schedule"""
    try:
        with st.spinner("Creating calendar events..."):
            result = st.session_state.calendar_client.create_events_from_plan(
                schedule_plan=st.session_state.proposed_schedule,
                user_intent=st.session_state.current_intent
            )

        # Build success message
        if result['success_count'] > 0:
            success_msg = f"""✅ **Successfully created {result['success_count']} calendar event(s)!**

Your schedule has been added to your Google Calendar. Check the calendar view to see your new events.
"""

            if result['failed_blocks']:
                success_msg += f"\n⚠️ Warning: {len(result['failed_blocks'])} event(s) failed to create."

            st.session_state.chat_history.append({
                'role': 'assistant',
                'content': success_msg
            })

            # Refresh calendar to show new events
            load_calendar_events()

        else:
            st.session_state.chat_history.append({
                'role': 'assistant',
                'content': "❌ Failed to create calendar events. Please try again."
            })

        # Reset state
        st.session_state.awaiting_confirmation = False
        st.session_state.proposed_schedule = None
        st.session_state.current_intent = None

    except Exception as e:
        st.session_state.chat_history.append({
            'role': 'assistant',
            'content': f"❌ Error creating events: {str(e)}"
        })
        st.session_state.awaiting_confirmation = False

    st.rerun()


def main():
    """Main application"""
    # Title
    st.title("🤖 AI Calendar Personal Assistant")

    # Initialize session state
    init_session_state()

    # Initialize clients
    if not initialize_clients():
        st.error("Failed to initialize application. Please check your configuration.")
        st.stop()

    # Authenticate with Google Calendar
    if not authenticate_calendar():
        st.warning("⚠️ Please authenticate with Google Calendar to continue.")
        if st.button("🔐 Authenticate Now"):
            authenticate_calendar()
            st.rerun()
        st.stop()

    # Load calendar events on first load
    if not st.session_state.calendar_events:
        load_calendar_events()

    # Create two-column layout
    col_left, col_right = st.columns([1, 1])

    # Left column: Calendar view
    with col_left:
        display_calendar_view()

    # Right column: Chat interface
    with col_right:
        display_chat_interface()

    # Footer
    st.divider()
    st.caption("🚀 AI Calendar Assistant - Phase 2: Intelligent Scheduling & Event Creation")


if __name__ == "__main__":
    main()
