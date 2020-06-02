#!/usr/bin/env python3

import csv
import json
import os
import sys
from datetime import datetime
from urllib.request import urlopen


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        '..', 'htdocs', 'data'))
CSV_DIR = os.path.join(DATA_DIR, 'csv')
JSON_DIR = os.path.join(DATA_DIR, 'json')


FEEDS = {
    'timeline.csv': {
        'format': 'csv',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRwJpCeZj4tsxMXqrHFDjIis5Znv-nI0kQk9enEAJAbYzZUBHm7TELQe0wl2huOYEkdaWLyR8N9k_uq/pub?gid=856590862&single=true&output=csv'
    },
}


def add_nested_key(d, full_key, value):
    keys = full_key.split(':')

    for key in keys[:-1]:
        d = d.setdefault(key, {})

    d[keys[-1]] = value


def import_feeds():
    for filename, info in FEEDS.items():
        out_filename = os.path.join(DATA_DIR, info['format'], filename)

        with urlopen(info['url']) as in_fp:
            with open(out_filename, 'wb') as out_fp:
                out_fp.write(in_fp.read())

        print('Wrote %s' % out_filename)


# Process timeline.csv.
def process_timeline():
    timeline = []

    with open(os.path.join(CSV_DIR, 'timeline.csv'), 'r') as fp:
        reader = csv.DictReader(fp, delimiter=',')

        for row in reader:
            date_info = {}
            timeline.append(date_info)

            for col_name, col_data in row.items():
                if col_name != 'row_id':
                    if col_data == '':
                        col_data = None
                    else:
                        try:
                            col_data = int(col_data)
                        except ValueError:
                            pass

                    add_nested_key(date_info, col_name, col_data)

    filename = os.path.join(JSON_DIR, 'timeline.json')

    with open(filename, 'w') as fp:
        json.dump(
            {
                'dates': timeline,
            },
            fp,
            sort_keys=True,
            indent=2)

    print('Wrote %s' % filename)


if __name__ == '__main__':
    import_feeds()
    process_timeline()
