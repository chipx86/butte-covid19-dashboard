#!/usr/bin/env python3

import os
import re
from urllib.request import urlopen


FEEDS = {
    'skilled-nursing-facilities.csv': {
        'format': 'csv',
        'url': 'https://raw.githubusercontent.com/datadesk/california-coronavirus-data/master/cdph-skilled-nursing-facilities.csv',
        'match': re.compile(b'.*Butte,007'),
    },
    'state-hospitals.csv': {
        'format': 'csv',
        'url': 'https://data.chhs.ca.gov/dataset/6882c390-b2d7-4b9a-aefa-2068cee63e47/resource/6cd8d424-dfaa-4bdd-9410-a3d656e1176e/download/covid19data.csv',
        'match': re.compile(b'^Butte,'),
    },
}


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        '..', 'htdocs', 'data'))


for filename, info in FEEDS.items():
    out_filename = os.path.join(DATA_DIR, info['format'], filename)
    match = info['match']

    with urlopen(info['url']) as in_fp:
        with open(out_filename, 'wb') as out_fp:
            if info['format'] == 'csv':
                out_fp.write(in_fp.readline())

                for line in in_fp.readlines():
                    line = line

                    if match.match(line):
                        out_fp.write(line)

    print('Wrote %s' % out_filename)
