#!/usr/bin/env python3

import codecs
import csv
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
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


class TableauPresModel(object):
    def __init__(self, loader, payload):
        self.loader = loader
        self.payload = payload

    @property
    def all_data_columns(self):
        return (
            self.payload
            ['presModelHolder']
            ['genVizDataPresModel']
            ['paneColumnsData']
            ['vizDataColumns']
        )

    @property
    def all_pane_columns(self):
        return (
            self.payload
            ['presModelHolder']
            ['genVizDataPresModel']
            ['paneColumnsData']
            ['paneColumnsList']
        )

    def get_pane_columns(self, pane_index):
        return self.all_pane_columns[pane_index]['vizPaneColumns']

    def get_mapped_col_data(self, cols):
        data_dicts = self.loader.get_bootstrap_data_dicts()
        result = {}

        for col_data in self.all_data_columns:
            caption = col_data.get('fieldCaption')

            if caption and caption in cols:
                col_info = cols[caption]
                data_type = col_data.get('dataType')

                if data_type != col_info['data_type']:
                    raise ParseError(
                        'Expected data type "%s" for column "%s", but got '
                        '"%s" instead.'
                        % (col_info['data_type'], caption, data_type))

                data_type_dict = data_dicts[data_type]
                cstring_dict = data_dicts['cstring']
                col_index = col_data['columnIndices'][0]
                pane_index = col_data['paneIndices'][0]

                result_key = col_info.get('result_key', caption)
                pane_columns = self.get_pane_columns(pane_index)
                value_index = col_info.get('value_index')
                normalize = col_info.get('normalize', lambda value: value)

                alias_indices = pane_columns[col_index]['aliasIndices']

                def _get_value(alias_index):
                    # I may be wrong, but I believe if an alias index is < 0,
                    # then it's a reference to a display for a value in the
                    # cstring data dict instead. It has to be converted to a
                    # positive value and then converted from a 1-based index
                    # to a 0-based index.
                    if alias_index < 0:
                        return data_dicts['cstring'][-alias_index - 1]
                    else:
                        return data_type_dict[alias_index]

                if value_index is None:
                    result[result_key] = [
                        normalize(_get_value(i))
                        for i in alias_indices
                    ]
                else:
                    result[result_key] = normalize(
                        _get_value(alias_indices[value_index]))

        expected_keys = set(
            col_info.get('result_key', col_key)
            for col_key, col_info in cols.items()
        )

        missing_keys = expected_keys - set(result.keys())

        if missing_keys:
            raise ParseError('The following keys could not be found: %s'
                             % ', '.join(sorted(missing_keys)))

        return result


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

    def get_workbook_metadata(self):
        if not hasattr(self, '_workbook_metadata'):
            response = self.session.get(
                'https://public.tableau.com/profile/api/workbook/%s'
                % self.owner)

            self._workbook_metadata = response.json()

        return self._workbook_metadata

    def get_last_update_date(self):
        metadata = self.get_workbook_metadata()
        return datetime.fromtimestamp(metadata['lastUpdateDate'] / 1000)

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

    @property
    def bootstrap_payload2(self):
        if not hasattr(self, '_bootstrap_payload2'):
            self._bootstrap_payload2 = json.loads(self.raw_bootstrap_payload2)

        return self._bootstrap_payload2

    def get_bootstrap_data_dicts(self, expected_counts={}):
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

    def get_pres_model(self, model_key):
        return TableauPresModel(
            loader=self,
            payload=(
                self.bootstrap_payload2
                ['secondaryInfo']
                ['presModelMap']
                ['vizData']
                ['presModelHolder']
                ['genPresModelMapPresModel']
                ['presModelMap']
                [model_key]
            ))

    def get_mapped_col_data(self, models_to_cols):
        result = {}

        for model_key, cols in models_to_cols.items():
            pres_model = self.get_pres_model(model_key)
            result.update(pres_model.get_mapped_col_data(cols))

        return result


class ParseError(Exception):
    pass


@contextmanager
def safe_open_for_write(filename):
    temp_filename = '%s.tmp' % filename

    with open(temp_filename, 'w') as fp:
        yield fp

    os.rename(temp_filename, filename)


