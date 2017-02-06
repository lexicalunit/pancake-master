# License: none (public domain)

import json
import logging

import dateutil.parser
import requests
from pytz import timezone
from slugify import slugify

SHOWTIMES_BASE_URL = 'https://feeds.drafthouse.com/adcService/showtimes.svc/market'
DRAFTHOUSE_BASE_URL = 'https://drafthouse.com'

log = logging.getLogger(__name__)


class Cinema:
    def __init__(self, cinema_id, cinema_name, market_name):
        self.cinema_id = cinema_id
        self.cinema_name = cinema_name
        self.cinema_market = market_name.split(',')[0].lower()

    @property
    def cinema_url(self):
        return '{}/theater/{}'.format(DRAFTHOUSE_BASE_URL, slugify(self.cinema_name))


class Film:
    def __init__(self, session_id, film_id, film_name, film_datetime, film_status, cinema):
        self.session_id = session_id
        self.film_id = film_id
        self.film_name = film_name
        self.film_datetime = film_datetime
        self.film_status = film_status
        self.cinema = cinema

    @property
    def film_url(self):
        cinema = self.cinema.cinema_id
        session = self.session_id
        return '{}/ticketing/{}/{}'.format(DRAFTHOUSE_BASE_URL, cinema, session)


def format_json(data):
    """Return pretty formated json data."""
    return json.dumps(data, indent=4)


def parse_datetime(datetime_str, timezone):
    return dateutil.parser.parse(datetime_str).replace(tzinfo=timezone)


def query(url, **kwargs):
    """Queries given Alamo Drafthouse API url using all kwargs as API parameters."""
    try:
        log.info('querying url "{}" with params {}'.format(url, kwargs))
        resp = requests.get(url, params=kwargs, verify=True)
        data = resp.json()
    except Exception as e:
        log.error('market sessions fail: {}'.format(e))
        raise
    if 'error' in data:
        raise Exception('Alamo Drafthouse API error: {}'.format(data['error']))
    return data


def query_pancakes(market_id, overrides):
    """Queries the Alamo Drafthouse API for the list of pancakes in a given market."""
    data = query('{}/{}'.format(SHOWTIMES_BASE_URL, market_id))
    market_data = data.get('Market')
    if log.isEnabledFor(logging.DEBUG):
        log.debug('market response:\n%s', format_json(data))
    if not market_data:
        return []
    market_name = market_data.get('MarketName')
    pancakes = []
    for date_data in market_data.get('Dates', []):
        log.debug('date: %s', date_data.get('Date'))
        for cinema_data in date_data.get('Cinemas', []):
            cinema_name = cinema_data.get('CinemaName')
            log.debug('cinema: %s', cinema_name)
            cinema = Cinema(cinema_data.get('CinemaId'), cinema_name, market_name)
            cinema_timezone = timezone(cinema_data.get('CinemaTimeZoneATE'))
            for film_data in cinema_data.get('Films', []):
                film_id = film_data.get('FilmId')
                film_name = film_data.get('FilmName')
                log.debug('film: %s', film_name)
                if not any(s.lower() in film_name.lower() for s in overrides):
                    if not all(s in film_name.lower() for s in ['pancake']):
                        continue  # DO NOT WANT!
                for series_data in film_data.get('Series', []):
                    for format_data in series_data.get('Formats', []):
                        for session_data in format_data.get('Sessions', []):
                            session_datetime = session_data.get('SessionDateTime')
                            log.debug('session: %s', session_datetime)
                            film_datetime = parse_datetime(session_datetime, cinema_timezone)
                            film_status = session_data.get('SessionStatus')
                            session_id = session_data.get('SessionId')
                            film = Film(session_id, film_id, film_name, film_datetime, film_status,
                                        cinema)
                            pancakes.append(film)
    return pancakes
