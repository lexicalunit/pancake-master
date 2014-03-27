# License: none (public domain)

import httplib2

from apiclient import discovery
from oauth2client import file


class GoogleCalendar(object):
    """Simple object for interacting with Google Calendar API."""

    def __init__(self, credentials_filename):
        """Creates Google Calendar API interface using the given credentials."""
        storage = file.Storage(credentials_filename)
        credentials = storage.get()
        if not credentials or credentials.invalid:
            raise Exception('Credentials invalid or missing :(')
        http = httplib2.Http(disable_ssl_certificate_validation=True)
        http = credentials.authorize(http)
        self.service = discovery.build('calendar', 'v3', http=http)

    def insert_event(self, calid, event_body):
        """Inserts a new calendar event."""
        self.service.events().insert(calendarId=calid, body=event_body).execute()

    def update_event(self, calid, eid, event_body):
        """Updates an existing calendar event."""
        self.service.events().update(calendarId=calid, eventId=eid, body=event_body).execute()

    def delete_event(self, calid, eid):
        """Deletes an existing calendar event."""
        self.service.events().delete(calendarId=calid, eventId=eid).execute()

    def events(self, calid):
        """Gets the list of calendar events."""
        page = None
        events = []
        while True:
            event_list = self.service.events().list(calendarId=calid, pageToken=page).execute()
            events.extend(event_list['items'])
            page = event_list.get('nextPageToken')
            if not page:
                break
        return events

    def calendar_list(self):
        """Gets lits of google calendars."""
        page = None
        calendars = []
        while True:
            calendar_list = self.service.calendarList().list(pageToken=page).execute()
            calendars.extend(calendar_list['items'])
            page = calendar_list.get('nextPageToken')
            if not page:
                break
        return calendars