def add_nested_key(d, full_key, value):
    keys = full_key.split(':')

    for key in keys[:-1]:
        d = d.setdefault(key, {})

    d[keys[-1]] = value


def parse_int(value, allow_blank=False):
    if allow_blank and value == '':
        return value

    if isinstance(value, int):
        return value

    value = value.replace(',', '')

    return int(value or 0)


def parse_real(value, allow_blank=False):
    if allow_blank and value == '':
        return value

    if isinstance(value, float):
        return value

    value = value.replace(',', '')

    return float(value or 0)


def parse_pct(value):
    if value == '':
        return value

    return float(value.replace('%', ''))


def parse_csv_value(value, data_type, col_info):
    if data_type == 'date':
        try:
            value = (
                datetime.strptime(value, col_info['format'])
                .strftime('%Y-%m-%d')
            )
        except Exception:
            raise ParseError('Unable to parse date "%s" using format '
                             '"%s"'
                             % (value, col_info['format']))
    elif data_type == 'int_or_blank':
        try:
            value = parse_int(value, allow_blank=True)
        except ValueError:
            raise ParseError(
                'Expected %r to be an integer or empty string.'
                % value)
    elif data_type == 'int':
        try:
            value = parse_int(value)
        except ValueError:
            raise ParseError('Expected %r to be an integer.'
                             % value)
    elif data_type == 'real':
        try:
            value = parse_real(value)
        except ValueError:
            raise ParseError('Expected %r to be an integer.'
                             % value)
    elif data_type == 'pct':
        try:
            value = parse_pct(value)
        except ValueError:
            raise ParseError('Expected %r to be a percentage.'
                             % value)
    elif data_type == 'string' or data_type is None:
        pass
    else:
        raise ParseError('Unexpected data type %s' % data_type)

    return value


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

    with safe_open_for_write(filename) as fp:
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

        value = None

        if blocks[0]['text'].lower() in expected_labels:
            value = blocks[1]['text']
        elif len(blocks) > 1 and blocks[1]['text'].lower() in expected_labels:
            value = blocks[0]['text']
        else:
            # They probably broke the labels/values again. Let's try to
            # find the label *in* the value.
            for label in expected_labels:
                for i in (0, 1):
                    if len(blocks) >= i and label in blocks[0]['text'].lower():
                        value = \
                            blocks[0]['text'].lower().split(label)[0].strip()

            if value is None:
                found_labels = [
                    block['text'].lower()
                    for block in blocks
                ]

                raise ParseError(
                    'Expected one of label %r to be one of %r for '
                    'entity %s'
                    % (found_labels, expected_labels, entity_id))

        # This won't always be "pending", but the idea is that we're trying
        # to gracefully handle when there's an issue with some value coming
        # from the county or state.
        if 'pending' in value.lower():
            return None

        try:
            return int(value)
        except Exception:
            raise ParseError('Expected value %r for entity %s to be int, '
                             'got %s'
                             % (value, entity_id, type(value)))

    def get_chart_info(entity_id, label_col=0, value_col=1):
        entity = get_entity(entity_id)
        data = entity['props']['chartData']['data'][0]

        return {
            row[label_col]: int(row[value_col])
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
            'labels': ['daily viral test results', 'daily viral tests'],
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
        'by_age': ('9ba3a895-019a-4e68-99ec-0eb7b5bd026c', 1),
        'deaths_by_age': ('9ba3a895-019a-4e68-99ec-0eb7b5bd026c', 2),
        'by_region': ('b26b9acd-b036-40bc-bbbe-68667dd338e4', 1),
    }

    scraped_data = {
        key: get_counter_value(info['entity_id'],
                               expected_labels=info['labels'])
        for key, info in COUNTER_KEYS_TO_ENTITIES.items()
    }
    scraped_data.update({
        key: get_chart_info(entity_id, value_col=value_col)
        for key, (entity_id, value_col) in CHART_KEYS_TO_ENTITIES.items()
    })

    try:
        by_age = scraped_data['by_age']
        by_region = scraped_data['by_region']
        deaths_by_age = scraped_data['deaths_by_age']

        row_result = {
            'date': datestamp.strftime('%Y-%m-%d'),
            'confirmed_cases': scraped_data['confirmed_cases'],
            'deaths': scraped_data['deaths'],
            'deaths_by': {
                'age_ranges_in_years': {
                    '0-17': deaths_by_age['0-17 Years'],
                    '18-24': deaths_by_age['18-24 Years'],
                    '25-34': deaths_by_age['25-34 Years'],
                    '35-44': deaths_by_age['35-44 Years'],
                    '45-54': deaths_by_age['45-54 Years'],
                    '55-64': deaths_by_age['55-64 Years'],
                    '65-74': deaths_by_age['65-74 Years'],
                    '75_plus': deaths_by_age['75+ Years'],
                },
            },
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
                '0-17': by_age['0-17 Years'],
                '18-24': by_age['18-24 Years'],
                '25-34': by_age['25-34 Years'],
                '35-44': by_age['35-44 Years'],
                '45-54': by_age['45-54 Years'],
                '55-64': by_age['55-64 Years'],
                '65-74': by_age['65-74 Years'],
                '75_plus': by_age['75+ Years'],

                # Legacy
                '18-49': None,
                '50-64': None,
                '65_plus': by_age['65-74 Years'] + by_age['75+ Years'],
            },
            'regions': {
                'biggs_gridley': by_region['Biggs/Gridley'],
                'chico': by_region['Chico'],
                'durham': by_region['Durham'],
                'oroville': by_region['Oroville'],
                'other': by_region['Other'],
                'ridge': by_region['Ridge Communities'],

                # Legacy
                'gridley': None,
            },
        }
    except Exception as e:
        raise ParseError('Unable to build row data: %s' % e)

    add_or_update_json_date_row(out_filename, row_result)


