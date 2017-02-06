# License: none (public domain)

import errno
import gzip
import hashlib
import logging
import os
import pickle
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itertools import count, groupby

from bs4 import BeautifulSoup

import tinycss
from lib import AlamoDrafthouseAPI as api
from lib.InlineCSS import styled

logging.basicConfig()
log = logging.getLogger(__name__)

RESOURCES_DIRECTORY = 'resources'
PICKLE_FILE = os.path.join(RESOURCES_DIRECTORY, 'cache', 'pancake.pickle')
RECIPIENTS_FILE = os.path.join(RESOURCES_DIRECTORY, 'config', 'pancake.list')
OVERRIDES_FILE = os.path.join(RESOURCES_DIRECTORY, 'config', 'overrides.list')
USER_FILE = os.path.join(RESOURCES_DIRECTORY, 'config', 'user')
PASS_FILE = os.path.join(RESOURCES_DIRECTORY, 'config', 'pass')
STYLE_FILE = os.path.join(RESOURCES_DIRECTORY, 'css', 'pancake.css')
TEMPLATE_FILE = os.path.join(RESOURCES_DIRECTORY, 'template', 'pancake.html')

DATE_FORMAT = '%A, %B %d, %Y'
TIME_FORMAT = '%I:%M%p'


def date_string(dt):
    """Returns a date string representation of the given datetime object."""
    return datetime.strftime(dt, DATE_FORMAT)


def time_string(dt):
    """Returns a time string representation of the given datetime object."""
    ts = datetime.strftime(dt, TIME_FORMAT).lstrip('0')
    return ts[:-2] + 'p' if ts.endswith('PM') else ts[:-2]


def datetime_string(dt):
    """Returns a date and time string representation of the given datetime object."""
    return date_string(dt) + ' - ' + time_string(dt)


def pancake_sort_key(pancake):
    """Key to sort pancakes by film title, cinema location, and datetime of the show."""
    return pancake.film_name, pancake.cinema.cinema_name, pancake.film_datetime


def html_showtimes(pancakes):
    """Returns a list of pancake showtimes, as pancake HTML."""
    showtimes = []
    for pancake in pancakes:
        soup = BeautifulSoup('<span></span>')
        soup.span['class'] = pancake.film_status

        if pancake.film_status == 'onsale':
            anchor = soup.new_tag('a', href=pancake.film_url)
            anchor.append(time_string(pancake.film_datetime))
            soup.span.append(anchor)
        else:  # pancake.film_status == 'soldout' or pancake.film_status == 'notonsale'
            soup.span.append(time_string(pancake.film_datetime))

        showtimes.append(str(soup))
    return showtimes


def html_digest(pancakes):
    """Returns pancake styled HTML digest of the given pancakes."""
    pancakes = sorted(pancakes, key=pancake_sort_key)

    # things to group by
    by_film_cinema = lambda p: (p.film_id, p.film_name, p.cinema.cinema_url, p.cinema.cinema_name)
    by_day = lambda p: p.film_datetime.date()

    soup = BeautifulSoup('')
    for key, pancakes in groupby(pancakes, key=by_film_cinema):
        film_id, film, cinema_url, cinema = key

        film_heading = BeautifulSoup('<h1><a></a></h1>')
        film_heading.h1['class'] = 'film_heading'
        film_heading.a['href'] = 'https://drafthouse.com/uid/' + film_id
        film_heading.a.append(film)

        cinema_name = 'Alamo Drafthouse ' + cinema
        if cinema_url:
            cinema_heading = BeautifulSoup('<h2><a></a></h2>')
            cinema_heading.h2['class'] = 'cinema_heading'
            cinema_heading.a['href'] = cinema_url
            cinema_heading.a.append(cinema_name)
        else:
            cinema_heading = BeautifulSoup('<h2></h2>')
            cinema_heading.h2['class'] = 'cinema_heading'
            cinema_heading.h2.append(cinema_name)

        item_data = []
        for day, pancakes in groupby(pancakes, key=by_day):
            item_data.append((date_string(day), ', '.join(html_showtimes(pancakes))))

        item_list = BeautifulSoup('<ul></ul>')
        item_list.ul['class'] = 'film_items'
        for data, n in zip(item_data, count(1)):
            day, showtimes = data

            item = item_list.new_tag('li')
            item['class'] = 'film_item'

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
        style = {
            r.selector.as_css(): {d.name: d.value.as_css()
                                  for d in r.declarations}
            for r in stylesheet.rules
        }
    except Exception as e:
        log.warn('could not load CSS style file: {}'.format(e))
        style = None

    # load HTML template
    try:
        with open(TEMPLATE_FILE, 'r') as f:
            template = f.read()
        return styled(template.format(content=content), style)
    except Exception as e:
        log.warn('could not load HTML template file: {}'.format(e))
        return styled(content, style)


