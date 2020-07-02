#!/usr/bin/env python3

import codecs
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
            'labels': ['released from isolation', 'recovered'],
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

    # We've hit issues where we've encountered empty data for the last few
    # days when pulling from the spreadsheet. That should not be happening.
    # Look for this and bail if we have to.
    found_cases = False

    for row in timeline[-3:]:
        if row['confirmed_cases']['total'] is not None:
            found_cases = True
            break

    if not found_cases:
        sys.stderr.write('Got an empty timeline dataset! Not writing.')
        return False

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

    pres_model_map = (
        tableau_loader.bootstrap_payload2
        ['secondaryInfo']
        ['presModelMap']
        ['vizData']
        ['presModelHolder']
        ['genPresModelMapPresModel']
        ['presModelMap']
    )

    def _get_data_value(name, field_caption, expected_data_type):
        data_pres_model = (
            pres_model_map
            [name]
            ['presModelHolder']
            ['genVizDataPresModel']
            ['paneColumnsData']
        )
        viz_cols_data = data_pres_model['vizDataColumns']

        for viz_col_data in viz_cols_data:
            if viz_col_data.get('fieldCaption') == field_caption:
                col_index = viz_col_data['columnIndices'][0]
                data_type = viz_col_data['dataType']
                pane_index = viz_col_data['paneIndices'][0]
                break
        else:
            raise ParseError('fieldCaption "%s" not found for "%s"'
                             % (field_caption, name))

        if data_type != expected_data_type:
            raise ParseError('Unexpected data type "%s" found for "%s"'
                             % (data_type, name))

        data_index = (
            data_pres_model
            ['paneColumnsList']
            [pane_index]
            ['vizPaneColumns']
            [col_index]
            ['aliasIndices']
            [0]
        )

        return data_dicts[data_type][data_index]

    # NOTE: Ideally we'd look this up from "Last Updated Date", but I'm still
    #       unsure how these map into a dataValues with a negative
    #       aliasIndices. So while this isn't correct, it's sort of what
    #       we've got right now.
    last_updated = datetime.strptime(
        sorted(data_dicts['datetime'])[-1],
        '%Y-%m-%d %H:%M:%S')

    beds = _get_data_value('Sheet 42',
                           'SUM(Bed Reporting (Fixed))',
                           'integer')
    face_shields = _get_data_value('Face Shields Distributed',
                                   'AGG(TableCalc Filled)',
                                   'integer')
    gloves = _get_data_value('Gloves Distributed',
                             'AGG(TableCalc Filled)',
                             'integer')
    gowns = _get_data_value('Gowns Distributed',
                            'AGG(TableCalc Filled)',
                            'integer')
    procedure_masks = _get_data_value('Proc Masks Distributed',
                                      'AGG(TableCalc Filled)',
                                      'integer')
    n95_respirators = _get_data_value('N95 Distributed',
                                      'AGG(TableCalc Filled)',
                                      'integer')
    icu_beds_pct = _get_data_value('ICU Beds Available BAN',
                                   'AGG(ICU Availability)',
                                   'real')
    ventilators_pct = _get_data_value('Ventilators Available %',
                                      'AGG(Ventilators Available %)',
                                      'real')

    add_or_update_json_date_row(
        out_filename,
        {
            'date': last_updated.strftime('%Y-%m-%d'),
            'beds': beds,
            'face_shields': face_shields,
            'gloves': gloves,
            'gowns': gowns,
            'procedure_masks': procedure_masks,
            'n95_respirators': n95_respirators,
            'icu_beds_pct': int(round(icu_beds_pct, 2) * 100),
            'ventilators_pct': int(round(ventilators_pct, 2) * 100),
        })


