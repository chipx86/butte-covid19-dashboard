#!/usr/bin/env python3

import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import quote

import requests


CACHE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                          '.http-cache'))
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        '..', 'htdocs', 'data'))
CSV_DIR = os.path.join(DATA_DIR, 'csv')
JSON_DIR = os.path.join(DATA_DIR, 'json')


USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36'
)


class TableauLoader(object):
    def __init__(self, session, owner, sheet, orig_response):
        self.session = session
        self.owner = owner
        self.sheet = sheet
        self.sheet_urlarg = self.sheet.replace(' ', '')
        self.session_id = orig_response.headers['x-session-id']
        self.referer = orig_response.url
        self.raw_bootstrap_payload1 = None
        self.raw_bootstrap_payload2 = None
        self.bootstrap_payload1 = None
        self.bootstrap_payload2 = None

    def bootstrap(self, extra_params={}):
        response = self.session.post(
            ('https://public.tableau.com/vizql/w/%s/v/%s/bootstrapSession/'
             'sessions/%s'
             % (self.owner, self.sheet_urlarg, self.session_id)),
            data=dict({
                'sheet_id': self.sheet,
            }, **extra_params),
            headers={
                'Accept': 'text/javascript',
                'Referer': self.referer,
                'X-Requested-With': 'XMLHttpRequest',
                'x-tsi-active-tab': self.sheet,
                'x-tsi-supports-accepted': 'true',
            })

        # The response contains two JSON payloads, each prefixed by a length.
        data = response.text
        i = data.find(';')
        length = int(data[:i])
        self.raw_bootstrap_payload1 = data[i + 1:length + i + 1]

        data = data[length + i + 1:]
        i = data.find(';')
        length = int(data[:i])
        self.raw_bootstrap_payload2 = data[i + 1:length + i + 1]

    def run_command(self, command, post_data):
        response = self.session.post(
            ('https://public.tableau.com/vizql/w/%s/v/%s/sessions/%s/'
             'commands/%s'
             % (self.owner, self.sheet_urlarg, self.session_id, command)),
            files={
                key: (None, value)
                for key, value in post_data.items()
            },
            headers={
                'Accept': 'text/javascript',
                'Referer': self.referer,
                'Origin': 'https://public.tableau.com',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'X-Requested-With': 'XMLHttpRequest',
                'x-tsi-active-tab': self.sheet,
                'x-tsi-supports-accepted': 'true',
            },
        )

        return response.json()

    def select(self, worksheet, object_ids):
        return self.run_command(
            'tabdoc/select',
            {
                'dashboard': self.sheet,
                'worksheet': worksheet,
                'selection': json.dumps({
                    'objectIds': object_ids,
                    'selectionType': 'tuples',
                }),
                'selectOptions': 'select-options-simple',
            })

    def get_bootstrap_data_dicts(self, expected_counts={}):
        if self.bootstrap_payload2 is None:
            self.bootstrap_payload2 = json.loads(self.raw_bootstrap_payload2)

        return self.get_data_dicts(
            data_columns=(
                self.bootstrap_payload2
                ['secondaryInfo']
                ['presModelMap']
                ['dataDictionary']
                ['presModelHolder']
                ['genDataDictionaryPresModel']
                ['dataSegments']
                ['0']
                ['dataColumns']
            ),
            expected_counts=expected_counts)

    def get_data_dicts(self, data_columns, expected_counts):
        data_dicts = {
            item['dataType']: item['dataValues']
            for item in data_columns
        }

        for key, count in expected_counts.items():
            value_count = len(data_dicts[key])

            if value_count != count:
                raise ParseError('Unexpected number of %s data values: %s'
                                 % (key, value_count))

        return data_dicts


class ParseError(Exception):
    pass


def add_nested_key(d, full_key, value):
    keys = full_key.split(':')

    for key in keys[:-1]:
        d = d.setdefault(key, {})

    d[keys[-1]] = value


