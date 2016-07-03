#!/usr/bin/env python

import argparse
import logging
import sys

from lib import PancakeMaster as pm


def setup_logging(level):
    """Sets up root logger to log to filename and console simultaneously."""
    logging.basicConfig(level=level)

    fh = logging.FileHandler('pancake.log')
    fh.setLevel(level)

    ch = logging.StreamHandler()
    ch.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    log = logging.getLogger()
    log.setLevel(level)

    log.addHandler(ch)
    log.addHandler(fh)
    return log


if __name__ == '__main__':
    log = setup_logging(logging.INFO)

    # yapf: disable
    usage_help = 'Pancake Master searches for new or on sale Master Pancake shows.'
    parser = argparse.ArgumentParser(description=usage_help)
    parser.add_argument('--market', '-m', metavar='MARKET', type=str, nargs='?',
                        default='0000', help='Alamo Drafthouse API market ID')
    parser.add_argument('--disable-notify', '-n', action='store_true',
                        help='disable email notification')
    parser.add_argument('--disable-fetch', '-f', action='store_true',
                        help='disable fetching updates, use local cache instead')
    parser.add_argument('--clear-cache', '-x', action='store_true',
                        help='clear database cache before running')
    parser.add_argument('--list', '-l', action='store_true',
                        help='list currently cached pancake database')
    args = parser.parse_args()
    # yapf: enable

    if args.clear_cache:
        pm.clear_cache()

    if args.list:
        pm.show_cache()
        sys.exit(0)

    pm.main(args.market, disable_notify=args.disable_notify, disable_fetch=args.disable_fetch)
