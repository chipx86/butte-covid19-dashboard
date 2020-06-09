#!/usr/bin/env python3

import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen


class ParseError(Exception):
    pass


def parse_butte_dashboard(info, in_fp, out_filename):
    def get_entity(entity_id):
        return (
            dashboard_data['elements']['content']['content']
            ['entities'][entity_id]
        )

    def get_counter_value(entity_id, expected_labels, label_first=False):
        entity = get_entity(entity_id)
        blocks = entity['props']['content']['blocks']

        if blocks[0]['text'].lower() in expected_labels:
            value = blocks[1]['text']
        elif blocks[1]['text'].lower() in expected_labels:
            value = blocks[0]['text']
        else:
            found_labels = [
                block['text'].lower()
                for block in blocks
            ]

            raise ParseError('Expected one of label %r to be one of %r for '
                             'entity %s'
                             % (found_labels, expected_labels, entity_id))

        try:
            return int(value)
        except Exception:
            raise ParseError('Expected value %r for entity %s to be int, '
                             'got %s'
                             % (value, entity_id, type(value)))

    def get_chart_info(entity_id):
        entity = get_entity(entity_id)
        data = entity['props']['chartData']['data'][0]

        return {
            row[0]: int(row[1])
            for row in data[1:]
        }

    html = in_fp.read()
    m = re.search(br'window.infographicData=(.*);</script>', html)

    if not m:
        raise ParseError('Unable to find infographicData in Butte Dashboard')

    try:
        dashboard_data = json.loads(m.group(1).decode('utf-8'))
    except Exception as e:
        raise ParseError('Unable to parse infographicData in Butte Dashboard: '
                         '%s'
                         % e)

    entity = get_entity('8af333ad-f476-48c5-8faa-d502b1dd6360')
    m = re.search(r'As of (\d+)/(\d+)/(\d{4})',
                  entity['props']['content']['blocks'][0]['text'])

    if not m:
        raise ParseError('Unable to find datestamp in Butte Dashboard')

    datestamp = datetime(month=int(m.group(1)),
                         day=int(m.group(2)),
                         year=int(m.group(3)))

    COUNTER_KEYS_TO_ENTITIES = {
        'confirmed_cases': {
            'labels': ['confirmed cases'],
            'entity_id': '15b62ec3-79df-492a-9171-f92c09dbe3c4',
        },
        'in_isolation': {
            'labels': ['currently in isolation'],
            'entity_id': '569b986d-bb02-48dc-ae00-15b58b58f712',
        },
        'released_from_isolation': {
            'labels': ['released from isolation'],
            'entity_id': 'f335bb23-9900-4acf-854a-8214e532c1de',
        },
        'deaths': {
            'labels': ['death', 'deaths'],
            'entity_id': '9c8d7a74-c196-40b5-a2e5-3bd643bbae8b',
        },
        'daily_viral_test_results': {
            'labels': ['daily viral test results'],
            'entity_id': '50f7771c-d7fb-49bf-8fb6-604ff802d2d9',
        },
        'total_viral_tests': {
            'labels': ['total viral tests'],
            'entity_id': 'bdc32af3-587c-462b-b88a-367835d6bf8b',
        },
        'hospitalized': {
            'labels': ['currently hospitalized'],
            'entity_id': '3f7e639a-c67b-48b3-8b29-f552c9a30dcf',
        },
    }

    CHART_KEYS_TO_ENTITIES = {
        'by_age': '9ba3a895-019a-4e68-99ec-0eb7b5bd026c',
        'by_region': 'b26b9acd-b036-40bc-bbbe-68667dd338e4',
    }

    scraped_data = {
        key: get_counter_value(info['entity_id'],
                               expected_labels=info['labels'])
        for key, info in COUNTER_KEYS_TO_ENTITIES.items()
    }
    scraped_data.update({
        key: get_chart_info(entity_id)
        for key, entity_id in CHART_KEYS_TO_ENTITIES.items()
    })

    date_key = datestamp.strftime('%Y-%m-%d')

    try:
        row_result = {
            'date': date_key,
            'confirmed_cases': scraped_data['confirmed_cases'],
            'deaths': scraped_data['deaths'],
            'in_isolation': {
                'current': scraped_data['in_isolation'],
                'total_released': scraped_data['released_from_isolation'],
            },
            'viral_tests': {
                'total': scraped_data['total_viral_tests'],
                'results': scraped_data['daily_viral_test_results'],
            },
            'hospitalized': {
                'current': scraped_data['hospitalized'],
            },
            'age_ranges_in_years': {
                '0-17': scraped_data['by_age']['0-17 Years'],
                '18-49': scraped_data['by_age']['18-49 Years'],
                '50-64': scraped_data['by_age']['50-64 Years'],
                '65_plus': scraped_data['by_age']['65+ Years'],
            },
            'regions': {
                region.lower(): value
                for region, value in scraped_data['by_region'].items()
            },
        }
    except Exception as e:
        raise ParseError('Unable to build row data: %s' % e)

    if os.path.exists(out_filename):
        with open(out_filename, 'r') as fp:
            try:
                dataset = json.load(fp)
            except Exception as e:
                raise ParseError('Unable to load existing dataset: %s', e)
    else:
        dataset = {
            'dates': [],
        }

    dates_data = dataset['dates']

    try:
        latest_date_key = dates_data[-1]['date']
    except (IndexError, KeyError):
        latest_date_key = None

    if latest_date_key == date_key:
        dates_data[-1] = row_result
    else:
        # See if we have days we're missing. If so, we need to fill in the
        # gaps. This is mainly to keep the spreadsheet rows aligned.
        latest_date = datetime.strptime(latest_date_key, '%Y-%m-%d')

        for day in range(1, (datestamp - latest_date).days):
            day_str = (latest_date + timedelta(days=day)).strftime('%Y-%m-%d')
            dates_data.append({
                'date': day_str,
            })

        dates_data.append(row_result)

    with open(out_filename, 'w') as fp:
        json.dump(dataset,
                  fp,
                  indent=2,
                  sort_keys=True)


