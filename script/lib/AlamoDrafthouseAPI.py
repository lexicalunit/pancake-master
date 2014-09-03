# License: none (public domain)

import json
import logging
import requests
import string

from datetime import datetime

ALAMO_DATETIME_FORMAT = '%A, %B %d, %Y - %I:%M%p'

CINEMA_SESSIONS_URL = 'https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/CinemaSessions.aspx'
MARKET_SESSIONS_URL = 'https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/marketsessions.aspx'
FILM_OVERRIDES = {
    'Action Pack: THE ULTIMATE WILLY WONKA PARTY'
}

log = logging.getLogger(__name__)


def format_json(data):
    """Return pretty formated json data."""
    return json.dumps(data, indent=4)


def format_uid(uid):
    """Returns uid formatted in the way that the Alamo Drafthouse API expects."""
    return '{:04.0f}'.format(uid)


def sanitize_film_title(title):
    """Sanitize utf-8 film title, returns ASCII title."""
    return title.replace(u'\u2019', "'").replace(u'\u2018', '').encode('utf-8').strip()


def parse_datetime(date_str, time_str, market_timezone):
    """Returns the show time of the given Alamo Drafthouse API's date and time."""
    timestamp = '{} - {}'.format(str(date_str), str(time_str))

    if time_str == 'Midnight':
        # Alamo Drafthouse API uses 'Midnight' instead of '12:00'
        timestamp = timestamp[:-8] + '12:00AM'
    elif time_str == 'Noon':
        # Alamo Drafthouse API uses 'Noon' instead of '12:00p'
        timestamp = timestamp[:-4] + '12:00PM'
    else:
        # Alamo Drafthouse API returns times with a 'p' appended for PM, otherwise assume AM
        timestamp = timestamp[:-1] + 'PM' if timestamp.endswith('p') else timestamp[:-1] + 'AM'

    return market_timezone.localize(datetime.strptime(timestamp, ALAMO_DATETIME_FORMAT))


def query(url, **kwargs):
    """Queries given Alamo Drafthouse API url using all kwargs as API parameters."""
    is_jsonp = 'callback' in kwargs

    try:
        log.info('querying url "{}" with params {}'.format(url, kwargs))
        resp = requests.get(url, params=kwargs, verify=False)

        if is_jsonp:
            jsonp = resp.text
            data = json.loads(jsonp[jsonp.index("(") + 1: jsonp.rindex(")")])
        else:
            data = resp.json()
    except Exception as e:
        log.error('market sessions fail: {}'.format(e))
        raise

    if 'msg' in data:
        raise Exception('Alamo Drafthouse API error: {}'.format(data['msg']))

    return data


def query_cinemas(market_id):
    """Queries the Alamo Drafthouse API for the list of cinemas in a given market."""
    data = query(
        MARKET_SESSIONS_URL,
        date=datetime.strftime(datetime.now(), '%Y%m%d'),
        marketid=format_uid(market_id))
    log.debug('market response:\n{}'.format(format_json(data)))

    cinemas = []
    if 'Market' in data:
        for cinema in data['Market']['Cinemas']:
            log.debug(cinema['CinemaName'])
            url = cinema.get('CinemaURL', None)  # Rolling Roadshow has no URL
            cinemas.append((
                int(cinema['CinemaId']),
                str(cinema['CinemaName']),
                str(url) if url else None
            ))
    return cinemas


def query_pancakes(market_id, market_timezone):
    """Queries the Alamo Drafthouse API for the list of pancakes in a given market."""
    pancakes = []
    for cinema_id, cinema, cinema_url in query_cinemas(market_id):
        data = query(
            CINEMA_SESSIONS_URL,
            cinemaid=format_uid(cinema_id),
            callback='whatever')  # sadly, this resource *requires* JSONP callback parameter
        log.debug('cinema response:\n{}'.format(format_json(data)))

        if 'Cinema' not in data:
            continue

        for date_data in data['Cinema']['Dates']:
            for film_data in date_data['Films']:
                film = sanitize_film_title(film_data['Film'])
                film_uid = str(film_data['FilmId'])

                if film not in FILM_OVERRIDES:
                    if not all(s in film.lower() for s in ['pancake', 'master']):
                        continue  # DO NOT WANT!

                for session_data in film_data['Sessions']:
                    status = str(session_data['SessionStatus'])
                    showtime = parse_datetime(
                        date_data['Date'],
                        session_data['SessionTime'],
                        market_timezone)
                    pancake = {
                        'film': string.capwords(film.replace('Master Pancake: ', '').lower()),
                        'film_uid': film_uid,
                        'url': str(session_data['SessionSalesURL']) if status == 'onsale' else None,
                        'cinema': cinema,
                        'cinema_url': cinema_url,
                        'datetime': showtime,
                        'status': status,
                    }
                    pancakes.append(pancake)
    return pancakes
