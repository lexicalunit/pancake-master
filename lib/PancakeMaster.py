# License: none (public domain)

import dateutil
import gzip
import hashlib
import logging
import os
import pickle
import tinycss

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itertools import groupby, count
from cssinline import styled
from GoogleCalendar import GoogleCalendar


RESOURCES_DIRECTORY = 'resources'
PICKLE_FILE = os.path.join(RESOURCES_DIRECTORY, 'pancake.pickle')
STYLE_FILE = os.path.join(RESOURCES_DIRECTORY, 'css', 'pancake.css')
TEMPLATE_FILE = os.path.join(RESOURCES_DIRECTORY, 'template', 'pancake.html')
GOOGLE_CALENDAR_CREDENTIALS_FILE = os.path.join(RESOURCES_DIRECTORY, 'credentials.dat')

DATE_FORMAT = '%A, %B %d, %Y'
TIME_FORMAT = '%I:%M%p'

log = logging.getLogger(__name__)


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
        else:  # pancake['status'] == 'soldout' or pancake['status'] == 'notonsale'
            soup.span.append(time_string(pancake['datetime']))

        showtimes.append(str(soup))
    return showtimes


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
        film_heading.h1['class'] = 'film_heading'
        film_heading.a['href'] = 'https://drafthouse.com/uid/' + film_uid
        film_heading.a.append(film)

        cinema_heading = BeautifulSoup('<h2><a></a></h2>')
        cinema_heading.h2['class'] = 'cinema_heading'
        cinema_heading.a['href'] = cinema_url
        cinema_heading.a.append(cinema)

        item_data = []
        for day, pancakes in groupby(pancakes, key=by_day):
            item_data.append((date_string(day), ', '.join(html_showtimes(pancakes))))

        item_list = BeautifulSoup('<ul></ul>')
        item_list.ul['class'] = 'pancake_items'
        for data, n in zip(item_data, count(1)):
            day, showtimes = data

            item = item_list.new_tag('li')
            item['class'] = 'pancake_item'

            item_content = '<span>{day} - {showtimes}</span>'.format(day=day, showtimes=showtimes)
            item.append(BeautifulSoup(item_content))
            item_list.ul.append(item)

        soup.append(film_heading)
        soup.append(cinema_heading)
        soup.append(item_list)

    content = str(soup)

    # load CSS stylesheet
    try:
        parser = tinycss.make_parser('page3')
        stylesheet = parser.parse_stylesheet_file(STYLE_FILE)
        style = {r.selector.as_css(): {d.name: d.value.as_css() for d in r.declarations} for r in stylesheet.rules}
    except Exception as e:
        log.warn('could not load CSS style file: {}'.format(e))
        style = None

    # load HTML template
    try:
        template = open(TEMPLATE_FILE, 'r').read()
        return styled(template.format(content=content), style)
    except Exception as e:
        log.warn('could not load HTML template file: {}'.format(e))
        return styled(content, style)


def text_digest(pancakes):
    """Returns a plain text digest of the given pancakes."""
    text = ''
    for pancake in sorted(pancakes, key=pancake_sort_key):
        if pancake['status'] == 'onsale':
            status = 'On sale now!'
        elif pancake['status'] == 'soldout':
            status = 'Sold out.'
        else:  # pancake['status'] == 'notonsale'
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
            if db[key]['status'] == 'notonsale' and pancake['status'] == 'onsale':
                updated.append(pancake)
        else:
            updated.append(pancake)

        db[key] = pancake
    return updated


def prune_database(db):
    """Removes old pancakes from the database."""
    for key, pancake in db.items():
        if pancake['datetime'].date() < datetime.now().date():
            del db[key]


def update_calendar(pancakes, market_timezone):
    """Updates our Google Calendar with Master Pancake events."""
    if not pancakes:
        return

    cal = GoogleCalendar(GOOGLE_CALENDAR_CREDENTIALS_FILE)
    calendars = cal.calendar_list()
    pancake_calendar_id = None
    for calendar_list_entry in calendars:
        if calendar_list_entry['summary'] == 'Master Pancakes':
            pancake_calendar_id = calendar_list_entry['id']
    if not pancake_calendar_id:
        raise Exception("Can't find 'Master Pancakes' calendar")
    events = cal.events(pancake_calendar_id)
    for pancake in pancakes:
        p_datetime = pancake['datetime']
        gevent = None
        for event in events:
            gevent_datetime = dateutil.parser.parse(event['start']['dateTime'])
            if event['summary'] == (pancake['film'] + pancake['cinema']) and gevent_datetime == p_datetime:
                gevent = event
                break
        if gevent:
            log.info('{} already in calendar'.format(pancake['film']))
        else:
            end_time = p_datetime + timedelta(hours=2)
            cal.insert_event(pancake_calendar_id, pancake['film'] + pancake['cinema'], p_datetime, end_time, market_timezone.zone)
