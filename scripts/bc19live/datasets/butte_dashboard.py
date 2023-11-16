import csv
import itertools
import json
import os
import re
from collections import OrderedDict
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from bc19live.errors import ParseError
from bc19live.utils import (add_or_update_json_date_row,
                            convert_json_to_csv,
                            safe_open_for_write)


def build_dataset(response, out_filename, **kwargs):
    """Parse the Butte County dashboard.

    This extracts case, fatalities, hospitalization, demographics, and testing
    information from the Butte County COVID-19 dashboard, hosted on Netlify.
    It's built to work around quirks that may show up from time to time, and
    to cancel out if any data appears to be missing.

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

    def get_counter_value(entity_id):
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
        div = soup.find(id=entity_id)

        if not div:
            raise ParseError('Could not find counter ID "%s"' % entity_id)

        value_el = div.find('span', 'value-output')

        if not value_el:
            raise ParseError('Could not find "value-output" for counter ID '
                             '"%s"'
                             % entity_id)

        value = value_el.string

        try:
            return int(re.sub(r'[, ]+', '', value))
        except Exception:
            raise ParseError('Expected value %r for counter ID "%s" to be int, '
                             'got %s'
                             % (value, entity_id, type(value)))

    def get_chart_data(container_id, _chart_data_cache={}):
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
        try:
            data = _chart_data_cache[container_id]
        except KeyError:
            script_el = soup.find(id=container_id).find('script')

            if script_el is None:
                raise ParseError('Could not find chart data for widget ID "%s"'
                                 % container_id)

            try:
                data = json.loads(script_el.string)
            except json.JSONDecodeError:
                raise ParseError('Unable to parse JSON chart data for widget '
                                 'ID "%s"'
                                 % container_id)

            _chart_data_cache[container_id] = data

        return data

    def get_chart_axis(container_id, label_key, value_key, data_index=0,
                       **kwargs):
        data = get_chart_data(container_id, **kwargs)

        try:
            chart_data = data['x']['data'][data_index]
            labels = chart_data[label_key]
            values = chart_data[value_key]
        except KeyError as e:
            raise ParseError('Unable to find chart data key "%s" for widget '
                             'ID "%s"'
                             % (e, container_id))

        return labels, values

    def get_chart_keyvals(label_map={}, label_key='y', value_key='x',
                          **kwargs):
        chart_data = get_chart_axis(label_key=label_key,
                                    value_key=value_key,
                                    **kwargs)

        return OrderedDict(
            (label_map.get(_label, _label), _value)
            for _label, _value in zip(*chart_data)
        )

    def get_chart_history(label_key='x', value_key='y', sum_data=False,
                          **kwargs):
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
        labels, values = get_chart_axis(label_key=label_key,
                                        value_key=value_key,
                                        **kwargs)

        if sum_data:
            return list(zip(labels, itertools.accumulate(values)))
        else:
            return list(zip(labels, values))

    def get_variant_data(**kwargs):
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
        VARIANT_LABEL_RE = re.compile(
            r'^<b>(?P<name>[^:]+): </b><br>(?P<month>[^\s]+) (?P<year>\d{4}) '
            r'(?P<count>\d+).*')

        VARIANT_NAME_MAP = {
            'Omicron BA.1': 'Omicron - BA.1',
            'Omicron BA.2': 'Omicron - BA.2',
        }

        data = get_chart_data(**kwargs)

        all_variant_names = set()
        dates = {}

        for variant_data in data['x']['data']:
            # This is pretty hacky. There's no other way currently to get
            # the information we need.
            for date, custom_data in zip(variant_data['x'],
                                         variant_data['customdata']):
                m = VARIANT_LABEL_RE.match(custom_data)

                if not m:
                    raise ParseError('Unable to match custom_data label for '
                                     'variant data: %r'
                                     % custom_data)

                variant_name = m.group('name')
                month = m.group('month')
                year = m.group('year')
                count = int(m.group('count'))

                variant_name = VARIANT_NAME_MAP.get(variant_name, variant_name)
                all_variant_names.add(variant_name)

                if date not in dates:
                    dates[date] = {
                        'variants': OrderedDict(),
                        'date_label': '%s-%s' % (month, year),
                    }

                dates[date]['variants'][variant_name] = count

        results = []

        for date, date_info in sorted(dates.items(),
                                      key=lambda pair: pair[0]):
            date_variants = date_info['variants']
            total = sum(date_variants.values())

            results.append({
                'label': '%s (N = %d)' % (date_info['date_label'], total),
                'rows': {
                    _variant_name: date_variants.get(_variant_name, 0)
                    for _variant_name in all_variant_names
                },
            })

        return results

    soup = BeautifulSoup(response.text, 'html5lib')

    datestamp = (datetime.now() - timedelta(days=1)).date()

    COUNTER_KEYS_TO_ENTITIES = {
        'confirmed_cases': {
            'entity_id': 'total-confirmed-cases-since-march-14-2020',
        },
        'deaths': {
            'entity_id': 'total-laboratory-confirmed-lives-lost-to-date',
        },
        'hospitalized': {
            'entity_id': 'currently-hospitalized-in-butte-county',
        },
    }

    # On February 28, 2022, Butte County Public Health terminated almost all
    # of the information they had displayed on the dashboard. There's no longer
    # an ability to graph smoe of the data we once had (like cases by area).
    #
    # The following map entries are left here for historical purposes.
    CHART_KEYS_TO_ENTITIES = {
        #'by_age': {
        #    'container_id': 'cases-by-age',
        #    'label_map': AGE_LABEL_MAP,
        #},
        #'deaths_by_age': {
        #    'container_id': 'verified-covid-19-lives-lost-by-age-group',
        #    'label_map': AGE_LABEL_MAP,
        #},
        #'probable_deaths_by_age': {
        #    'data_index': 1,
        #    'container_id': 'verified-covid-19-lives-lost-by-age-group',
        #    'label_map': AGE_LABEL_MAP,
        #},
    }

    HISTORY_CHART_KEYS_TO_ENTITIES = {
        'cases': {
            'container_id': 'cases',
            'data_index': 1,
            'sum_data': True,
        },
        'deaths': {
            'container_id': 'verified-covid-19-lives-lost',
            'data_index': 0,
            'sum_data': True,
        },
        'probable_cases': {
            'container_id': 'cases',
            'data_index': 2,
            'sum_data': True,
        },
    }

    scraped_data = {
        _key: get_counter_value(**_kwargs)
        for _key, _kwargs in COUNTER_KEYS_TO_ENTITIES.items()
    }
    scraped_data.update({
        _key: get_chart_keyvals(**_kwargs)
        for _key, _kwargs in CHART_KEYS_TO_ENTITIES.items()
    })

    scraped_history_data = {
        _key: get_chart_history(**_kwargs)
        for _key, _kwargs in HISTORY_CHART_KEYS_TO_ENTITIES.items()
    }
    scraped_history_data['sequenced_variants'] = \
        get_variant_data(container_id='variant-sequencing-results')

    try:
        by_age = scraped_data.get('by_age', {})
        by_region = scraped_data.get('by_region', {})
        deaths_by_age = scraped_data.get('deaths_by_age', {})
        probable_cases = scraped_data.get('probable_cases', {})
        probable_deaths_by_age = scraped_data.get('probable_deaths_by_age', {})

        # As of Monday, September 28, 2020, the county has changed the By Ages
        # graph to show the non-fatal vs. fatal cases, instead of total vs.
        # fatal. To preserve the information we had, we need to add the deaths
        # back in.
        for key in list(by_age.keys()):
            by_age[key] += deaths_by_age.get(key, 0)

        probable_case_total = sum(probable_cases.values())

        row_result = {
            'date': datestamp.strftime('%Y-%m-%d'),
            'confirmed_cases': scraped_data['confirmed_cases'],
            'probable_cases': probable_case_total,
            'deaths': scraped_data.get('deaths', []),
            'deaths_by': {
                'age_ranges_in_years': {
                    '0-4': deaths_by_age.get('0-4', 0),
                    '5-12': deaths_by_age.get('5-12', 0),
                    '13-17': deaths_by_age.get('13-17', 0),
                    '18-24': deaths_by_age.get('18-24'),
                    '25-34': deaths_by_age.get('25-34'),
                    '35-44': deaths_by_age.get('35-44'),
                    '45-54': deaths_by_age.get('45-54'),
                    '55-64': deaths_by_age.get('55-64'),
                    '65-74': deaths_by_age.get('65-74'),
                    '75_plus': deaths_by_age.get('75+'),

                    # Legacy
                    '0-17': (deaths_by_age.get('0-4', 0) +
                             deaths_by_age.get('5-12', 0) +
                             deaths_by_age.get('13-17', 0)),
                },
            },
            'probable_deaths_by': {
                'age_ranges_in_years': {
                    '0-4': probable_deaths_by_age.get('0-4', 0),
                    '5-12': probable_deaths_by_age.get('5-12', 0),
                    '13-17': probable_deaths_by_age.get('13-17', 0),
                    '18-24': probable_deaths_by_age.get('18-24'),
                    '25-34': probable_deaths_by_age.get('25-34'),
                    '35-44': probable_deaths_by_age.get('35-44'),
                    '45-54': probable_deaths_by_age.get('45-54'),
                    '55-64': probable_deaths_by_age.get('55-64'),
                    '65-74': probable_deaths_by_age.get('65-74'),
                    '75_plus': probable_deaths_by_age.get('75+'),
                },
            },
            'in_isolation': {
                'current': scraped_data.get('in_isolation'),
                'total_released': scraped_data.get('released_from_isolation'),
            },
            'viral_tests': {
                'total': None,
                'results': None,
            },
            'hospitalized': {
                'current': scraped_data.get('hospitalized'),
            },
            'age_ranges_in_years': {
                '0-4': by_age.get('0-4'),
                '5-12': by_age.get('5-12'),
                '13-17': by_age.get('13-17'),
                '18-24': by_age.get('18-24'),
                '25-34': by_age.get('25-34'),
                '35-44': by_age.get('35-44'),
                '45-54': by_age.get('45-54'),
                '55-64': by_age.get('55-64'),
                '65-74': by_age.get('65-74'),
                '75_plus': by_age.get('75+'),

                # Legacy
                '0-17': (
                    (by_age.get('0-4') +
                     by_age.get('5-12') +
                     by_age.get('13-17'))
                    if by_age
                    else None
                ),
                '18-49': None,
                '50-64': None,
                '65_plus': (
                    (by_age['65-74'] + by_age['75+'])
                    if by_age
                    else None
                ),
            },
            'regions': {
                'biggs_gridley': by_region.get('Biggs/Gridley'),
                'chico': by_region.get('Chico'),
                'durham': by_region.get('Durham'),
                'oroville': by_region.get('Oroville'),
                'other': by_region.get('Other/Missing'),
                'ridge': by_region.get('Ridge Communities'),

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
                'as_of_date': datestamp.strftime('%Y-%m-%d'),
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
    start_i = 0

    for date, value in history['cases']:
        if value == '':
            start_i += 1
            break

    for key in keys:
        for date, value in history.get(key, [])[start_i:]:
            dates_to_values.setdefault(date, {})[key] = value

    with safe_open_for_write(out_filename) as fp:
        csv_writer = csv.DictWriter(fp, fieldnames=['date'] + keys)
        csv_writer.writeheader()

        for date, values in sorted(dates_to_values.items(),
                                   key=lambda pair: pair[0]):
            if datetime.strptime(date, '%Y-%m-%d') >= HISTORY_START_DATE:
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


HISTORY_START_DATE = datetime(2020, 3, 14)


DATASETS = [
    {
        'filename': 'butte-dashboard.json',
        'format': 'json',
        'url': 'https://bcph.netlify.app/',
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
