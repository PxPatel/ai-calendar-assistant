import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
GOOGLE_GEMINI_API_KEY = os.getenv("GOOGLE_GEMINI_API_KEY")
GOOGLE_GEMINI_MODEL = os.getenv("GOOGLE_GEMINI_MODEL", "gemini-1.5-flash")

# Google Calendar OAuth (uses credentials.json in project root)
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"

# Calendar Settings
WORK_HOURS_START = 8  # 8 AM
WORK_HOURS_END = 22   # 10 PM
DEFAULT_DAYS_AHEAD = 7

# Scheduling Preferences
PREFERRED_BLOCK_SIZE_MINUTES = 30  # 1 hours
MIN_BLOCK_SIZE_MINUTES = 15
MAX_BLOCK_SIZE_MINUTES = 180  # 3 hours

# Time Zone
TIMEZONE = "America/New_York"  # Change to your timezone