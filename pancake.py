#!/usr/bin/env python

# License: none (public domain)

import gzip
import hashlib
import json
import logging
import pickle
import re
import smtplib
import string
import urllib2

from datetime import datetime, time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itertools import groupby, count
from pytz import timezone # third party; is there a standard solution?


# setup logging to pancake.log and console
log = logging.getLogger('pancake')
log.setLevel(logging.DEBUG)

fh = logging.FileHandler('pancake.log')
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)

log.addHandler(ch)
log.addHandler(fh)


PANCAKE_MARKET = 0 # 0 is Austin's market id
PANCAKE_TIMEZONE = timezone('US/Central') # Austin is US/Central

PICKLE_FILE = 'pancake.pickle'
RECIPIENTS_FILE = 'pancake.list'
TEMPLATE_FILE = 'pancake.html'

ALAMO_DATETIME_FORMAT = '%A, %B %d, %Y - %I:%M%p'
DATE_FORMAT = '%A, %B %d, %Y'
TIME_FORMAT = '%I:%M%p'
TODAY = datetime.now()


class PancakeStatus(object):
    """Alamo Drafthouse API film statuses."""
    NOTONSALE = 1
    ONSALE = 2
    SOLDOUT = 3


class API(object):
    """Alamo Drafthouse API resources."""
    cinema_sessions_url = 'https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/CinemaSessions.aspx'
    market_sessions_url = 'https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/marketsessions.aspx'


def date_string(dt):
    """Returns a date string representation of the given datetime object."""
    return datetime.strftime(dt, DATE_FORMAT)


def time_string(dt):
    """Returns a time string representation of the given datetime object."""
    time = datetime.strftime(dt, TIME_FORMAT).lstrip('0')
    return time[:-2] + 'p' if time.endswith('PM') else time[:-2]


def datetime_string(dt):
    """Returns a date and time string representation of the given datetime object."""
    return date_string(dt) + ' - ' + time_string(dt)


def pancake_sort_key(pancake):
    """Key to sort pancakes by film title, cinema location, and datetime of the show."""
    return pancake['film'], pancake['cinema'], pancake['datetime']


def html_link(url, text):
    """Returns pancake styled HTML for hyperlink."""
    return '<a href="{url}" style="margin: 0;padding: 0;border: 0;text-decoration: none;">{text}</a>'.format(url=url, text=text)


def html_film(film_uid, film):
    """Returns pancake styled HTML for film header."""
    return '<h1 style="margin: 0;padding: 2% 2% 0% 2%;border: 0;background-color: #A31E21;border-left: 8px solid #E2C162;border-right: 8px solid #E2C162;border-top-left-radius: 15px;border-top-right-radius: 15px;border-top: 8px solid #E2C162;color: #E9E5C8;margin-top: 5%;text-shadow: 3px 3px 3px #4d4d4d;"><a href="https://drafthouse.com/uid/{film_uid}/" style="color: #E9E5C8;text-decoration: none;">{film}</a></h1>\n'.format(film_uid=film_uid, film=film)


def html_cinema(cinema_url, cinema):
    """Returns pancake styled HTML for cinema header."""
    return '<h2 style="margin: 0;padding: 0;border: 0;background-color: #A31E21;border-left: 8px solid #E2C162;border-right: 8px solid #E2C162;color: #E9E5C8;padding-bottom: 1%;padding-left: 3%;"><a href="{cinema_url}" style="color: #E9E5C8;text-decoration: none;">{cinema}</a></h2>\n'.format(cinema_url=cinema_url, cinema=cinema)


def html_times(pancakes):
    """Returns a list of pancake times, as pancake styled HTML."""
    times = []
    for p in pancakes:
        if p['status'] == PancakeStatus.ONSALE:
            times.append(html_link(p['url'], time_string(p['datetime'])))
        elif p['status'] == PancakeStatus.SOLDOUT:
            times.append('<span style="text-decoration: line-through;">' + time_string(p['datetime']) + '</span>')
        else: # p['status'] == PancakeStatus.NOTONSALE
            times.append(time_string(p['datetime']))
    return times


