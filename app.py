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
        - "Schedule 3 hours for my CS homework due Friday"
        - "Add a meeting with Prof. Smith tomorrow at 2pm for 30 minutes"
        - "I need 5 hours for my AI project before Monday, high priority"
        - "Block 2 hours for gym this week, preferably mornings"
        - "Study for finals tomorrow"
        """)

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

    # Chat input
    user_input = st.chat_input("Type your scheduling request...")

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

                # Create response message
                response = f"""✅ **I understood your request:**

{intent.get_readable_summary()}

---
📋 **Parsed Details:**
- **Action**: {intent.action}
- **Task**: {intent.task_name}
- **Duration**: {intent.duration_minutes} minutes
- **Priority**: {intent.priority}
"""

                if intent.deadline:
                    response += f"- **Deadline**: {intent.deadline.strftime('%Y-%m-%d %I:%M %p')}\n"

                if intent.specific_datetime:
                    response += f"- **Scheduled for**: {intent.specific_datetime.strftime('%Y-%m-%d %I:%M %p')}\n"

                response += "\n*Note: In Phase 2, I'll automatically find time slots and create calendar events.*"

                # Add assistant response to chat history
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
    st.caption("🚀 AI Calendar Assistant - Phase 1: Intent Parsing & Calendar Display")


if __name__ == "__main__":
    main()