def parse_butte_county_jail(response, out_filename, **kwargs):
    # Try to find the rough section of content we want to search within.
    m = re.search(r'(DAILY COVID-19.*)ENHANCED CLEANING',
                  response.text,
                  re.S)

    if not m:
        raise ParseError(
            'Could not find COVID-19 section for Butte County Jail.')

    content = m.group(1)

    m = re.search(r'DAILY COVID-19 UPDATE FOR ([A-Za-z]+) (\d+), (20\d{2}) '
                  r'\(Updated',
                  content)

    if not m:
        raise ParseError(
            'Unable to find update datestamp for Butte County Jail')

    months = {
        'january': 1,
        'february': 2,
        'march': 3,
        'april': 4,
        'may': 5,
        'june': 6,
        'july': 7,
        'august': 8,
        'september': 9,
        'october': 10,
        'november': 11,
        'december': 12,
    }

    datestamp_str = '%s %s, %s' % (m.group(1), m.group(2), m.group(3))
    datestamp = datetime(month=months[m.group(1).lower()],
                         day=int(m.group(2)),
                         year=int(m.group(3)))

    if datestamp.date() != datetime.now().date():
        # This is stale data not from today. OR it might be new data but
        # the county forgot to update the datestamp. So don't risk
        # overwriting historical data, and instead bail.
        return

    def get_int(pattern):
        m = re.search(pattern, content)

        if not m:
            raise ParseError('Unable to find "%s" in Butte County Jail')

        try:
            return int(m.group(1))
        except ValueError:
            raise ParseError('Value for "%s" in Butte County Jail was not an '
                             'int!')

    inmates_data = {
        'current_population': get_int(r'inmate population as of '
                                      r'[A-Za-z]+ \d+, 20\d{2}: (\d+)'),
        'current_cases': get_int(r'currently has (\d+) positive '
                                 r'in-custody inmate'),
        'pending_tests': get_int(r'has (\d+) inmate COVID-19 tests pending'),
        'total_negative': get_int(r'(\d+) negative'),
        'total_recovered': get_int(r'(\d+) recovered'),
        'total_tests': get_int(r'Estimate of (\d+) total inmate tests'),
    }

    staff_data = {
        'total_tests': get_int(r'conducted (\d+) tests on staff'),
        'total_cases': get_int('total of (\d+) staff cases'),
        'total_recovered': get_int('(\d+) of those have recovered and '
                                   'returned to work'),
    }

    inmates_data['total_positive'] = \
        inmates_data['total_tests'] - inmates_data['total_negative']

    add_or_update_json_date_row(out_filename, {
        'date': datestamp.strftime('%Y-%m-%d'),
        'inmates': inmates_data,
        'staff': staff_data,
    })