def add_or_update_json_date_row(filename, row_data, date_field='date'):
    date_key = row_data[date_field]

    if os.path.exists(filename):
        with open(filename, 'r') as fp:
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
        latest_date_key = dates_data[-1][date_field]
    except (IndexError, KeyError):
        latest_date_key = None

    if latest_date_key == date_key:
        dates_data[-1] = row_data
    else:
        # See if we have days we're missing. If so, we need to fill in the
        # gaps. This is mainly to keep the spreadsheet rows aligned.
        if latest_date_key is not None:
            cur_date = datetime.strptime(date_key, '%Y-%m-%d')
            latest_date = datetime.strptime(latest_date_key, '%Y-%m-%d')

            for day in range(1, (cur_date - latest_date).days):
                dates_data.append({
                    date_field: (latest_date +
                                 timedelta(days=day)).strftime('%Y-%m-%d'),
                })

        dates_data.append(row_data)

    with open(filename, 'w') as fp:
        json.dump(dataset,
                  fp,
                  indent=2,
                  sort_keys=True)


def parse_butte_dashboard(response, out_filename, **kwargs):
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

    m = re.search(r'window.infographicData=(.*);</script>', response.text)

    if not m:
        raise ParseError('Unable to find infographicData in Butte Dashboard')

    try:
        dashboard_data = json.loads(m.group(1))
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

    if datestamp.date() != datetime.now().date():
        # This is stale data not from today. OR it might be new data but
        # the county forgot to update the datestamp on it *again*. So don't
        # risk overwriting historical data, and instead bail.
        return

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

    try:
        row_result = {
            'date': datestamp.strftime('%Y-%m-%d'),
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

    add_or_update_json_date_row(out_filename, row_result)


def convert_json_to_csv(info, in_fp, out_filename, **kwargs):
    def _get_key_value(d, paths):
        for path in paths:
            d = d.get(path)

            if d is None:
                break

        return d

    key_map = info['key_map']
    dataset = json.load(in_fp)

    with open(out_filename, 'w') as fp:
        csv_writer = csv.DictWriter(
            fp,
            fieldnames=[
                key_entry[0]
                for key_entry in key_map
            ])
        csv_writer.writeheader()

        for row in dataset.get('dates', []):
            csv_writer.writerow({
                key: _get_key_value(row, paths)
                for key, paths in key_map
            })


def build_timeline_json(in_fp, out_filename, **kwargs):
    timeline = []
    reader = csv.DictReader(in_fp, delimiter=',')

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

    with open(out_filename, 'w') as fp:
        json.dump(
            {
                'dates': timeline,
            },
            fp,
            sort_keys=True,
            indent=2)


def build_state_resources_json(session, response, out_filename, **kwargs):
    # Set up the session and fetch the initial payloads.
    tableau_loader = TableauLoader(session=session,
                                   owner='COVID-19CountyProfile3',
                                   sheet='County Level Combined',
                                   orig_response=response)
    tableau_loader.bootstrap({
        'showParams': json.dumps({
            'unknownParams': 'County=Butte',
        }),
        'stickySessionKey': json.dumps({
            'workbookId': 6139600,
        }),
    })

    data_dicts = tableau_loader.get_bootstrap_data_dicts()
    date = datetime.strptime(data_dicts['datetime'][-1],
                             '%Y-%m-%d %H:%M:%S')
    county_data_ints = data_dicts['integer']
    county_data_reals = data_dicts['real']

    add_or_update_json_date_row(
        out_filename,
        {
            'date': date.strftime('%Y-%m-%d'),
            'beds': county_data_ints[-2],
            'face_shields': county_data_ints[-6],
            'gloves': county_data_ints[-5],
            'gowns': county_data_ints[-7],
            'procedure_masks': county_data_ints[-8],
            'n95_respirators': county_data_ints[-9],
            'icu_beds_pct': int(round(county_data_reals[-2], 2) *
                                          100),
            'ventilators_pct': int(round(county_data_reals[-1], 2) *
                                             100),
        })


def parse_csv(info, response, out_filename, **kwargs):
    match = info.get('match')

    with open(out_filename, 'wb') as out_fp:
        if match is None:
            out_fp.write(response.content)
        else:
            lines = response.content.splitlines(True)

            out_fp.write(lines[0])

            for line in lines[1:]:
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
        'filename': 'columbia-projections-nochange.csv',
        'format': 'csv',
        'url': 'https://raw.githubusercontent.com/shaman-lab/COVID-19Projection/master/Production/Projection_nochange.csv',
        'match': re.compile(b'^Butte County CA'),
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
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Confirmed Cases', ('confirmed_cases',)),
            ('Deaths', ('deaths',)),
            ('Currently In Isolation', ('in_isolation', 'current')),
            ('Total Released From Isolation', ('in_isolation',
                                               'total_released')),
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
        ],
    },
