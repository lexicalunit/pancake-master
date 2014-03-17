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

from bs4 import BeautifulSoup # third party
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

PANCAKE_STYLE = {
    'html': {
        'margin': '0',
        'padding': '0',
        'border': '0',
    },
    'body': {
        'background-color': '#F2F2F2',
        'font-family': 'sans-serif',
    },
    'a': {
        'margin': '0',
        'padding': '0',
        'border': '0',
        'color': 'inherit',
        'text-decoration': 'none',
    },
    'ul': {
        'background-color': '#A31E21',
        'margin': '0',
        'padding': '2%',
        'border-top': '0',
        'border-right': '8px solid #E2C162',
        'border-bottom': '8px solid #E2C162',
        'border-left': '8px solid #E2C162',
        'border-bottom-left-radius': '15px',
        'border-bottom-right-radius': '15px',
        'list-style-type': 'none',
        'list-style': 'none',
    },
    'h1': {
        'color': '#E9E5C8',
        'background-color': '#A31E21',
        'margin': '5% 0 0 0',
        'padding': '2% 2% 0% 2%',
        'border-top': '8px solid #E2C162',
        'border-right': '8px solid #E2C162',
        'border-bottom': '0',
        'border-left': '8px solid #E2C162',
        'border-top-left-radius': '15px',
        'border-top-right-radius': '15px',
        'text-shadow': '3px 3px 3px #4d4d4d',
    },
    'h2': {
        'color': '#E9E5C8',
        'background-color': '#A31E21',
        'margin': '0',
        'padding': '0 0 1% 3%',
        'border-top': '0',
        'border-right': '8px solid #E2C162',
        'border-bottom': '0',
        'border-left': '8px solid #E2C162',
    },
    'li': {
        'margin': '0 3% 0 3%',
        'padding': '0 3% 0 3%',
        'border': '0',
        'font-size': '125%',
        'line-height': '150%',
    },
    '.onsale': {
        'color': 'blue',
    },
    '.soldout': {
        'text-decoration': 'line-through',
    },
    '#footer': {
        'width': '80%',
        'margin-top': '0',
        'margin-right': 'auto',
        'margin-bottom': '0',
        'margin-left': 'auto',
        'padding': '0',
        'border-top': '2em solid #F2F2F2',
        'border-right': '0',
        'border-bottom': '2em solid #F2F2F2',
        'border-left': '0',
        'text-align': 'center',
        'line-height': '150%',
    },
    '#main': {
        'width': '80%',
        'padding': '0',
        'margin-top': '0',
        'margin-right': 'auto',
        'margin-bottom': '0',
        'margin-left': 'auto',
        'border': '0',
    },
}


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


def html_showtimes(pancakes):
    """Returns a list of pancake showtimes, as pancake HTML."""
    showtimes = []
    for pancake in pancakes:
        soup = BeautifulSoup('<span></span>')
        soup.span['class'] = pancake['status']

        if pancake['status'] == 'onsale':
            anchor = soup.new_tag('a', href=pancake['url'])
            anchor.append(time_string(pancake['datetime']))
            soup.span.append(anchor)
        else: # pancake['status'] == 'soldout' or pancake['status'] == 'notonsale'
            soup.span.append(time_string(pancake['datetime']))

        showtimes.append(str(soup))
    return showtimes


def apply_style(tag, style):
    """Applies the given CSS style to the given tag."""
    if 'style' not in tag.attrs:
        tag['style'] = ''
    s = ''.join('{}: {};'.format(k, v) for k, v in style.items())
    tag['style'] += s


def styled(html, style):
    """Returns inline CSS styled HTML."""
    soup = BeautifulSoup(html)
    for tag in soup.find_all(True):
        if tag.name in style:
            apply_style(tag, style[tag.name])
        if 'class' in tag.attrs:
            for tag_class in tag['class']:
                key = '.' + tag_class
                if key in style:
                    apply_style(tag, style[key])
        if 'id' in tag.attrs:
            key = '#' + tag['id']
            if key in style:
                apply_style(tag, style[key])
    return str(soup.prettify())


