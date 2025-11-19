import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

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