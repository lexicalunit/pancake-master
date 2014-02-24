#!/usr/bin/env python

import gzip
import hashlib
import json
import pickle
import re
import smtplib
import urllib2

from email.mime.text import MIMEText
from itertools import product


COMMASPACE = ', '
RECIPIENTS = ['amy@lexicalunit.com']
SENDER = 'pancake-alerter'
PICKLE_FILE = 'pancake.p'


def notify(pancake):
    subject = 'Pancake Alert: {}'.format(pancake['film'])
    body = '{}\n{}\n{}\n{}\n{}'.format(pancake['film'], pancake['cinema'], pancake['date'], pancake['time'], pancake['onsale'])

    if pancake['onsale']:
        subject += ' ON SALE!'
        body += '\n{}'.format(pancake['url'])

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER
    msg['To'] = COMMASPACE.join(RECIPIENTS)

    s = smtplib.SMTP('localhost')
    s.sendmail(SENDER, RECIPIENTS, msg.as_string())
    s.quit()


def json_data(data):   
    return json.loads(re.search('.*?({.*)\)', data).group(1))


def cinemas(market_id):
    r = urllib2.urlopen('https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/marketsessions.aspx?callback=callback&date=20140223&marketid={:04.0f}'.format(market_id)).read()
    data = json_data(r)

    for cinema in data['Market']['Cinemas']:
       yield cinema['CinemaName'], int(cinema['CinemaId'])


def pancakes(market_id):
    for cinema, cinema_id in cinemas(market_id):
        r = urllib2.urlopen('https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/CinemaSessions.aspx?cinemaid={:04.0f}&callback=callback'.format(cinema_id)).read()
        data = json_data(r)

        for date_data in data['Cinema']['Dates']:
            for film_data in date_data['Films']:
                film = film_data['Film']

                if 'pancake' not in film.lower():
                    continue # DO NOT WANT!

                for session_data in film_data['Sessions']:
                    onsale = session_data['SessionStatus'] == 'onsaale'
                    result = {
                        'film': film.lstrip('Master Pancake: ').title(),
                        'cinema': cinema,
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
    with gzip.GzipFile(filename, 'wb') as f:
        f.write(pickle.dumps(object, bin))


def load(filename):
    with gzip.GzipFile(filename, 'rb') as f:
        buf = ''
        while True:
            data = f.read()
            if data == '':
                break
            buf += data
        return pickle.loads(buf)


if __name__ == '__main__':
    try:
        db = load(PICKLE_FILE)
    except:
        db = {}

    for pancake in pancakes(0): # Market 0 is Austin
        key = pancake_key(pancake)

        if key in db and db[key]['onsale'] != pancake['onsale'] and pancake['onsale']:
            notify(pancake)
        elif key not in db:
            notify(pancake)
    
        db[key] = pancake

    save(PICKLE_FILE, db)
