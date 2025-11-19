import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

# Scopes define what access we need
SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate():
    """Authenticate with Google Calendar"""
    creds = None
    
    # Check if we have saved credentials
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next time
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def test_calendar_access():
    """Test that we can access the calendar"""
    creds = authenticate()
    service = build('calendar', 'v3', credentials=creds)
    
    # Get the next 10 events
    print("Fetching your calendar events...")
    events_result = service.events().list(
        calendarId='primary',
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    
    if not events:
        print('No upcoming events found.')
    else:
        print(f'Found {len(events)} events:')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f"  - {start}: {event['summary']}")
    
    print("\n✅ Google Calendar API is working!")

if __name__ == '__main__':
    test_calendar_access()