#    {
#        'filename': 'state-resources.json',
#        'format': 'json',
#        'url': (
#            'https://public.tableau.com/views/COVID-19CountyProfile3/'
#            'CountyLevelCombined?%3AshowVizHome=no&County=Butte'
#        ),
#        'parser': build_state_resources_json,
#    },
#    {
#        'filename': 'state-resources.csv',
#        'format': 'csv',
#        'local_source': {
#            'filename': 'state-resources.json',
#            'format': 'json',
#        },
#        'parser': convert_json_to_csv,
#        'key_map': [
#            ('Date', ('date',)),
#            ('Beds', ('beds',)),
#            ('Face Shields', ('face_shields',)),
#            ('Gloves', ('gloves',)),
#            ('Gowns', ('gowns',)),
#            ('N95 Respirators', ('n95_respirators',)),
#            ('Procedure Masks', ('procedure_masks',)),
#            ('ICU Beds Percent', ('icu_beds_pct',)),
#            ('Ventilators Percent', ('ventilators_pct',)),
#        ],
#    },
    {
        'filename': 'timeline.csv',
        'format': 'csv',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRwJpCeZj4tsxMXqrHFDjIis5Znv-nI0kQk9enEAJAbYzZUBHm7TELQe0wl2huOYEkdaWLyR8N9k_uq/pub?gid=856590862&single=true&output=csv'
    },
    {
        'filename': 'timeline.json',
        'format': 'json',
        'local_source': {
            'filename': 'timeline.csv',
            'format': 'csv',
        },
        'parser': build_timeline_json,
    },
]


def main():
    try:
        with open(CACHE_FILE, 'r') as fp:
            cache = json.load(fp)
    except Exception:
        cache = {}

    for info in FEEDS:
        filename = info['filename']
        out_dir = os.path.join(DATA_DIR, info['format'])

        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        out_filename = os.path.join(out_dir, filename)
        parser = info.get('parser')
        up_to_date = False

        if parser is None and info['format'] == 'csv':
            parser = parse_csv

        if 'url' in info:
            url = info['url']
            url_cache_info = cache.get(url)

            session = requests.Session()
            session.headers['User-Agent'] = USER_AGENT

            headers = {}

            if url_cache_info and os.path.exists(out_filename):
                try:
                    headers['If-None-Match'] = url_cache_info['etag']
                except KeyError:
                    pass

            response = session.get(url, headers=headers)

            if response.status_code == 200:
                try:
                    result = parser(info=info,
                                    response=response,
                                    out_filename=out_filename,
                                    session=session)
                except ParseError as e:
                    sys.stderr.write('Data parse error while building %s: %s\n'
                                     % (filename, e))
                    continue

                if response.headers.get('etag'):
                    cache[url] = {
                        'etag': response.headers['etag'],
                    }
            elif response.status_code == 304:
                up_to_date = True
            else:
                sys.stderr.write('HTTP error %s while fetching %s: %s'
                                 % (response.status_code, filename,
                                    response.text))
                continue
        elif 'local_source' in info:
            local_source = info['local_source']
            source_filename = os.path.join(DATA_DIR, local_source['format'],
                                           local_source['filename'])

            with open(source_filename, 'r') as in_fp:
                try:
                    result = parser(info=info,
                                    in_fp=in_fp,
                                    out_filename=out_filename)
                except ParseError as e:
                    sys.stderr.write('Data parse error while building %s: %s\n'
                                     % (filename, e))
                    continue
        else:
            sys.stderr.write('Invalid feed entry: %r\n' % info)
            continue

        if up_to_date:
            print('Up-to-date: %s' % out_filename)
        else:
            print('Wrote %s' % out_filename)


    with open(CACHE_FILE, 'w') as fp:
        json.dump(cache, fp)


if __name__ == '__main__':
    main()
