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
from itertools import groupby


logging.basicConfig(filename='pfannkuchen.log', filemode='w', level=logging.DEBUG)
log = logging.getLogger()
log.setLevel(logging.DEBUG)


COMMASPACE = ', '
DATETIME_FORMAT = '%A, %B %d, %Y - %I:%M%p'
PANCAKE_MARKET = 0 # 0 is Austin's market id
PICKLE_FILE = 'pfannkuchen.p'
RECIPIENTS = []
TEMPLATE_FILE = 'pfannkuchen.html'
TODAY = datetime.now()


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

    content = u''
    for k, pancakes in groupby(pancakes, key=by_film_and_cinema):
        content += u'<h1><a href="https://drafthouse.com/uid/{}/">{}</h1>\n'.format(k[0], k[1])
        content += u'<h2><a href="{}">{}</a></h2>\n'.format(k[2], k[3])
        content += u'<ul>\n'
        for k, pancakes in groupby(pancakes, key=by_date):
            content += u'    <li>{} - {}</li>\n'.format(k, ', '.join(pancake_times_html(pancakes)))
        content += u'</ul>\n\n'

    template = open(TEMPLATE_FILE, 'r').read()
    return template.decode('utf-8').format(content=content)


def pancake_text(pancakes):
    """Returns a plain text digest of the given pancakes."""
    text = ''
    for pancake in sorted(pancakes, key=pancake_sort_key):
        params = (
            pancake['film'],
            pancake['cinema'],
            pancake['date'],
            pancake['time'],
            u'On sale now!' if pancake['onsale'] else u'Not on sale.',
        )
        text += u'{}\n{}\n{}\n{}\n{}'.format(*params)
        if pancake['onsale']:
            text += u'\n{}'.format(pancake['url'])
        text += u'\n\n'
    return text


def notify(pancakes):
    """Sends digest email(s) to RECIPIENTS given pancakes (no email sent if pancakes is empty)."""
    if not pancakes:
        return

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Pancake Alert: {}'.format(datetime.strftime(datetime.now(), DATETIME_FORMAT))
        msg['To'] = COMMASPACE.join(RECIPIENTS)

        plain = pancake_text(pancakes)        
        log.info(u'digest:\n{}'.format(plain))

        msg.attach(MIMEText(plain, 'plain', 'utf-8'))
        msg.attach(MIMEText(pancake_html(pancakes), 'html', 'utf-8'))

        if RECIPIENTS:
            msg['From'] = RECIPIENTS[0]
            s = smtplib.SMTP('localhost')
            s.sendmail(msg['From'], RECIPIENTS, msg.as_string())
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
        url = '{}?&date={}&marketid={:04.0f}&callback=callback'.format(API.market_sessions_url, datetime.strftime(TODAY, '%Y%m%d'), market_id)
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
                    onsale = session_data['SessionStatus'] == u'onsale'
                    pancake = {
                        'film': string.capwords(film.lstrip('Master Pancake: ').lower()),
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
    m.update(pancake['film'].encode('utf-8'))
    m.update(pancake['cinema'].encode('utf-8'))
    m.update(pancake['date'].encode('utf-8'))
    m.update(pancake['time'].encode('utf-8'))
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
    for key, pancake in db.items():
        if pancake_datetime(pancake).date() < TODAY.date():
            del db[key]

if __name__ == '__main__':
    try:
        db = load_database()
    except:
        # start new database if we couldn't load one
        db = {}

    try:
        RECIPIENTS = [line.strip() for line in open('pfannkuchen.list')]
    except:
        # will not spend email notifications
        pass

    pancakes = query_pancakes(PANCAKE_MARKET)
    updated = update_pancakes(db, pancakes)
    notify(updated)
    prune_database(db)
    save_database(db)