def convert_json_to_csv(info, in_fp, out_filename, **kwargs):
    def _get_key_value(d, paths):
        for path in paths:
            d = d.get(path)

            if d is None:
                break

        return d

    key_map = info['key_map']
    dataset = json.load(in_fp) or {}

    with safe_open_for_write(out_filename) as fp:
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


def build_timeline_json(info, in_fp, out_filename, **kwargs):
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
                        try:
                            col_data = float(col_data)
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

    payload = {
        'dates': timeline,
    }

    with safe_open_for_write(out_filename) as fp:
        json.dump(payload,
                  fp,
                  sort_keys=True,
                  indent=2)

    min_filename = os.path.join(os.path.dirname(out_filename),
                                info['min_filename'])

    with safe_open_for_write(min_filename) as fp:
        json.dump(payload,
                  fp,
                  sort_keys=True,
                  separators=(',', ':'))


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

    # NOTE: Ideally we'd look this up from "Last Updated Date", but I'm still
    #       unsure how these map into a dataValues with a negative
    #       aliasIndices. So while this isn't correct, it's sort of what
    #       we've got right now.
    data_dicts = tableau_loader.get_bootstrap_data_dicts()
    last_updated = datetime.strptime(
        sorted(data_dicts['datetime'])[-1],
        '%Y-%m-%d %H:%M:%S')

    if last_updated > datetime.now():
        # This isn't today's date. Skip it.
        return False

    data = tableau_loader.get_mapped_col_data({
        'Face Shields Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'face_shields',
                'value_index': 0,
            },
        },
        'Gloves Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'gloves',
                'value_index': 0,
            },
        },
        'Gowns Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'gowns',
                'value_index': 0,
            },
        },
        'ICU Beds Available BAN': {
            'AGG(ICU Availability)': {
                'data_type': 'real',
                'normalize': lambda value: int(round(value, 2) * 100),
                'result_key': 'icu_beds_pct',
                'value_index': 0,
            },
        },
        'N95 Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'n95_respirators',
                'value_index': 0,
            },
        },
        'Proc Masks Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'procedure_masks',
                'value_index': 0,
            },
        },
        'Sheet 42': {
            'SUM(Bed Reporting (Fixed))': {
                'data_type': 'integer',
                'result_key': 'beds',
                'value_index': 0,
            },
        },
        'Ventilators Available %': {
            'AGG(Ventilators Available %)': {
                'data_type': 'real',
                'normalize': lambda value: int(round(value, 2) * 100),
                'result_key': 'ventilators_pct',
                'value_index': 0,
            },
        },
    })
    data['date'] = last_updated.strftime('%Y-%m-%d')

    add_or_update_json_date_row(out_filename, data)


def build_state_tiers_json(session, response, out_filename, **kwargs):
    tableau_loader = TableauLoader(session=session,
                                   owner='Planforreducingcovid-19',
                                   sheet='Plan for reducing covid-19',
                                   orig_response=response)
    tableau_loader.bootstrap({
        'showParams': json.dumps({
            'unknownParams': 'County=Butte',
        }),
        'stickySessionKey': json.dumps({
            'workbookId': 6582582,
        }),
    })

    data = tableau_loader.get_mapped_col_data({
        'Counties by Phase': {
            'AGG(zn([Case Metrics by Episode Date w/ Pop].[Weekly Avg Per 100K]))': {
                'data_type': 'real',
                'result_key': 'cases_per_100k',
                'value_index': 0,
                'normalize': lambda value: round(value, 2),
            },
            'AGG(Positivity Rate)': {
                'data_type': 'real',
                'result_key': 'pos_rate',
                'value_index': 0,
                'normalize': lambda value: round(value, 5),
            },
            'Overall Status': {
                'data_type': 'integer',
                'result_key': 'status',
                'value_index': 0,
            },
        },
    })
    data['date'] = tableau_loader.get_last_update_date().strftime('%Y-%m-%d')

    add_or_update_json_date_row(out_filename, data)