def html_digest(pancakes):
    """Returns pancake styled HTML digest of the given pancakes."""
    pancakes = sorted(pancakes, key=pancake_sort_key)

    # things to group by
    by_film_and_cinema = lambda p: (p['film_uid'], p['film'], p['cinema_url'], p['cinema'])
    by_day = lambda p: p['datetime'].date()

    content = ''
    for k, pancakes in groupby(pancakes, key=by_film_and_cinema):
        content += html_film(k[0], k[1])
        content += html_cinema(k[2], k[3])
        content += '<ul style="margin: 0;padding: 2%;border: 0;list-style: none;background-color: #A31E21;border-bottom-left-radius: 15px;border-bottom-right-radius: 15px;border-bottom: 8px solid #E2C162;border-left: 8px solid #E2C162;border-right: 8px solid #E2C162;list-style-type: none;">\n'

        items = []
        for k, pancakes in groupby(pancakes, key=by_day):
            items.append((date_string(k), ', '.join(html_times(pancakes))))

        for item, n in zip(items, count(1)):
            li_style = 'margin: 0;padding: 0;border: 0;font-size: 125%;line-height: 150%;padding-left: 3%;padding-right: 3%;margin-left: 3%;margin-right: 3%;'
            if n % 2 == 0:
                li_style += 'background-color: #FFFFFF;'
            else:
                li_style += 'background-color: #F5F5F5;'
            if n == 1:
                li_style += 'border-top-left-radius: 15px;border-top-right-radius: 15px;'
            if n == len(items):
                li_style += 'border-bottom-left-radius: 15px;border-bottom-right-radius: 15px;'
            content += '    <li style="{li_style}">{day} - {links}</li>\n'.format(li_style=li_style, day=item[0], links=item[1])

        content += '</ul>\n\n'

    try:
        template = open(TEMPLATE_FILE, 'r').read()
        return template.format(content=content)
    except:
        log.warn('could not load HTML template file, generating incomplete HTML...')
        return content


def text_digest(pancakes):
    """Returns a plain text digest of the given pancakes."""
    text = ''
    for pancake in sorted(pancakes, key=pancake_sort_key):
        if pancake['status'] == PancakeStatus.ONSALE:
            status = 'On sale now!'
        elif pancake['status'] == PancakeStatus.SOLDOUT:
            status = 'Sold out.'
        else: # pancake['status'] == PancakeStatus.NOTONSALE
            status = 'Not on sale yet.'
        params = (
            pancake['film'].encode('utf-8'),
            pancake['cinema'],
            date_string(pancake['datetime']),
            time_string(pancake['datetime']),
            status,
        )
        text += '{}\n{}\n{}\n{}\n{}'.format(*params)
        if pancake['status'] == PancakeStatus.ONSALE:
            text += '\n{}'.format(pancake['url'])
        text += '\n\n'
    return text


def notify(pancakes, recipients):
    """Sends digest email(s) to recipients given pancakes (no email sent if pancakes is empty)."""
    if not pancakes:
        return

    plain = text_digest(pancakes)
    log.info('digest:\n{}'.format(plain))

    if not recipients:
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Pancake Master: {}'.format(datetime_string(datetime.now()))
    msg['To'] = ', '.join(recipients)
    msg['From'] = recipients[0]
    msg.attach(MIMEText(plain, 'plain'))
    msg.attach(MIMEText(html_digest(pancakes), 'html'))

    try:
        s = smtplib.SMTP('localhost')
        s.sendmail(msg['From'], recipients, msg.as_string())
        s.quit()
        log.info('sent email(s) to {}'.format(', '.join(recipients)))
    except Exception as e:
        log.error('email fail: {}'.format(e))
        raise


def parse_data(data):
    """Parses out and returns the data from a Alamo Drafthouse API data response."""
    return json.loads(re.search('.*?({.*)\)', data).group(1))


def query_cinemas(market_id):
    """Queries the Alamo Drafthouse API for the list of cinemas in a given market."""
    try:
        params = {
            'url': API.market_sessions_url,
            'date': datetime.strftime(TODAY, '%Y%m%d'),
            'market_id': market_id,
        }
        url = '{url}?&date={date}&marketid={market_id:04.0f}&callback=callback'.format(**params)
        r = urllib2.urlopen(url).read()
        data = parse_data(r)
    except Exception as e:
        log.error('market sessions fail: {}'.format(e))
        raise

    cinemas = []
    for cinema in data['Market']['Cinemas']:
        cinemas.append((int(cinema['CinemaId']), str(cinema['CinemaName']), str(cinema['CinemaURL'])))
    return cinemas