def text_digest(pancakes):
    """Returns a plain text digest of the given pancakes."""
    text = ''
    for pancake in sorted(pancakes, key=pancake_sort_key):
        if pancake.film_status == 'onsale':
            status = 'On sale now!'
        elif pancake.film_status == 'soldout':
            status = 'Sold out.'
        else:  # pancake.film_status == 'notonsale'
            status = 'Not on sale yet.'
        params = (
            pancake.film_name.encode('utf-8'),
            pancake.cinema.cinema_name,
            date_string(pancake.film_datetime),
            time_string(pancake.film_datetime),
            status, )
        text += '{}\n{}\n{}\n{}\n{}'.format(*params)
        if pancake.film_status == 'onsale':
            text += '\n{}'.format(pancake.film_url)
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
    msg['To'] = 'undisclosed-recipients'
    msg['From'] = recipients[0]
    msg.attach(MIMEText(plain, 'plain'))
    msg.attach(MIMEText(html_digest(pancakes), 'html'))

    try:
        s = smtplib.SMTP('localhost')
        s.set_debuglevel(1)
        s.login(load_user(), load_pass())
        s.sendmail(msg['From'], recipients, msg.as_string())
        s.quit()
        log.info('sent email(s) to {}'.format(', '.join(recipients)))
    except Exception as e:
        log.error('email fail: {}'.format(e))
        raise


def pancake_key(pancake):
    """Creates a unique id for a given pancake."""
    m = hashlib.md5()
    m.update(pancake.film_name.encode('utf-8'))
    m.update(pancake.cinema.cinema_name.encode('utf-8'))
    m.update(datetime_string(pancake.film_datetime).encode('utf-8'))
    return m.hexdigest()


def save_database(db):
    """Saves pancake database to disk."""
    filename = PICKLE_FILE
    log.info('saving {}'.format(filename))
    try:
        with gzip.GzipFile(filename, 'wb') as f:
            f.write(pickle.dumps(db, 1))
    except Exception as e:
        log.error('save failure: {}'.format(e))
        raise


def load_database():
    """Unpickles and decompresses the given file and returns the created object."""
    filename = PICKLE_FILE
    log.info('loading {}'.format(filename))

    try:
        with gzip.open(filename, 'rb') as f:
            data = f.read()
            return pickle.loads(data)
    except Exception as e:
        log.error('load failure: {}'.format(e))
        log.warn('creating new pancake database...')
    return {}


def update_pancakes(db, pancakes):
    """Updates database given the list of all pancakes, returns list of updated pancakes."""
    updated = []
    for pancake in pancakes:
        key = pancake_key(pancake)

        if key in db:
            if db[key].film_status == 'notonsale' and pancake.film_status == 'onsale':
                updated.append(pancake)
        else:
            updated.append(pancake)

        db[key] = pancake
    return updated


def prune_database(db):
    """Removes old pancakes from the database."""
    for key, pancake in db.items():
        if pancake.film_datetime.date() < datetime.now().date():
            del db[key]


def load_user():
    with open(USER_FILE) as f:
        return f.readlines()[0].strip()


def load_pass():
    with open(PASS_FILE) as f:
        return f.readlines()[0].strip()


def load_recipients():
    """Returns list of email addresses to notify."""
    try:
        with open(RECIPIENTS_FILE) as f:
            return [line for line in (line.strip() for line in f.readlines()) if line]
    except:
        log.warn('no email recipients found, not sending email notifications...')
    return []


def load_overrides():
    """Returns list of film overrides to notify for in addition to pancakes."""
    try:
        with open(OVERRIDES_FILE) as f:
            return [line for line in (line.strip() for line in f.readlines()) if line]
    except:
        pass
    return []


def mkdir_p(path):
    """Make directory without error if it already exists."""
    try:
        os.makedirs(path, exist_ok=True)  # python 3.2+
    except TypeError as e:
        try:
            os.makedirs(path)
        except OSError as e:  # python <2.5
            if e.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise


def clear_cache():
    """Deletes existing pancake database."""
    try:
        os.remove(PICKLE_FILE)
    except:
        log.exception('clearing cache:')


def show_cache():
    """Shows text digest of existing pancake database."""
    try:
        db = load_database()
        log.info(text_digest(db.values()))
    except:
        log.exception('loading cache:')


def main(market, disable_notify=False, disable_fetch=False):
    """Fetches pancake data, send notifications, and reports updates."""
    mkdir_p(os.path.join(RESOURCES_DIRECTORY, 'config'))
    mkdir_p(os.path.join(RESOURCES_DIRECTORY, 'cache'))

    db = load_database()
    recipients = load_recipients()
    overrides = load_overrides()

    if not disable_fetch:
        try:
            pancakes = api.query_pancakes(market, overrides)
        except:
            pancakes = []
            log.exception('api error:')

        updated = update_pancakes(db, pancakes)
    else:
        updated = db.values()

    if not disable_notify:
        try:
            notify(updated, recipients)
        except:
            log.exception('notification error:')

    prune_database(db)
    save_database(db)