def convert_butte_dashboard_to_csv(info, in_fp, out_filename):
    def _get_key_value(d, paths):
        for path in paths:
            d = d.get(path)

            if d is None:
                break

        return d

    dataset = json.load(in_fp)

    KEY_MAP = [
        ('Date', ('date',)),
        ('Confirmed Cases', ('confirmed_cases',)),
        ('Deaths', ('deaths',)),
        ('Currently In Isolation', ('in_isolation', 'current')),
        ('Total Released From Isolation', ('in_isolation', 'total_released')),
        ('Total Viral Tests', ('viral_tests', 'total')),
        ('Daily Viral Test Results', ('viral_tests', 'results')),
        ('Currently Hospitalized', ('hospitalized', 'current')),
        ('Age 0-17 Years', ('age_ranges_in_years', '0-17')),
        ('Age 18-49 Years', ('age_ranges_in_years', '18-49')),
        ('Age 50-64 Years', ('age_ranges_in_years', '50-64')),
        ('Age 65+ Years', ('age_ranges_in_years', '65_plus')),
        ('Chico Cases', ('regions', 'chico')),
        ('Gridley Cases', ('regions', 'gridley')),
        ('Oroville Cases', ('regions', 'oroville')),
        ('Other Region Cases', ('regions', 'other')),
    ]

    with open(out_filename, 'w') as fp:
        csv_writer = csv.DictWriter(
            fp,
            fieldnames=[
                key_entry[0]
                for key_entry in KEY_MAP
            ])
        csv_writer.writeheader()

        for row in dataset.get('dates', []):
            csv_writer.writerow({
                key: _get_key_value(row, paths)
                for key, paths in KEY_MAP
            })


def parse_csv(info, in_fp, out_filename):
    match = info['match']

    with open(out_filename, 'wb') as out_fp:
        out_fp.write(in_fp.readline())

        for line in in_fp.readlines():
            line = line

            if match.match(line):
                out_fp.write(line)


FEEDS = [
    {
        'filename': 'skilled-nursing-facilities.csv',
        'format': 'csv',
        'url': 'https://raw.githubusercontent.com/datadesk/california-coronavirus-data/master/cdph-skilled-nursing-facilities.csv',
        'match': re.compile(b'.*Butte,007'),
    },
    {
        'filename': 'state-hospitals.csv',
        'format': 'csv',
        'url': 'https://data.chhs.ca.gov/dataset/6882c390-b2d7-4b9a-aefa-2068cee63e47/resource/6cd8d424-dfaa-4bdd-9410-a3d656e1176e/download/covid19data.csv',
        'match': re.compile(b'^Butte,'),
    },
    {
        'filename': 'butte-dashboard.json',
        'format': 'json',
        'url': 'https://infogram.com/1pe66wmyjnmvkrhm66x9362kp3al60r57ex',
        'parser': parse_butte_dashboard,
    },
    {
        'filename': 'butte-dashboard.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'butte-dashboard.json',
            'format': 'json',
        },
        'parser': convert_butte_dashboard_to_csv,
    },
]


DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        '..', 'htdocs', 'data'))


for info in FEEDS:
    filename = info['filename']
    out_filename = os.path.join(DATA_DIR, info['format'], filename)
    parser = info.get('parser')

    if parser is None and info['format'] == 'csv':
        parser = parse_csv

    if 'url' in info:
        with urlopen(info['url']) as in_fp:
            try:
                result = parser(info, in_fp, out_filename)
            except ParseError as e:
                sys.stderr.write('Data parse error while building %s: %s\n'
                                 % (filename, e))
                continue
    elif 'local_source' in info:
        local_source = info['local_source']
        source_filename = os.path.join(DATA_DIR, local_source['format'],
                                       local_source['filename'])

        with open(source_filename, 'r') as in_fp:
            try:
                result = parser(info, in_fp, out_filename)
            except ParseError as e:
                sys.stderr.write('Data parse error while building %s: %s\n'
                                 % (filename, e))
                continue
    else:
        sys.stderr.write('Invalid feed entry: %r\n' % info)

    print('Wrote %s' % out_filename)