def build_hospital_cases_json(session, response, out_filename, **kwargs):
    hospital_keys = {
        'Enloe Medical Center - Esplanade Campus': 'enloe_hospital',
        'Oroville Hospital': 'oroville_hospital',
        'Orchard Hospital': 'orchard_hospital',
    }

    tableau_loader = TableauLoader(session=session,
                                   owner='COVID-19PublicDashboard',
                                   sheet='Covid-19 Hospitals',
                                   orig_response=response)
    tableau_loader.bootstrap({
        'showParams': json.dumps({
            'unknownParams': 'COUNTY=Butte',
        }),
        'stickySessionKey': json.dumps({
            'workbookId': 5911876,
        }),
    })

    data_dicts = tableau_loader.get_bootstrap_data_dicts()
    date = datetime.strptime(
        sorted(data_dicts['datetime'])[-1],
        '%Y-%m-%d %H:%M:%S.%f')

    pres_model_map = (
        tableau_loader.bootstrap_payload2
        ['secondaryInfo']
        ['presModelMap']
        ['vizData']
        ['presModelHolder']
        ['genPresModelMapPresModel']
        ['presModelMap']
        ['Map Patients']
        ['presModelHolder']
        ['genVizDataPresModel']
        ['paneColumnsData']
    )

    pane_columns = (
        pres_model_map
        ['paneColumnsList']
        [1]
        ['vizPaneColumns']
    )

    real_dicts = data_dicts['real']
    cstring_dicts = data_dicts['cstring']

    # Find the columns we care about.
    hospital_names = []
    counts = []

    for viz_col_data in pres_model_map['vizDataColumns']:
        caption = viz_col_data.get('fieldCaption')
        data_type = viz_col_data.get('dataType')

        if caption == 'Hospital Name' and data_type == 'cstring':
            col_index = viz_col_data['columnIndices'][0]

            for i in pane_columns[col_index]['aliasIndices']:
                hospital_names.append(cstring_dicts[i])
        elif caption == 'AGG(Selector KPI)' and data_type == 'real':
            col_index = viz_col_data['columnIndices'][0]

            for i in pane_columns[col_index]['aliasIndices']:
                counts.append(real_dicts[i])

        if hospital_names and counts:
            break

    if not hospital_names:
        raise ParseError('Unable to find hospital names.')

    if not counts:
        raise ParseError('Unable to find hospital case counts.')

    if len(hospital_names) != len(counts):
        raise ParseError('Number of hospital names (%s) does not match '
                         'number of case counts (%s).'
                         % (len(hospital_names), len(counts)))

    hospital_cases = {
        hospital_keys.get(hospital_name, hospital_name): count
        for hospital_name, count in zip(hospital_names, counts)
    }
    hospital_cases['date'] = date.strftime('%Y-%m-%d')

    add_or_update_json_date_row(out_filename, hospital_cases)


def parse_csv(info, response, out_filename, **kwargs):
    csv_info = info.get('csv', {})
    columns = csv_info['columns']
    match = csv_info.get('match_row')
    sort_by = csv_info.get('sort_by')
    validator = csv_info.get('validator')
    unique_col = csv_info.get('unique_col')

    unique_found = set()
    results = []

    reader = csv.DictReader(codecs.iterdecode(response.iter_lines(), 'utf-8'),
                            delimiter=',')

    for row in reader:
        if match is not None and not match(row):
            continue

        row_result = {}

        for col_info in columns:
            dest_name = col_info['name']
            src_name = col_info.get('source_column', dest_name)
            data_type = col_info.get('type')

            try:
                value = row[src_name]
            except KeyError:
                raise ParseError('Missing column in CSV file: %s' % src_name)

            if data_type == 'date':
                try:
                    row_result[dest_name] = (
                        datetime.strptime(value, col_info['format'])
                        .strftime('%Y-%m-%d')
                    )
                except Exception:
                    raise ParseError('Unable to parse date "%s" using format '
                                     '"%s"'
                                     % (value, col_info['format']))
            else:
                row_result[dest_name] = value

        if unique_col is None:
            results.append(row_result)
        elif isinstance(unique_col, tuple):
            unique_values = tuple(
                row_result[_col]
                for _col in unique_col
            )

            if unique_values not in unique_found:
                # We haven't encountered this row before. Add it to the
                # results.
                results.append(row_result)
                unique_found.add(unique_values)
        else:
            unique_value = row_result[unique_col]

            if unique_value not in unique_found:
                # We haven't encountered this row before. Add it to the
                # results.
                results.append(row_result)
                unique_found.add(unique_value)

    # Some datasets are unordered or not in an expected order. If needed, sort.
    if sort_by is not None:
        results = sorted(results, key=lambda row: row[sort_by])

    # Validate that we have the data we expect. We don't want to be offset by
    # a row or have garbage or something.
    if validator is not None and not validator(results):
        raise ParseError('Resulting CSV file did not pass validation!')

    with open(out_filename, 'w') as out_fp:
        writer = csv.DictWriter(
            out_fp,
            fieldnames=[
                col_info['name']
                for col_info in columns
            ])
        writer.writeheader()

        for row_result in results:
            writer.writerow(row_result)


