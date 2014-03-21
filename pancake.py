#!/usr/bin/env python

# License: none (public domain)
# dependencies: beautifulsoup4, dateutil, google-api-python-client, httplib2, oauth2client, pytz, requests, tinycss, uritemplate

import lib.PancakeMaster as pm
import lib.AlamoDrafthouseAPI as api
import logging

from pytz import timezone


LOG_FILE = 'pancake.log'
MARKET_TIMEZONE = timezone('US/Central') # Austin is US/Central
PANCAKE_MARKET = 0 # 0 is Austin's market id
RECIPIENTS_FILE = 'pancake.list'


def setup_logging(filename):
    """Setups up root logger to log to filename and console simultaneously."""
    log = logging.getLogger()
    log.setLevel(logging.INFO)

    fh = logging.FileHandler(filename)
    fh.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    log.addHandler(ch)
    log.addHandler(fh)


if __name__ == '__main__':
    setup_logging(LOG_FILE)
    log = logging.getLogger()

    try:
        db = pm.load_database()
    except:
        log.warn('creating new pancake database...')
        db = {}

    try:
        recipients = [line.strip() for line in open(RECIPIENTS_FILE)]
    except:
        recipients = None
        log.warn('no email recipients found, not sending email notifications...')

    try:
        pancakes = api.query_pancakes(PANCAKE_MARKET, MARKET_TIMEZONE)
        updated = pm.update_pancakes(db, pancakes)
        pm.update_calendar(updated, MARKET_TIMEZONE)
        pm.notify(updated, recipients)
        pm.prune_database(db)
        pm.save_database(db)
    except:
        log.exception('fatal error:')
