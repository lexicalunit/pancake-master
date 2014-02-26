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
RECIPIENTS = [line.strip() for line in open('pcake.list')]
SENDER = 'pancake-alerter'
PICKLE_FILE = 'pcake.p'
TEMPLATE_FILE = 'pcake.html'
DATETIME_FORMAT = '%A, %B %d, %Y - %I:%M%p'


def pancake_sort_key(pancake):
    timestamp = '{} - {}'.format(pancake['date'], pancake['time'])
    if timestamp.endswith('p'):
        timestamp = timestamp[:-1] + 'PM'
    else:
        timestamp = timestamp[:-1] + 'AM'
    return pancake['film'], pancake['cinema'], datetime.strptime(timestamp, DATETIME_FORMAT)


def pancake_html(pancakes):
    pancakes = sorted(pancakes, key=pancake_sort_key)

    def times_html(pancakes):
        return ['<a href="{}">{}</a>'.format(p['url'], p['time']) if p['onsale'] else p['time'] for p in pancakes]

    content = ''
    for film, date_times in groupby(pancakes, key=lambda p: (p['film'], p['film_uid'], p['cinema'], p['cinema_url'])):

        content += '<h1><a href="https://drafthouse.com/uid/{film_uid}/">{film}</h1>\n'.format(film_uid=film[1], film=film[0])
        content += '<h2><a href="{cinema_url}">{cinema}</a></h2>\n'.format(cinema_url=film[3], cinema=film[2])
        content += '<ul>\n'

        for date, times in groupby(date_times, key=lambda p: p['date']):
            content += '    <li>{} - {}</li>\n'.format(date, ', '.join(times_html(times)))

        content += '</ul>\n\n'

    template = open(TEMPLATE_FILE, 'r').read()
    return template.format(content=content)


def pancake_text(pancakes):
    text = ''
    for pancake in sorted(pancakes, key=pancake_sort_key):
        text += '{}\n{}\n{}\n{}\n{}'.format(
            pancake['film']
            , pancake['cinema']
            , pancake['date']
            , pancake['time']
            , 'On sale now!' if pancake['onsale'] else 'Not on sale.'
        )
        if pancake['onsale']:
            text += '\n{}'.format(pancake['url'])
        text += '\n\n'


def notify(pancakes):
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


def json_data(data):   
    return json.loads(re.search('.*?({.*)\)', data).group(1))


def query_cinemas(market_id):
    try:
        r = urllib2.urlopen('https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/marketsessions.aspx?callback=callback&date=20140223&marketid={:04.0f}'.format(market_id)).read()
    except Exception as e:
        log.error('market sessions fail: {}'.format(e))
        raise

    data = json_data(r)

    for cinema in data['Market']['Cinemas']:
       yield int(cinema['CinemaId']), cinema['CinemaName'], cinema['CinemaURL']


def query_pancakes(market_id):
    for cinema_id, cinema, cinema_url in query_cinemas(market_id):
        try:
            r = urllib2.urlopen('https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/CinemaSessions.aspx?cinemaid={:04.0f}&callback=callback'.format(cinema_id)).read()
        except Exception as e:
            log.error('cinema sessions fail: {}'.format(e))
            raise

        data = json_data(r)

        for date_data in data['Cinema']['Dates']:
            for film_data in date_data['Films']:
                film = film_data['Film']
                film_uid = film_data['FilmId']

                if 'pancake' not in film.lower():
                    continue # DO NOT WANT!

                for session_data in film_data['Sessions']:
                    onsale = session_data['SessionStatus'] == 'onsale'
                    result = {
                        'film': film.lstrip('Master Pancake: ').title(),
                        'film_uid': film_uid,
                        'cinema': cinema,
                        'cinema_url': cinema_url,
                        'date': date_data['Date'],
                        'time': session_data['SessionTime'],
                        'onsale': onsale,
                    }
                    if onsale:
                        result['url'] = session_data['SessionSalesURL']
                    yield result


def pancake_key(pancake):
    m = hashlib.md5()
    m.update(pancake['film'])
    m.update(pancake['cinema'])
    m.update(pancake['date'])
    m.update(pancake['time'])
    return m.hexdigest()


def save(filename, object, bin=1):
    log.info('saving {}'.format(filename))
    try:
        with gzip.GzipFile(filename, 'wb') as f:
            f.write(pickle.dumps(object, bin))
    except Exception as e:
        log.error('load failure: {}'.format(e))
        raise


def load(filename):
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


def find_pancakes(db, market_id):
    pancakes = []
    for pancake in query_pancakes(market_id):
        key = pancake_key(pancake)

        if key in db and db[key]['onsale'] != pancake['onsale'] and pancake['onsale']:
            pancakes.append(pancake)
        elif key not in db:
            pancakes.append(pancake)
    
        db[key] = pancake
    return pancakes


if __name__ == '__main__':
    try:
        db = load(PICKLE_FILE)
    except:
        db = {}

    try:
        pancakes = find_pancakes(db, 0) # 0 is Austin's market id
        if pancakes:
            notify(pancakes)
    except Exception as e:
        log.error('script fail: {}'.format(e))

    save(PICKLE_FILE, db)