FEEDS = [
    {
        'filename': 'skilled-nursing-facilities-v2.csv',
        'format': 'csv',
        'url': 'https://raw.githubusercontent.com/datadesk/california-coronavirus-data/master/cdph-skilled-nursing-facilities.csv',
        'csv': {
            'match_row': lambda row: row['county'] == 'Butte',
            'validator': lambda results: results[0]['date'] == '2020-04-24',
            'sort_by': 'date',
            'unique_col': ('date', 'name'),
            'columns': [
                {
                    'name': 'date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {'name': 'name'},
                {'name': 'staff_active_cases'},
                {'name': 'patients_active_cases'},
                {'name': 'staff_confirmed_cases'},
                {'name': 'patients_confirmed_cases'},
                {'name': 'staff_confirmed_cases_note'},
                {'name': 'patients_confirmed_cases_note'},
                {'name': 'staff_deaths'},
                {'name': 'patients_deaths'},
                {'name': 'staff_deaths_note'},
                {'name': 'patients_deaths_note'},
            ],
        },
    },
    {
        'filename': 'state-hospitals-v3.csv',
        'format': 'csv',
        'url': 'https://data.ca.gov/dataset/529ac907-6ba1-4cb7-9aae-8966fc96aeef/resource/42d33765-20fd-44b8-a978-b083b7542225/download/hospitals_by_county.csv',
        'csv': {
            'match_row': lambda row: row['county'] == 'Butte',
            'validator': lambda results: results[0]['date'] == '2020-03-29',
            'sort_by': 'date',
            'unique_col': 'date',
            'columns': [
                {
                    'name': 'date',
                    'source_column': 'todays_date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {'name': 'hospitalized_covid_confirmed_patients'},
                {'name': 'hospitalized_suspected_covid_patients'},
                {'name': 'icu_covid_confirmed_patients'},
                {'name': 'icu_suspected_covid_patients'},
                {'name': 'all_hospital_beds'},
                {'name': 'icu_available_beds'},
            ],
        },
    },
    {
        'filename': 'columbia-projections-nochange.csv',
        'format': 'csv',
        'url': 'https://raw.githubusercontent.com/shaman-lab/COVID-19Projection/master/Production/Projection_nochange.csv',
        'csv': {
            'match_row': lambda row: row['county'] == 'Butte County CA',
            'sort_by': 'date',
            'unique_col': 'date',
            'columns': [
                {
                    'name': 'date',
                    'source_column': 'Date',
                    'type': 'date',
                    'format': '%m/%d/%y',
                },
                {'name': 'report_2.5'},
                {'name': 'report_25'},
                {'name': 'report_50'},
                {'name': 'report_75'},
                {'name': 'report_97.5'},
                {'name': 'total_2.5'},
                {'name': 'total_25'},
                {'name': 'total_50'},
                {'name': 'total_75'},
                {'name': 'total_97.5'},
            ],
        },
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
    {
        'filename': 'state-resources.json',
        'format': 'json',
        'url': (
            'https://public.tableau.com/views/COVID-19CountyProfile3/'
            'CountyLevelCombined?%3AshowVizHome=no&County=Butte'
        ),
        'parser': build_state_resources_json,
    },
    {
        'filename': 'state-resources.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'state-resources.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Beds', ('beds',)),
            ('Face Shields', ('face_shields',)),
            ('Gloves', ('gloves',)),
            ('Gowns', ('gowns',)),
            ('N95 Respirators', ('n95_respirators',)),
            ('Procedure Masks', ('procedure_masks',)),
            ('ICU Beds Percent', ('icu_beds_pct',)),
            ('Ventilators Percent', ('ventilators_pct',)),
        ],
    },
    {
        'filename': 'hospital-cases.json',
        'format': 'json',
        'url': (
            'https://public.tableau.com/views/COVID-19HospitalsDashboard/'
            'Hospitals?&:showVizHome=no'
        ),
        'parser': build_hospital_cases_json,
    },
    {
        'filename': 'hospital-cases.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'hospital-cases.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Enloe Hospital', ('enloe_hospital',)),
            ('Oroville Hospital', ('oroville_hospital',)),
            ('Orchard Hospital', ('orchard_hospital',)),
        ],
    },
    {
        'filename': 'timeline.csv',
        'format': 'csv',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRwJpCeZj4tsxMXqrHFDjIis5Znv-nI0kQk9enEAJAbYzZUBHm7TELQe0wl2huOYEkdaWLyR8N9k_uq/pub?gid=856590862&single=true&output=csv',
        'csv': {
            'validator': lambda results: (
                len(results) > 0 and
                results[0]['date'] == '2020-03-20' and
                (results[-1]['confirmed_cases:total'] != '' or
                 results[-2]['confirmed_cases:total'] != '' or
                 results[-3]['confirmed_cases:total'] != '')
            ),
            'columns': [
                {
                    'name': 'date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {'name': 'confirmed_cases:total'},
                {'name': 'confirmed_cases:delta_total'},
                {'name': 'in_isolation:current'},
                {'name': 'in_isolation:delta_current'},
                {'name': 'in_isolation:total_released'},
                {'name': 'in_isolation:delta_total_released'},
                {'name': 'deaths:total'},
                {'name': 'deaths:delta_total'},
                {'name': 'viral_tests:total'},
                {'name': 'viral_tests:delta_total'},
                {'name': 'viral_tests:results'},
                {'name': 'viral_tests:delta_results'},
                {'name': 'viral_tests:pending'},
                {'name': 'viral_tests:delta_pending'},
                {'name': 'hospitalizations:county_data:hospitalized'},
                {'name': 'hospitalizations:state_data:positive'},
                {'name': 'hospitalizations:state_data:delta_positive'},
                {'name': 'hospitalizations:state_data:suspected_positive'},
                {'name': 'hospitalizations:state_data:delta_suspected_positive'},
                {'name': 'hospitalizations:state_data:icu_positive'},
                {'name': 'hospitalizations:state_data:delta_icu_positive'},
                {'name': 'hospitalizations:state_data:icu_suspected'},
                {'name': 'hospitalizations:state_data:delta_icu_suspected'},
                {'name': 'hospitalizations:state_data:enloe_hospital'},
                {'name': 'hospitalizations:state_data:delta_enloe_hospital'},
                {'name': 'hospitalizations:state_data:oroville_hospital'},
                {'name': 'hospitalizations:state_data:delta_oroville_hospital'},
                {'name': 'hospitalizations:state_data:orchard_hospital'},
                {'name': 'hospitalizations:state_data:delta_orchard_hospital'},
                {'name': 'regions:chico:cases'},
                {'name': 'regions:chico:delta_cases'},
                {'name': 'regions:oroville:cases'},
                {'name': 'regions:oroville:delta_cases'},
                {'name': 'regions:gridley:cases'},
                {'name': 'regions:gridley:delta_cases'},
                {'name': 'regions:other:cases'},
                {'name': 'regions:other:delta_cases'},
                {'name': 'age_ranges_in_years:0-17'},
                {'name': 'age_ranges_in_years:delta_0-17'},
                {'name': 'age_ranges_in_years:18-49'},
                {'name': 'age_ranges_in_years:delta_18-49'},
                {'name': 'age_ranges_in_years:50-64'},
                {'name': 'age_ranges_in_years:delta_50_64'},
                {'name': 'age_ranges_in_years:65_plus'},
                {'name': 'age_ranges_in_years:delta_65_plus'},
                {'name': 'resources:state_data:icu_beds_pct'},
                {'name': 'resources:state_data:ventilators_pct'},
                {'name': 'resources:state_data:n95_respirators'},
                {'name': 'resources:state_data:procedure_masks'},
                {'name': 'resources:state_data:gowns'},
                {'name': 'resources:state_data:face_shields'},
                {'name': 'resources:state_data:gloves'},
                {'name': 'note'},
                {'name': 'skilled_nursing_facilities:current_patient_cases'},
                {'name': 'skilled_nursing_facilities:current_staff_cases'},
                {'name': 'skilled_nursing_facilities:total_patient_deaths'},
                {'name': 'skilled_nursing_facilities:total_staff_deaths'},
            ],
        },
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
    if len(sys.argv) > 1:
        feeds_to_build = set(sys.argv[1:])
    else:
        feeds_to_build = set(
            feed['filename']
            for feed in FEEDS
        )

    try:
        with open(CACHE_FILE, 'r') as fp:
            cache = json.load(fp)
    except Exception:
        cache = {}

    for info in FEEDS:
        filename = info['filename']

        if filename not in feeds_to_build:
            continue

        out_dir = os.path.join(DATA_DIR, info['format'])

        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        out_filename = os.path.join(out_dir, filename)
        parser = info.get('parser')
        result = None
        up_to_date = False
        skipped = False

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

        skipped = (result is False)

        if up_to_date:
            print('Up-to-date: %s' % out_filename)
        elif skipped:
            print('Skipped %s' % out_filename)
        else:
            print('Wrote %s' % out_filename)


    with open(CACHE_FILE, 'w') as fp:
        json.dump(cache, fp)


if __name__ == '__main__':
    main()
