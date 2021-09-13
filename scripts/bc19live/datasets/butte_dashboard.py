import csv
import json
import os
import re
from collections import OrderedDict
from datetime import datetime, timedelta

from bc19live.errors import ParseError
from bc19live.utils import (add_or_update_json_date_row,
                            convert_json_to_csv,
                            safe_open_for_write)


def build_dataset(response, out_filename, **kwargs):
    """Parse the Butte County dashboard.

    This extracts case, fatalities, hospitalization, demographics, and testing
    information from the Butte County COVID-19 dashboard, hosted on Infogram.
    It's built to work around quirks that may show up from time to time, and
    to cancel out if any data appears to be missing.

    Infogram pages contain a JSON payload of data used to generate the
    dashboard. These consist of entities, which contain information for some
    part of the dashboard. An entity may be broken into blocks that each
    contain a label and a value, or may contain chart data.

    If the current timestamp on the dashboard doesn't match today's date, the
    dashboard state will not be loaded.

    Args:
        response (requests.Response):
            The HTTP response containing the page.

        out_filename (str):
            The name of the outputted JSON file.

        **kwargs (dict, unused):
            Unused keyword arguments passed to this parser.

    Returns:
        bool:
        ``True`` if the file was written, or ``False`` if skipped.

    Raises:
        ParseError:
            Expected data was missing or was in an unexpected format. Detailed
            information will be in the error message.
    """
    def get_entity(entity_id):
        """Return an entity from the page's dashboard data.

        Args:
            entity_id (str):
                The unique ID of the entity.

        Returns:
            dict:
            The entity's payload data.

        Raises:
            KeyError:
                The entity ID was not found.
        """
        return (
            dashboard_data['elements']['content']['content']
            ['entities'][entity_id]
        )

    def get_counter_value(entity_id, expected_labels, label_first=False):
        """Return a value from a counter entity.

        This is used for entities like "Confirmed Cases". It will look for a
        label matching one of the possible expected labels and try to return
        the associated number.

        Args:
            entity_id (str):
                The unique ID of the counter entity.

            expected_labels (list of str):
                The list of labels that can match the entity.

            label_first (bool, optional):
                Whether the label is listed before the value.

        Returns:
            int:
            The counter value.

        Raises:
            ParseError:
                The entity could not be found.
        """
        entity = get_entity(entity_id)
        blocks = entity['props']['content']['blocks']

        value = None

        if blocks[0]['text'].strip().lower() in expected_labels:
            value = blocks[1]['text']
        elif (len(blocks) > 1 and
              blocks[1]['text'].strip().lower() in expected_labels):
            value = blocks[0]['text']
        else:
            # They probably broke the labels/values again. Let's try to
            # find the label *in* the value.
            for label in expected_labels:
                for i in (0, 1):
                    if (len(blocks) >= i and
                        label in blocks[0]['text'].strip().lower()):
                        value = (
                            blocks[0]['text']
                            .lower()
                            .split(label)[0]
                            .strip()
                        )

            if value is None:
                found_labels = [
                    block['text'].strip().lower()
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
            return int(re.sub(r'[, ]+', '', value))
        except Exception:
            raise ParseError('Expected value %r for entity %s (%s) to be int, '
                             'got %s'
                             % (value, entity_id, ', '.join(expected_labels),
                                type(value)))

    def get_chart_info(entity_id, label_col=0, value_col=1):
        """Return information from a chart.

        This will extract a chart's data, returning a mapping of chart axis
        labels to values.

        Args:
            entity_id (str):
                The unique ID of the counter entity.

            label_col (int, optional):
                The column index containing the label. This defaults to the
                first column.

            value_col (int, optional):
                The column index containing the value. This defaults to the
                second column.

        Returns:
            dict:
            A dictionary mapping chart labels to values.
        """
        entity = get_entity(entity_id)
        data = entity['props']['chartData']['data'][0]

        result = OrderedDict()

        whitespace_re = re.compile('\s+')

        for row in data[1:]:
            try:
                label = row[label_col]
                value = row[value_col]
            except IndexError:
                label = None
                value = ''

            if label is None:
                continue

            if value == '':
                value = 0
            else:
                try:
                    value = int(value)
                except IndexError:
                    # This column may not exist in this field, due to no value
                    # provided yet in the graph data.
                    value = 0

            key = whitespace_re.sub(' ', label)
            result[key] = value

        return result

    def get_chart_history(entity_id):
        """Return history/timeline information from a chart.

        This will extract the history data and perform date normalization,
        handling the cases where the dashboard lacks year information.

        Args:
            entity_id (str):
                The unique ID of the graph entity.

        Returns:
            dict:
            A dictionary mapping chart labels to values.
        """
        entity = get_entity(entity_id)
        history = []
        year = 2020

        for item in entity['props']['chartData']['data'][0][1:]:
            if item[0] is None:
                continue

            parts = [
                int(_i)
                for _i in item[0].split('/')
            ]

            if parts[0] == 1 and parts[1] == 1:
                year += 1

            assert len(parts) == 2 or parts[2] + 2000 == year

            key = '%d-%02d-%02d' % (year, parts[0], parts[1])

            try:
                value = int(item[2])
            except ValueError:
                value = None

            history.append((key, value))

        return history

    def get_stacked_bar_chart_history(entity_id, row_label_offset=1,
                                      column_data_offset=2):
        """Return historical data from a stacked bar chart.

        This will extract the history data and perform date normalization.

        Note that this is currently geared toward the variant percentage
        bar chart, since there's no others. It might not handle other
        situations if presented later.

        Args:
            entity_id (str):
                The unique ID of the graph entity.

            row_label_offset (int, optional):
                The offset within a row's data where the column label is
                present.

            column_data_offset (int, optional):
                The offset within a column's data where the values begin.

        Returns:
            list of dict:
            The history data.
        """
        MONTH_MAP = {
            'Jan.': 'January',
            'Feb.': 'February',
            'Mar.': 'March',
            'Apr.': 'April',
            'Jun.': 'June',
            'Jul.': 'July',
            'Aug.': 'August',
            'Sept.': 'September',
            'Oct.': 'October',
            'Nov.': 'November',
            'Dec.': 'December',
        }

        entity = get_entity(entity_id)
        history = []

        chart_data = entity['props']['chartData']['data'][0]
        row_labels = chart_data[0][row_label_offset:]

        for column_data in chart_data[1:]:
            # Kind of a hack... Definitely going to have to change this if
            # dealing with more stacked bar charts.
            label = ' '.join(
                MONTH_MAP.get(_s, _s)
                for _s in column_data[0].split(' ')
            )
            row_data = column_data[column_data_offset - 1:]

            history.append({
                'label': label,
                'rows': dict(zip(row_labels, row_data)),
            })

        return history

    # Sometimes the county reports the current day in the report, and sometimes
    # the previous day. This flag dictates behavior around that.
    m = re.search(r'window.infographicData=(.*);</script>', response.text)

    if not m:
        raise ParseError('Unable to find infographicData in Butte Dashboard')

    try:
        dashboard_data = json.loads(m.group(1))
    except Exception as e:
        raise ParseError('Unable to parse infographicData in Butte Dashboard: '
                         '%s'
                         % e)

    datestamp = (datetime.now() - timedelta(days=1)).date()

    COUNTER_KEYS_TO_ENTITIES = {
        'confirmed_cases': {
            'labels': ['confirmed cases total'],
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
            'labels': ['deaths confirmed by viral test'],
            'entity_id': '9c8d7a74-c196-40b5-a2e5-3bd643bbae8b',
        },
        'hospitalized': {
            'labels': ['currently hospitalized'],
            'entity_id': '3e7ad00d-727d-436a-bdf6-edef227d7c28',
        },
    }

    CHART_KEYS_TO_ENTITIES = {
        'by_age': ('9ba3a895-019a-4e68-99ec-0eb7b5bd026c', 1),
        'deaths_by_age': ('f744cc14-179a-428f-8125-e68421784ada', 1),
        'probable_deaths_by_age': ('f744cc14-179a-428f-8125-e68421784ada', 2),
        'by_region': ('b26b9acd-b036-40bc-bbbe-68667dd338e4', 1),
        'probable_cases': ('7e36765a-23c2-4bc7-9fc1-ea4a927c8064', 2),
    }

    HISTORY_CHART_KEYS_TO_ENTITIES = {
        'cases': '65c738a3-4a8f-4938-92c5-d282362a4a77',
        'deaths': 'ee2d7dd8-d5b2-45c4-b866-6013db24ad19',
        'probable_cases': '7e36765a-23c2-4bc7-9fc1-ea4a927c8064',
    }

    STACKED_BAR_CHART_KEYS_TO_ENTITIES = {
        'sequenced_variants': 'f96daffb-b27b-458a-a474-b7460bee5415',
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


    scraped_history_data = {
        key: get_chart_history(entity_id)
        for key, entity_id in HISTORY_CHART_KEYS_TO_ENTITIES.items()
    }
    scraped_history_data.update({
        key: get_stacked_bar_chart_history(entity_id)
        for key, entity_id in STACKED_BAR_CHART_KEYS_TO_ENTITIES.items()
    })

    # Find the datestamp for vaccines.
    #
    # XXX This is no longer available on the dashboard itself.
    vaccines_datestamp = datestamp

    # We have two forms of dates being used on the dashboard.
    #
    # strftime sadly does not allow for representing day/month numbers
    # without a padded 0, so do this the hard way.
    graph_date_key1 = '%s-%s' % (datestamp.strftime('%d').lstrip('0'),
                                 datestamp.strftime('%b').lstrip('0'))
    graph_date_key2 = '%s/%s' % (datestamp.strftime('%m').lstrip('0'),
                                 datestamp.strftime('%d').lstrip('0'))

    try:
        by_age = scraped_data['by_age']
        by_region = scraped_data['by_region']
        deaths_by_age = scraped_data['deaths_by_age']
        probable_cases = scraped_data['probable_cases']
        probable_deaths_by_age = scraped_data['probable_deaths_by_age']

        # As of Monday, September 28, 2020, the county has changed the By Ages
        # graph to show the non-fatal vs. fatal cases, instead of total vs.
        # fatal. To preserve the information we had, we need to add the deaths
        # back in.
        for key in list(by_age.keys()):
            by_age[key] += deaths_by_age.get(key, 0)

        try:
            # Normal graph entries: <dd>-<Mon>
            probable_case_total = probable_cases[graph_date_key1]
        except KeyError:
            # Variant: <mm>/<dd>
            try:
                probable_case_total = probable_cases[graph_date_key2]
            except KeyError:
                # The graph wasn't updated in the current report.
                probable_case_total = None

        row_result = {
            'date': datestamp.strftime('%Y-%m-%d'),
            'confirmed_cases': scraped_data['confirmed_cases'],
            'probable_cases': probable_case_total,
            'deaths': scraped_data['deaths'],
            'deaths_by': {
                'age_ranges_in_years': {
                    '0-4': deaths_by_age.get('0-4 Years', 0),
                    '5-12': deaths_by_age.get('5-12 Years', 0),
                    '13-17': deaths_by_age.get('13-17 Years', 0),
                    '18-24': deaths_by_age['18-24 Years'],
                    '25-34': deaths_by_age['25-34 Years'],
                    '35-44': deaths_by_age['35-44 Years'],
                    '45-54': deaths_by_age['45-54 Years'],
                    '55-64': deaths_by_age['55-64 Years'],
                    '65-74': deaths_by_age['65-74 Years'],
                    '75_plus': deaths_by_age['75+ Years'],

                    # Legacy
                    '0-17': (deaths_by_age.get('0-4 Years', 0) +
                             deaths_by_age.get('5-12 Years', 0) +
                             deaths_by_age.get('13-17 Years', 0)),
                },
            },
            'probable_deaths_by': {
                'age_ranges_in_years': {
                    '0-4': probable_deaths_by_age.get('0-4 Years', 0),
                    '5-12': probable_deaths_by_age.get('5-12 Years', 0),
                    '13-17': probable_deaths_by_age.get('13-17 Years', 0),
                    '18-24': probable_deaths_by_age['18-24 Years'],
                    '25-34': probable_deaths_by_age['25-34 Years'],
                    '35-44': probable_deaths_by_age['35-44 Years'],
                    '45-54': probable_deaths_by_age['45-54 Years'],
                    '55-64': probable_deaths_by_age['55-64 Years'],
                    '65-74': probable_deaths_by_age['65-74 Years'],
                    '75_plus': probable_deaths_by_age['75+ Years'],
                },
            },
            'in_isolation': {
                'current': scraped_data['in_isolation'],
                'total_released': scraped_data['released_from_isolation'],
            },
            'viral_tests': {
                'total': None,
                'results': None,
            },
            'hospitalized': {
                'current': scraped_data['hospitalized'],
            },
            'age_ranges_in_years': {
                '0-4': by_age['0-4 Years'],
                '5-12': by_age['5-12 Years'],
                '13-17': by_age['13-17 Years'],
                '18-24': by_age['18-24 Years'],
                '25-34': by_age['25-34 Years'],
                '35-44': by_age['35-44 Years'],
                '45-54': by_age['45-54 Years'],
                '55-64': by_age['55-64 Years'],
                '65-74': by_age['65-74 Years'],
                '75_plus': by_age['75+ Years'],

                # Legacy
                '0-17': (by_age['0-4 Years'] +
                         by_age['5-12 Years'] +
                         by_age['13-17 Years']),
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
            'vaccines': {
                'total_allocation': None,
                'total_administered': None,
                'total_received': None,
                'total_first_doses_ordered': None,
                'total_second_doses_ordered': None,
                'total_fully_vaccinated': None,
                'as_of_date': vaccines_datestamp.strftime('%Y-%m-%d'),
            },
            'history': scraped_history_data,
        }
    except Exception as e:
        raise ParseError('Unable to build row data: %s' % e) from e

    add_or_update_json_date_row(out_filename, row_result)


def build_history_dataset(in_fp, out_filename, **kwargs):
    """Build a CSV dataset for Butte County Dashboard timeline histories.

    This will contain the history of cases, probable cases, and deaths.

    Args:
        in_fp (file):
            A file pointer to the JSON file being read.

        out_filename (str):
            The name of the outputted CSV file.

        **kwargs (dict, unused):
            Unused keyword arguments passed to this parser.
    """
    keys = ['cases', 'probable_cases', 'deaths']

    dataset = json.load(in_fp)
    history = dataset['dates'][-1]['history']

    dates_to_values = {}

    for key in keys:
        for date, value in history[key]:
            dates_to_values.setdefault(date, {})[key] = value

    with safe_open_for_write(out_filename) as fp:
        csv_writer = csv.DictWriter(fp, fieldnames=['date'] + keys)
        csv_writer.writeheader()

        for date, values in sorted(dates_to_values.items(),
                                   key=lambda pair: pair[0]):
            csv_writer.writerow(dict({
                'date': date,
            }, **values))


def build_sequenced_variants_dataset(in_fp, out_filename, **kwargs):
    """Build a CSV dataset for Butte County Dashboard sequenced variants.

    Args:
        in_fp (file):
            A file pointer to the JSON file being read.

        out_filename (str):
            The name of the outputted CSV file.

        **kwargs (dict, unused):
            Unused keyword arguments passed to this parser.
    """
    dataset = json.load(in_fp)
    data = dataset['dates'][-1]['history']['sequenced_variants']

    keys = sorted(list(data[0]['rows'].keys()))

    with safe_open_for_write(out_filename) as fp:
        csv_writer = csv.DictWriter(fp, fieldnames=['date'] + keys)
        csv_writer.writeheader()

        for column in data:
            csv_writer.writerow(dict({
                'date': column['label'],
            }, **column['rows']))


DATASETS = [
    {
        'filename': 'butte-dashboard.json',
        'format': 'json',
        'url': 'https://infogram.com/1pe66wmyjnmvkrhm66x9362kp3al60r57ex',
        'parser': build_dataset,
    },
    {
        'filename': 'butte-dashboard-v4.csv',
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
            ('Age 0-4 Years', ('age_ranges_in_years', '0-4')),
            ('Age 5-12 Years', ('age_ranges_in_years', '5-12')),
            ('Age 13-17 Years', ('age_ranges_in_years', '13-17')),
            ('Age 18-24 Years', ('age_ranges_in_years', '18-24')),
            ('Age 25-34 Years', ('age_ranges_in_years', '25-34')),
            ('Age 35-44 Years', ('age_ranges_in_years', '35-44')),
            ('Age 45-54 Years', ('age_ranges_in_years', '45-54')),
            ('Age 55-64 Years', ('age_ranges_in_years', '55-64')),
            ('Age 65-74 Years', ('age_ranges_in_years', '65-74')),
            ('Age 75+ Years', ('age_ranges_in_years', '75_plus')),
            ('Age 0-17 Years', ('age_ranges_in_years', '0-17')),
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
            ('Deaths - Age 0-4 Years',
             ('deaths_by', 'age_ranges_in_years', '0-4')),
            ('Deaths - Age 5-12 Years',
             ('deaths_by', 'age_ranges_in_years', '5-12')),
            ('Deaths - Age 13-17 Years',
             ('deaths_by', 'age_ranges_in_years', '13-17')),
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
            ('Deaths - Age 0-17 Years',
             ('deaths_by', 'age_ranges_in_years', '0-17')),
            ('Probably Cases', ('probable_cases',)),
            ('Probable Deaths - Age 0-4 Years',
             ('probable_deaths_by', 'age_ranges_in_years', '0-4')),
            ('Probable Deaths - Age 5-12 Years',
             ('probable_deaths_by', 'age_ranges_in_years', '5-12')),
            ('Probable Deaths - Age 13-17 Years',
             ('probable_deaths_by', 'age_ranges_in_years', '13-17')),
            ('Probable Deaths - Age 18-24 Years',
             ('probable_deaths_by', 'age_ranges_in_years', '18-24')),
            ('Probable Deaths - Age 25-34 Years',
             ('probable_deaths_by', 'age_ranges_in_years', '25-34')),
            ('Probable Deaths - Age 35-44 Years',
             ('probable_deaths_by', 'age_ranges_in_years', '35-44')),
            ('Probable Deaths - Age 45-54 Years',
             ('probable_deaths_by', 'age_ranges_in_years', '45-54')),
            ('Probable Deaths - Age 55-64 Years',
             ('probable_deaths_by', 'age_ranges_in_years', '55-64')),
            ('Probable Deaths - Age 65-74 Years',
             ('probable_deaths_by', 'age_ranges_in_years', '65-74')),
            ('Probable Deaths - Age 75+ Years',
             ('probable_deaths_by', 'age_ranges_in_years', '75_plus')),
            ('Vaccines - As Of Date',
             ('vaccines', 'as_of_date')),
            ('Vaccines - Total Allocation',
             ('vaccines', 'total_allocation')),
            ('Vaccines - Total Received',
             ('vaccines', 'total_received')),
            ('Vaccines - Total Administered',
             ('vaccines', 'total_administered')),
            ('Vaccines - Total First Doses Ordered',
             ('vaccines', 'total_first_doses_ordered')),
            ('Vaccines - Total Second Doses Ordered',
             ('vaccines', 'total_second_doses_ordered')),
            ('Vaccines - Total Fully-Vaccinated',
             ('vaccines', 'total_fully_vaccinated')),
        ],
    },
    {
        'filename': 'butte-dashboard-history.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'butte-dashboard.json',
            'format': 'json',
        },
        'parser': build_history_dataset,
    },
    {
        'filename': 'butte-dashboard-sequenced-variants.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'butte-dashboard.json',
            'format': 'json',
        },
        'parser': build_sequenced_variants_dataset,
    },
]
