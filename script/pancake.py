#!/usr/bin/env python

# License: none (public domain)
# dependencies: beautifulsoup4, dateutil, google-api-python-client, httplib2,
#               oauth2client, pytz, requests, tinycss, uritemplate

import argparse
import lib.PancakeMaster as pm
import logging
import sys

from pytz import timezone


def setup_logging(level):
    """Setups up root logger to log to filename and console simultaneously."""
    log = logging.getLogger()
    log.setLevel(level)

    fh = logging.FileHandler('pancake.log')
    fh.setLevel(level)

    ch = logging.StreamHandler()
    ch.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    log.addHandler(ch)
    log.addHandler(fh)
    return log


if __name__ == '__main__':
    log = setup_logging(logging.INFO)

    usage_help = 'Pancake Master searches for new or on sale Master Pancake shows.'
    parser = argparse.ArgumentParser(description=usage_help)
    parser.add_argument('--market', '-m', metavar='MARKET', type=int, nargs='?',
                        default=0, help='Alamo Drafthouse API market ID number')
    parser.add_argument('--timezone', '-t', metavar='TIMEZONE', type=str, nargs='?',
                        default='US/Central', help='timezone for showtimes')
    parser.add_argument('--disable-notify', '-n', action='store_true',
                        help='disable email notification')
    parser.add_argument('--disable-calendar', '-c', action='store_true',
                        help='disable google calendar updates')
    parser.add_argument('--clear-cache', '-x', action='store_true',
                        help='clear database cache before running')
    args = parser.parse_args()

    try:
        market_timezone = timezone(args.timezone)
    except:
        log.exception('parse error:')
        sys.exit(1)

    if args.clear_cache:
        pm.clear_cache()

    pm.main(args.market, market_timezone,
            disable_notify=args.disable_notify, disable_calendar=args.disable_calendar)