def build_hospital_cases_json(session, response, out_filename, **kwargs):
    hospital_keys = {
        'Enloe Medical Center - Esplanade': 'enloe_hospital',
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

    if date > datetime.now():
        # This isn't today's date. Skip it.
        return False

    # Find the columns we care about.
    data = tableau_loader.get_mapped_col_data({
        'Map Patients': {
            'Hospital Name': {
                'data_type': 'cstring',
                'result_key': 'hospital_names',
                'normalize': lambda name: hospital_keys.get(name, name),
            },
            'AGG(Selector KPI)': {
                'data_type': 'real',
                'result_key': 'counts',
            },
        },
    })

    hospital_names = data['hospital_names']
    counts = data['counts']

    if len(hospital_names) != len(counts):
        raise ParseError('Number of hospital names (%s) does not match '
                         'number of case counts (%s).'
                         % (len(hospital_names), len(counts)))

    hospital_cases = {
        hospital_name: count
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
    skip_rows = csv_info.get('skip_rows', 0)
    default_type = csv_info.get('default_type')
    end_if = csv_info.get('end_if')

    unique_found = set()
    results = []

    lines = response.iter_lines()

    for i in range(skip_rows):
        next(lines)

    reader = csv.DictReader(codecs.iterdecode(lines, 'utf-8'),
                            delimiter=',')
    prev_row = None

    for row in reader:
        if match is not None and not match(row):
            continue

        if end_if is not None and end_if(row):
            break

        row_result = {}

        for col_info in columns:
            dest_name = col_info['name']
            src_name = col_info.get('source_column', dest_name)
            data_type = col_info.get('type', default_type)

            try:
                value = row[src_name]
            except KeyError:
                raise ParseError('Missing column in CSV file: %s' % src_name)

            if data_type == 'delta':
                delta_from = col_info['delta_from']

                if (row[delta_from] == '' or
                    prev_row is None or
                    prev_row[delta_from] == ''):
                    value = ''
                else:
                    value = parse_csv_value(
                        value=value,
                        data_type=col_info.get('delta_type', default_type),
                        col_info=col_info)
            else:
                value = parse_csv_value(value=value,
                                        data_type=data_type,
                                        col_info=col_info)

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

        prev_row = row

    # Some datasets are unordered or not in an expected order. If needed, sort.
    if sort_by is not None:
        results = sorted(results, key=lambda row: row[sort_by])

    # Validate that we have the data we expect. We don't want to be offset by
    # a row or have garbage or something.
    if validator is not None and not validator(results):
        raise ParseError('Resulting CSV file did not pass validation!')

    with safe_open_for_write(out_filename) as out_fp:
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
        'url': 'https://raw.githubusercontent.com/shaman-lab/COVID-19Projection/master/LatestProjections/Projection_nochange.csv',
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
        'filename': 'butte-dashboard-v3.csv',
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
            ('Age 18-24 Years', ('age_ranges_in_years', '18-24')),
            ('Age 25-34 Years', ('age_ranges_in_years', '25-34')),
            ('Age 35-44 Years', ('age_ranges_in_years', '35-44')),
            ('Age 45-54 Years', ('age_ranges_in_years', '45-54')),
            ('Age 55-64 Years', ('age_ranges_in_years', '55-64')),
            ('Age 65-74 Years', ('age_ranges_in_years', '65-74')),
            ('Age 75+ Years', ('age_ranges_in_years', '75_plus')),
            ('Age 18-49 Years', ('age_ranges_in_years', '18-49')),
            ('Age 50-64 Years', ('age_ranges_in_years', '50-64')),
            ('Age 65+ Years', ('age_ranges_in_years', '65_plus')),
            ('Biggs/Gridley Cases', ('regions', 'biggs_gridley')),
            ('Chico Cases', ('regions', 'chico')),
            ('Durham Cases', ('regions', 'durham')),
            ('Oroville Cases', ('regions', 'oroville')),
            ('Ridge Community Cases', ('regions', 'ridge')),
            ('Other Region Cases', ('regions', 'other')),
            ('Gridley Cases (Historical)', ('regions', 'gridley')),
            ('Deaths - Age 0-17 Years',
             ('deaths_by', 'age_ranges_in_years', '0-17')),
            ('Deaths - Age 18-24 Years',
             ('deaths_by', 'age_ranges_in_years', '18-24')),
            ('Deaths - Age 25-34 Years',
             ('deaths_by', 'age_ranges_in_years', '25-34')),
            ('Deaths - Age 35-44 Years',
             ('deaths_by', 'age_ranges_in_years', '35-44')),
            ('Deaths - Age 45-54 Years',
             ('deaths_by', 'age_ranges_in_years', '45-54')),
            ('Deaths - Age 55-64 Years',
             ('deaths_by', 'age_ranges_in_years', '55-64')),
            ('Deaths - Age 65-74 Years',
             ('deaths_by', 'age_ranges_in_years', '65-74')),
            ('Deaths - Age 75+ Years',
             ('deaths_by', 'age_ranges_in_years', '75_plus')),
        ],
    },
    {
        'filename': 'butte-county-jail.json',
        'format': 'json',
        'url': 'https://www.buttecounty.net/sheriffcoroner/Covid-19',
        'parser': parse_butte_county_jail,
    },
    {
        'filename': 'butte-county-jail.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'butte-county-jail.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Inmate Population', ('inmates', 'current_population')),
            ('Current Inmate Cases', ('inmates', 'current_cases')),
            ('Total Recovered Inmates', ('inmates', 'total_recovered')),
            ('Total Inmate Tests', ('inmates', 'total_tests')),
            ('Total Negative Inmate Tests', ('inmates', 'total_negative')),
            ('Total Positive Inmate Tests', ('inmates', 'total_positive')),
            ('Pending Inmate Tests', ('inmates', 'pending_tests')),
            ('Total Staff Tests', ('staff', 'total_tests')),
            ('Total Staff Cases', ('staff', 'total_cases')),
            ('Total Recovered Staff', ('staff', 'total_recovered')),
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
        'filename': 'state-tiers.json',
        'format': 'json',
        'url': (
            'https://public.tableau.com/views/Planforreducingcovid-19/'
            'planforreducingcovid-19/?%3AshowVizHome=no&County=Butte'
        ),
        'parser': build_state_tiers_json,
    },
    {
        'filename': 'state-tiers.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'state-tiers.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Status', ('status',)),
            ('New Case Rate', ('cases_per_100k',)),
            ('Positivity Rate', ('pos_rate',)),
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
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRwJpCeZj4tsxMXqrHFDjIis5Znv-nI0kQk9enEAJAbYzZUBHm7TELQe0wl2huOYEkdaWLyR8N9k_uq/pub?gid=169564738&single=true&output=csv',
        'csv': {
            'end_if': lambda row: (row['confirmed_cases:total'] == ''),
            'validator': lambda results: (
                len(results) > 0 and
                results[0]['date'] == '2020-03-20' and
                (results[-1]['confirmed_cases:total'] != '' or
                 results[-2]['confirmed_cases:total'] != '' or
                 results[-3]['confirmed_cases:total'] != '')
            ),
            'skip_rows': 4,
            'default_type': 'int_or_blank',
            'columns': [
                {
                    'name': 'date',
                    'type': 'date',
                    'format': '%a, %b %d, %Y',
                },
                {'name': 'confirmed_cases:total'},
                {
                    'name': 'confirmed_cases:delta_total',
                    'type': 'delta',
                    'delta_from': 'confirmed_cases:total',
                },
                {'name': 'in_isolation:current'},
                {
                    'name': 'in_isolation:delta_current',
                    'type': 'delta',
                    'delta_from': 'in_isolation:current',
                },
                {'name': 'in_isolation:total_released'},
                {
                    'name': 'in_isolation:delta_total_released',
                    'type': 'delta',
                    'delta_from': 'in_isolation:total_released',
                },
                {'name': 'deaths:total'},
                {
                    'name': 'deaths:delta_total',
                    'type': 'delta',
                    'delta_from': 'deaths:total',
                },
                {'name': 'deaths:age_ranges_in_years:0-17'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_0-17',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:0-17',
                },
                {'name': 'deaths:age_ranges_in_years:18-24'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_18-24',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:18-24',
                },
                {'name': 'deaths:age_ranges_in_years:25-34'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_25-34',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:25-34',
                },
                {'name': 'deaths:age_ranges_in_years:35-44'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_35-44',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:35-44',
                },
                {'name': 'deaths:age_ranges_in_years:45-54'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_45-54',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:45-54',
                },
                {'name': 'deaths:age_ranges_in_years:55-64'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_55-64',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:55-64',
                },
                {'name': 'deaths:age_ranges_in_years:65-74'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_65-74',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:65-74',
                },
                {'name': 'deaths:age_ranges_in_years:75_plus'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_75_plus',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:75_plus',
                },
                {'name': 'viral_tests:total'},
                {
                    'name': 'viral_tests:delta_total',
                    'type': 'delta',
                    'delta_from': 'viral_tests:total',
                },
                {'name': 'viral_tests:results'},
                {
                    'name': 'viral_tests:delta_results',
                    'type': 'delta',
                    'delta_from': 'viral_tests:results',
                },
                {'name': 'viral_tests:pending'},
                {
                    'name': 'viral_tests:delta_pending',
                    'type': 'delta',
                    'delta_from': 'viral_tests:pending',
                },
                {'name': 'hospitalizations:county_data:hospitalized'},
                {'name': 'hospitalizations:state_data:positive'},
                {
                    'name': 'hospitalizations:state_data:delta_positive',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:positive',
                },
                {'name': 'hospitalizations:state_data:suspected_positive'},
                {
                    'name': 'hospitalizations:state_data:delta_suspected_positive',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:suspected_positive',
                },
                {'name': 'hospitalizations:state_data:icu_positive'},
                {
                    'name': 'hospitalizations:state_data:delta_icu_positive',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:icu_positive',
                },
                {'name': 'hospitalizations:state_data:icu_suspected'},
                {
                    'name': 'hospitalizations:state_data:delta_icu_suspected',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:icu_suspected',
                },
                {'name': 'hospitalizations:state_data:enloe_hospital'},
                {
                    'name': 'hospitalizations:state_data:delta_enloe_hospital',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:enloe_hospital',
                },
                {'name': 'hospitalizations:state_data:oroville_hospital'},
                {
                    'name': 'hospitalizations:state_data:delta_oroville_hospital',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:oroville_hospital',
                },
                {'name': 'hospitalizations:state_data:orchard_hospital'},
                {
                    'name': 'hospitalizations:state_data:delta_orchard_hospital',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:orchard_hospital',
                },
                {'name': 'regions:biggs_gridley:cases'},
                {
                    'name': 'regions:biggs_gridley:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:biggs_gridley:cases',
                },
                {'name': 'regions:chico:cases'},
                {
                    'name': 'regions:chico:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:chico:cases',
                },
                {'name': 'regions:durham:cases'},
                {
                    'name': 'regions:durham:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:durham:cases',
                },
                {'name': 'regions:gridley:cases'},
                {
                    'name': 'regions:gridley:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:gridley:cases',
                },
                {'name': 'regions:oroville:cases'},
                {
                    'name': 'regions:oroville:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:oroville:cases',
                },
                {'name': 'regions:ridge:cases'},
                {
                    'name': 'regions:ridge:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:ridge:cases',
                },
                {'name': 'regions:other:cases'},
                {
                    'name': 'regions:other:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:other:cases',
                },
                {'name': 'age_ranges_in_years:0-17'},
                {
                    'name': 'age_ranges_in_years:delta_0-17',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:0-17',
                },
                {'name': 'age_ranges_in_years:18-24'},
                {
                    'name': 'age_ranges_in_years:delta_18-24',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:18-24',
                },
                {'name': 'age_ranges_in_years:25-34'},
                {
                    'name': 'age_ranges_in_years:delta_25-34',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:25-34',
                },
                {'name': 'age_ranges_in_years:35-44'},
                {
                    'name': 'age_ranges_in_years:delta_35-44',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:35-44',
                },
                {'name': 'age_ranges_in_years:45-54'},
                {
                    'name': 'age_ranges_in_years:delta_45-54',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:45-54',
                },
                {'name': 'age_ranges_in_years:55-64'},
                {
                    'name': 'age_ranges_in_years:delta_55-64',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:55-64',
                },
                {'name': 'age_ranges_in_years:65-74'},
                {
                    'name': 'age_ranges_in_years:delta_65-74',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:65-74',
                },
                {'name': 'age_ranges_in_years:75_plus'},
                {
                    'name': 'age_ranges_in_years:delta_75_plus',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:75_plus',
                },
                {'name': 'age_ranges_in_years:18-49'},
                {
                    'name': 'age_ranges_in_years:delta_18-49',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:18-49',
                },
                {'name': 'age_ranges_in_years:50-64'},
                {
                    'name': 'age_ranges_in_years:delta_50_64',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:50-64',
                },
                {'name': 'age_ranges_in_years:65_plus'},
                {
                    'name': 'age_ranges_in_years:delta_65_plus',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:65_plus',
                },
                {
                    'name': 'resources:state_data:icu_beds_pct',
                    'type': 'pct',
                },
                {
                    'name': 'resources:state_data:ventilators_pct',
                    'type': 'pct',
                },
                {'name': 'resources:state_data:n95_respirators'},
                {'name': 'resources:state_data:procedure_masks'},
                {'name': 'resources:state_data:gowns'},
                {'name': 'resources:state_data:face_shields'},
                {'name': 'resources:state_data:gloves'},
                {
                    'name': 'note',
                    'type': 'string',
                },
                {'name': 'skilled_nursing_facilities:current_patient_cases'},
                {'name': 'skilled_nursing_facilities:current_staff_cases'},
                {'name': 'skilled_nursing_facilities:total_patient_deaths'},
                {'name': 'skilled_nursing_facilities:total_staff_deaths'},
                {'name': 'county_jail:inmates:population'},
                {
                    'name': 'county_jail:inmates:delta_population',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:population',
                },
                {'name': 'county_jail:inmates:total_tests'},
                {
                    'name': 'county_jail:inmates:delta_total_tests',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:total_tests',
                },
                {'name': 'county_jail:inmates:total_positive'},
                {
                    'name': 'county_jail:inmates:delta_total_positive',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:total_positive',
                },
                {'name': 'county_jail:inmates:tests_pending'},
                {
                    'name': 'county_jail:inmates:delta_tests_pending',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:tests_pending',
                },
                {'name': 'county_jail:inmates:current_cases'},
                {
                    'name': 'county_jail:inmates:delta_current_cases',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:current_cases',
                },
                {'name': 'county_jail:inmates:total_recovered'},
                {
                    'name': 'county_jail:inmates:delta_total_recovered',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:total_recovered',
                },
                {'name': 'county_jail:staff:total_tests'},
                {
                    'name': 'county_jail:staff:delta_total_tests',
                    'type': 'delta',
                    'delta_from': 'county_jail:staff:total_tests',
                },
                {'name': 'county_jail:staff:total_positive'},
                {
                    'name': 'county_jail:staff:delta_total_positive',
                    'type': 'delta',
                    'delta_from': 'county_jail:staff:total_positive',
                },
                {
                    'name': 'monitoring:tier',
                    'type': 'string',
                },
                {
                    'name': 'monitoring:new_case_rate',
                    'type': 'real',
                },
                {
                    'name': 'monitoring:delta_new_case_rate',
                    'type': 'delta',
                    'delta_from': 'monitoring:new_case_rate',
                    'delta_type': 'real',
                },
                {
                    'name': 'monitoring:test_pos_rate',
                    'type': 'pct',
                },
                {
                    'name': 'monitoring:delta_test_pos_rate',
                    'type': 'delta',
                    'delta_from': 'monitoring:test_pos_rate',
                    'delta_type': 'pct',
                }
            ],
        },
    },
    {
        'filename': 'timeline.json',
        'min_filename': 'timeline.min.json',
        'format': 'json',
        'local_source': {
            'filename': 'timeline.csv',
            'format': 'csv',
        },
        'parser': build_timeline_json,
    },
]


def main():
    if '--not-timeline' in sys.argv:
        feeds_to_build = {
            feed['filename']
            for feed in FEEDS
        } - {'timeline.csv', 'timeline.json'}
    elif len(sys.argv) > 1:
        feeds_to_build = set(sys.argv[1:])
    else:
        feeds_to_build = {
            feed['filename']
            for feed in FEEDS
        }

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

            if not os.path.exists(source_filename):
                with open(source_filename, 'w') as out_fp:
                    out_fp.write('[]')

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
