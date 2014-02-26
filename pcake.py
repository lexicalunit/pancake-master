#!/usr/bin/env python

import gzip
import hashlib
import json
import logging
import pickle
import re
import smtplib
import urllib2


from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itertools import groupby


logging.basicConfig(filename='pcake.log', filemode='w', level=logging.DEBUG)
log = logging.getLogger()
log.setLevel(logging.DEBUG)


COMMASPACE = ', '
DATETIME_FORMAT = '%A, %B %d, %Y - %I:%M%p'
PANCAKE_MARKET = 0 # 0 is Austin's market id
PICKLE_FILE = 'pcake.p'
RECIPIENTS = [line.strip() for line in open('pcake.list')]
SENDER = 'pancake-alerter'
TEMPLATE_FILE = 'pcake.html'


class API(object):
    """Alamo Drafthouse API resources."""
    cinema_sessions_url = 'https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/CinemaSessions.aspx'
    market_sessions_url = 'https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/marketsessions.aspx'


def pancake_datetime(pancake):
    """Returns a datetime object representing the show time of the given pancake."""
    timestamp = '{} - {}'.format(pancake['date'], pancake['time'])

    # Alamo Drafthouse API returns times with a 'p' appended for PM, otherwise assume AM
    if timestamp.endswith('p'):
        timestamp = timestamp[:-1] + 'PM'
    else:
        timestamp = timestamp[:-1] + 'AM'

    return datetime.strptime(timestamp, DATETIME_FORMAT)


def pancake_sort_key(pancake):
    """Key to sort pancakes by film title, cinema location, and datetime of the show."""
    return pancake['film'], pancake['cinema'], pancake_datetime(pancake)


def pancake_html(pancakes):
    """Returns an HTML string digest of the given pancakes."""
    pancakes = sorted(pancakes, key=pancake_sort_key)

    def pancake_times_html(pancakes):
        """Returns a list of pancake times, as HTML, with hyperlink if currently on sale."""
        return ['<a href="{}">{}</a>'.format(p['url'], p['time']) if p['onsale'] else p['time'] for p in pancakes]

    # things to group by
    by_film_and_cinema = lambda p: (p['film_uid'], p['film'], p['cinema_url'], p['cinema'])
    by_date = lambda p: p['date']

    content = ''
    for k, pancakes in groupby(pancakes, key=by_film_and_cinema):
        content += '<h1><a href="https://drafthouse.com/uid/{}/">{}</h1>\n'.format(k[0], k[1])
        content += '<h2><a href="{}">{}</a></h2>\n'.format(k[2], k[3])
        content += '<ul>\n'
        for k, pancakes in groupby(pancakes, key=by_date):
            content += '    <li>{} - {}</li>\n'.format(k, ', '.join(pancake_times_html(pancakes)))
        content += '</ul>\n\n'

    template = open(TEMPLATE_FILE, 'r').read()
    return template.format(content=content)


def pancake_text(pancakes):
    """Returns a plain text digest of the given pancakes."""
    text = ''
    for pancake in sorted(pancakes, key=pancake_sort_key):
        params = (
            pancake['film'],
            pancake['cinema'],
            pancake['date'],
            pancake['time'],
            'On sale now!' if pancake['onsale'] else 'Not on sale.',
        )
        text += '{}\n{}\n{}\n{}\n{}'.format(*params)
        if pancake['onsale']:
            text += '\n{}'.format(pancake['url'])
        text += '\n\n'
    return text


def notify(pancakes):
    """Sends digest email(s) to RECIPIENTS given pancakes (no email sent if pancakes is empty)."""
    if not pancakes:
        return

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Pancake Alert: {}'.format(datetime.strftime(datetime.now(), DATETIME_FORMAT))
        msg['From'] = SENDER
        msg['To'] = COMMASPACE.join(RECIPIENTS)
        msg.attach(MIMEText(pancake_text(pancakes), 'plain'))
        msg.attach(MIMEText(pancake_html(pancakes), 'html'))

        s = smtplib.SMTP('localhost')
        s.sendmail(SENDER, RECIPIENTS, msg.as_string())
        s.quit()

        log.info('sent email(s) to {}'.format(COMMASPACE.join(RECIPIENTS)))
    except Exception as e:
        log.error('email fail: {}'.format(e))
        raise


def parse_data(data):
    """Parses out and returns the data from a Alamo Drafthouse API data response."""
    return json.loads(re.search('.*?({.*)\)', data).group(1))


def query_cinemas(market_id):
    """Queries the Alamo Drafthouse API for the list of cinemas in a given market."""
    try:
        today = datetime.strftime(datetime.now(), '%Y%m%d')
        url = '{}?&date={}&marketid={:04.0f}&callback=callback'.format(API.market_sessions_url, today, market_id)
        r = urllib2.urlopen(url).read()
        data = parse_data(r)
    except Exception as e:
        log.error('market sessions fail: {}'.format(e))
        raise

    cinemas = []
    for cinema in data['Market']['Cinemas']:
       cinemas.append((int(cinema['CinemaId']), cinema['CinemaName'], cinema['CinemaURL']))
    return cinemas


def query_pancakes(market_id):
    """Queries the Alamo Drafthouse API for the list of pancakes in a given market."""
    pancakes = []
    for cinema_id, cinema, cinema_url in query_cinemas(market_id):
        try:
            url = '{}?cinemaid={:04.0f}&callback=callback'.format(API.cinema_sessions_url, cinema_id)
            r = urllib2.urlopen(url).read()
            data = parse_data(r)
        except Exception as e:
            log.error('cinema sessions fail: {}'.format(e))
            raise

        for date_data in data['Cinema']['Dates']:
            for film_data in date_data['Films']:
                film = film_data['Film']
                film_uid = film_data['FilmId']

                if 'pancake' not in film.lower():
                    continue # DO NOT WANT!

                for session_data in film_data['Sessions']:
                    onsale = session_data['SessionStatus'] == 'onsale'
                    pancake = {
                        'film': film.lstrip('Master Pancake: ').title(),
                        'film_uid': film_uid,
                        'cinema': cinema,
                        'cinema_url': cinema_url,
                        'date': date_data['Date'],
                        'time': session_data['SessionTime'],
                        'onsale': onsale,
                    }
                    if onsale:
                        pancake['url'] = session_data['SessionSalesURL']
                    pancakes.append(pancake)
    return pancakes


def pancake_key(pancake):
    """Creates a unique id for a given pancake."""
    m = hashlib.md5()
    m.update(pancake['film'])
    m.update(pancake['cinema'])
    m.update(pancake['date'])
    m.update(pancake['time'])
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

        if key in db and db[key]['onsale'] != pancake['onsale'] and pancake['onsale']:
            updated.append(pancake)
        elif key not in db:
            updated.append(pancake)
    
        db[key] = pancake
    return updated


def prune_database(db):
    """Removes old pancakes from the database."""
    # TODO: Go through the database checking to see if the pancakes are old, remove them if they are.


if __name__ == '__main__':
    try:
        db = load_database()
    except:
        # start new database if we couldn't load one
        db = {}

    pancakes = query_pancakes(PANCAKE_MARKET)
    updated = update_pancakes(db, pancakes)
    notify(updated)
    prune_database(db)
    save_database(db)
