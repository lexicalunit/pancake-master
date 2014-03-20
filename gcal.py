import httplib2
import sys
import datetime
import dateutil.parser

from pancake import query_pancakes
from apiclient import discovery
from oauth2client import file
from oauth2client import client


class GoogleCalender():

    def __init__(self):
        storage = file.Storage('credentials.dat')
        credentials = storage.get()
        if credentials is None or credentials.invalid:
            raise Exception('Credentials invalid or missing :(')
        http = httplib2.Http()
        http = credentials.authorize(http)
        self.service = discovery.build('calendar', 'v3', http=http)

    def MakeEvent(self, calid, summary, startdt, enddt, timezone='America/Chicago'):
        newevent = {
            'summary': summary,
            'start': {
                'dateTime': startdt.isoformat(),
                'timeZone': timezone
            },
            'end': {
                'dateTime': enddt.isoformat(),
                'timeZone': timezone
            }
        }
        self.service.events().insert(calendarId=calid, body=newevent).execute()

    def GetEvents(self, calid):
        page_token = None
        events = []
        while True:
            event_list = self.service.events().list(calendarId=calid, pageToken=None).execute()
            events.extend(event_list['items'])
            page_token = event_list.get('nextPageToken')
            if not page_token:
                break
        return events

    def GetCalenders(self):
        page_token = None
        calenders = []
        while True:
            calender_list = self.service.calendarList().list(pageToken=None).execute()
            calenders.extend(calender_list['items'])
            page_token = calender_list.get('nextPageToken')
            if not page_token:
                break
        return calenders