def html_digest(pancakes):
    """Returns pancake styled HTML digest of the given pancakes."""
    pancakes = sorted(pancakes, key=pancake_sort_key)

    # things to group by
    by_film_and_cinema = lambda p: (p['film_uid'], p['film'], p['cinema_url'], p['cinema'])
    by_day = lambda p: p['datetime'].date()

    soup = BeautifulSoup('')
    for key, pancakes in groupby(pancakes, key=by_film_and_cinema):
        film_uid, film, cinema_url, cinema = key

        film_heading = BeautifulSoup('<h1><a></a></h1>')
        film_heading.a['href'] = 'https://drafthouse.com/uid/' + film_uid
        film_heading.a.append(film)

        cinema_heading = BeautifulSoup('<h2><a></a></h2>')
        cinema_heading.a['href'] = cinema_url
        cinema_heading.a.append(cinema)

        item_data = []
        for day, pancakes in groupby(pancakes, key=by_day):
            item_data.append((date_string(day), ', '.join(html_showtimes(pancakes))))

        item_list = BeautifulSoup('<ul></ul>')
        for data, n in zip(item_data, count(1)):
            day, showtimes = data

            item = item_list.new_tag('li')

            if n % 2 == 0:
                item['style'] = 'background-color: #FFFFFF;'
            else:
                item['style'] = 'background-color: #F5F5F5;'

            if n == 1:
                item['style'] += 'border-top-left-radius: 15px;border-top-right-radius: 15px;'

            if n == len(item_data):
                item['style'] += 'border-bottom-left-radius: 15px;border-bottom-right-radius: 15px;'

            item_content = '<span>{day} - {showtimes}</span>'.format(day=day, showtimes=showtimes)
            item.append(BeautifulSoup(item_content))
            item_list.ul.append(item)

        soup.append(film_heading)
        soup.append(cinema_heading)
        soup.append(item_list)

    try:
        template = open(TEMPLATE_FILE, 'r').read()
        return styled(template.format(content=str(soup)), PANCAKE_STYLE)
    except:
        log.warn('could not load HTML template file, generating incomplete HTML...')
        return content


def text_digest(pancakes):
    """Returns a plain text digest of the given pancakes."""
    text = ''
    for pancake in sorted(pancakes, key=pancake_sort_key):
        if pancake['status'] == 'onsale':
            status = 'On sale now!'
        elif pancake['status'] == 'soldout':
            status = 'Sold out.'
        else: # pancake['status'] == 'notonsale'
            status = 'Not on sale yet.'
        params = (
            pancake['film'].encode('utf-8'),
            pancake['cinema'],
            date_string(pancake['datetime']),
            time_string(pancake['datetime']),
            status,
        )
        text += '{}\n{}\n{}\n{}\n{}'.format(*params)
        if pancake['status'] == 'onsale':
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


def parse_datetime(date_str, time_str):
    """Returns a datetime object representing the show time of the given Alamo Drafthouse API's date and time."""
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


def query_pancakes(market_id):
    """Queries the Alamo Drafthouse API for the list of pancakes in a given market."""
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
                    status = str(session_data['SessionStatus'])
                    pancake = {
                        'film': string.capwords(film.replace('Master Pancake: ', '').lower()),
                        'film_uid': film_uid,
                        'url': str(session_data['SessionSalesURL']) if status == 'onsale' else None,
                        'cinema': str(cinema),
                        'cinema_url': str(cinema_url),
                        'datetime': parse_datetime(date_data['Date'], session_data['SessionTime']),
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

        if key in db:
            if db[key]['status'] != pancake['status'] and pancake['status'] == 'onsale':
                updated.append(pancake)
        else:
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
        recipients = None
        log.warn('no email recipients found, not sending email notifications...')

    try:
        pancakes = query_pancakes(PANCAKE_MARKET)
        updated = update_pancakes(db, pancakes)
        notify(updated, recipients)
        prune_database(db)
        save_database(db)
    except:
        log.exception('fatal error:')