def sanitize_film_title(title):
    """Sanitize utf-8 film title, returns ASCII title."""
    return str(title.replace(u'\u2019', "'").replace(u'\u2018', ''))


def query_pancakes(market_id):
    """Queries the Alamo Drafthouse API for the list of pancakes in a given market."""

    def pancake_datetime(date_str, time_str):
        """Returns a datetime object representing the show time of the given pancake."""
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

        return PANCAKE_TIMEZONE.localize(datetime.strptime(timestamp, ALAMO_DATETIME_FORMAT))

    pancakes = []
    for cinema_id, cinema, cinema_url in query_cinemas(market_id):
        try:
            params = {
                'url': API.cinema_sessions_url,
                'cinema_id': cinema_id,
            }
            url = '{url}?cinemaid={cinema_id:04.0f}&callback=callback'.format(**params)
            r = urllib2.urlopen(url).read()
            data = parse_data(r)
        except Exception as e:
            log.error('cinema sessions fail: {}'.format(e))
            raise

        for date_data in data['Cinema']['Dates']:
            for film_data in date_data['Films']:
                film = sanitize_film_title(film_data['Film'])
                film_uid = str(film_data['FilmId'])

                if not all(s in film.lower() for s in ['pancake', 'master']):
                    continue # DO NOT WANT!

                for session_data in film_data['Sessions']:
                    session_status = str(session_data['SessionStatus'])
                    if session_status == 'onsale':
                        status = PancakeStatus.ONSALE
                    elif session_status == 'soldout':
                        status = PancakeStatus.SOLDOUT
                    else: # session_status == 'notonsale'
                        status = PancakeStatus.NOTONSALE
                    pancake = {
                        'film': string.capwords(film.replace('Master Pancake: ', '').lower()),
                        'film_uid': film_uid,
                        'url': str(session_data['SessionSalesURL']) if status == PancakeStatus.ONSALE else None,
                        'cinema': str(cinema),
                        'cinema_url': str(cinema_url),
                        'datetime': pancake_datetime(date_data['Date'], session_data['SessionTime']),
                        'status': status,
                    }
                    pancakes.append(pancake)
    return pancakes


def pancake_key(pancake):
    """Creates a unique id for a given pancake."""
    m = hashlib.md5()
    m.update(pancake['film'])
    m.update(pancake['cinema'])
    m.update(datetime_string(pancake['datetime']))
    return m.hexdigest()


def save_database(db):
    """Saves pancake database to disk."""
    filename = PICKLE_FILE
    log.info('saving {}'.format(filename))
    try:
        with gzip.GzipFile(filename, 'wb') as f:
            f.write(pickle.dumps(db, 1))
    except Exception as e:
        log.error('load failure: {}'.format(e))
        raise


def load_database():
    """Unpickles and decompresses the given file and returns the created object."""
    filename = PICKLE_FILE
    log.info('loading {}'.format(filename))
    try:
        with gzip.GzipFile(filename, 'rb') as f:
            buf = ''
            while True:
                data = f.read()
                if data == '':
                    break
                buf += data
            return pickle.loads(buf)
    except Exception as e:
        log.error('load failure: {}'.format(e))
        raise


def update_pancakes(db, pancakes):
    """Updates the given database of pancakes given the list of all pancakes, returns list of updated pancakes."""
    updated = []
    for pancake in pancakes:
        key = pancake_key(pancake)

        if (key in db
            and db[key]['status'] != pancake['status']
            and pancake['status'] != PancakeStatus.NOTONSALE):
            updated.append(pancake)
        elif key not in db:
            updated.append(pancake)
    
        db[key] = pancake
    return updated


def prune_database(db):
    """Removes old pancakes from the database."""
    for key, pancake in db.items():
        if pancake['datetime'].date() < TODAY.date():
            del db[key]

if __name__ == '__main__':
    try:
        db = load_database()
    except:
        log.warn('creating new pancake database...')
        db = {}

    try:
        recipients = [line.strip() for line in open(RECIPIENTS_FILE)]
    except:
        log.warn('no email recipients found, not sending email notifications...')

    try:
        pancakes = query_pancakes(PANCAKE_MARKET)
        updated = update_pancakes(db, pancakes)
        notify(updated, recipients)
        prune_database(db)
        save_database(db)
    except:
        log.exception('fatal error:')
