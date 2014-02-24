#!/usr/bin/env python

import json
import re
import requests
from termcolor import colored

austin_cinemas = {
    'Ritz': 2,
    'Village': 3,
    'Slaughter Lane': 6,
    'Lakeline': 7,
}

def json_data(data):   
    return json.loads(re.search('.*?({.*)\)', data).group(1))

for cinema_name, cinema_id in austin_cinemas.items():
    r = requests.get('https://d20ghz5p5t1zsc.cloudfront.net/adcshowtimeJson/CinemaSessions.aspx?callback=jQuery18209344239365309477_1393202979246&cinemaid={cinema_id:04.0f}&callback=tix.theaterLinks'.format(cinema_id=cinema_id))
    data = json_data(r.text)

    for date_data in data['Cinema']['Dates']:
        date = date_data['Date']
    
        found_pancake = False
        for film_data in date_data['Films']:
            film = film_data['Film']
            if 'pancake' in film_data['Film'].lower():
                found_pancake = True
                print colored(film.lstrip('Master Pancake: ').lower().title(), 'blue', attrs=['bold'])
                print '{} - {}'.format(date, cinema_name)
                print '    {:10} {:10} {}'.format('On Sale', 'Time', 'Link')
                for session_data in film_data['Sessions']:
                    status = session_data['SessionStatus']
                    if status == 'onsale':
                        print '    {:10} {:10} {}'.format('Yes', session_data['SessionTime'], session_data['SessionSalesURL'])
                    else:
                        print '    {:10} {:10}'.format('No', session_data['SessionTime'])
    
        if found_pancake:
            print
