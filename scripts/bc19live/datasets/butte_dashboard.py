import json
import re
from collections import OrderedDict
from datetime import datetime, timedelta

from bc19live.errors import ParseError
from bc19live.utils import add_or_update_json_date_row, convert_json_to_csv


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
                    if len(blocks) >= i and label in blocks[0]['text'].lower():
                        value = (
                            blocks[0]['text']
                            .lower()
                            .split(label)[0]
                            .strip()
                        )

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
            return int(value.replace(',', ''))
        except Exception:
            raise ParseError('Expected value %r for entity %s to be int, '
                             'got %s'
                             % (value, entity_id, type(value)))

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

    m = re.search(r'window.infographicData=(.*);</script>', response.text)

    if not m:
        raise ParseError('Unable to find infographicData in Butte Dashboard')

    try:
        dashboard_data = json.loads(m.group(1))
    except Exception as e:
        raise ParseError('Unable to parse infographicData in Butte Dashboard: '
                         '%s'
                         % e)

    try:
        entity = get_entity('7758d945-3baa-414b-8672-fb348d435436')
    except KeyError:
        raise ParseError('Unable to find datestamp entity in Butte Dashboard')

    m = re.search(r'as of (\d+)/(\d+)/(\d{4})',
                  entity['props']['content']['blocks'][0]['text'],
                  re.I)

    if not m:
        raise ParseError('Unable to find datestamp in Butte Dashboard')

    # Sometimes the county reports the current day in the report, and sometimes
    # the previous day. This flag dictates behavior around that.
    REPORT_USES_PREV_DAY = True

    datestamp = datetime(month=int(m.group(1)),
                         day=int(m.group(2)),
                         year=int(m.group(3)))

    if not REPORT_USES_PREV_DAY:
        datestamp -= timedelta(days=1)

    if datestamp.date() != (datetime.now() - timedelta(days=1)).date():
        # This is stale data not from today's report OR it might be new
        # data but the county forgot to update the datestamp on it. So don't
        # risk overwriting historical data, and instead bail.
        return False

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
            'labels': ['deaths confirmed by viral test'],
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
        'vaccines_total_allocation': {
            'labels': ['total vaccine allocation for butte county'],
            'entity_id': '6735874d-4394-4f10-92c4-60a861aef46f',
        },
        'vaccines_total_received': {
            'labels': ['total vaccine received'],
            'entity_id': 'f844fcb6-6b99-4267-8491-9f43e47bcc63',
        },
        'vaccines_total_first_doses_ordered': {
            'labels': ['total number of first doses ordered'],
            'entity_id': '70ab4c6c-10c4-4f04-ae90-d9a0ddcdffca',
        },
        'vaccines_total_second_doses_ordered': {
            'labels': ['total number of second doses ordered'],
            'entity_id': '8637a3ab-5335-467d-95b8-53f413a74238',
        },
        'vaccines_total_administered': {
            'labels': ['total administered vaccines*'],
            'entity_id': '74e76670-078b-40b9-8ec5-b61159126122',
        },
    }

    CHART_KEYS_TO_ENTITIES = {
        'by_age': ('9ba3a895-019a-4e68-99ec-0eb7b5bd026c', 1),
        'deaths_by_age': ('f744cc14-179a-428f-8125-e68421784ada', 1),
        'probable_deaths_by_age': ('f744cc14-179a-428f-8125-e68421784ada', 2),
        'by_region': ('b26b9acd-b036-40bc-bbbe-68667dd338e4', 1),
        'probable_cases': ('7e36765a-23c2-4bc7-9fc1-ea4a927c8064', 2),
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

    # Find the datestamp for vaccines.
    try:
        entity = get_entity('0ebe511f-988e-4b1f-a68d-9fc2f4be5901')
    except KeyError:
        raise ParseError('Unable to find vaccine datestamp entity in '
                         'Butte Dashboard')

    m = re.search(r'Updated (\d+)/(\d+)/(\d{4})',
                  entity['props']['content']['blocks'][0]['text'],
                  re.I)

    if not m:
        raise ParseError('Unable to parse vaccine datestamp entity in '
                         'Butte Dashboard')

    vaccines_datestamp = datetime(month=int(m.group(1)),
                                  day=int(m.group(2)),
                                  year=int(m.group(3)))

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
                'total': scraped_data['total_viral_tests'],
                'results': scraped_data['daily_viral_test_results'],
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
                'total_allocation': scraped_data['vaccines_total_allocation'],
                'total_administered':
                    scraped_data['vaccines_total_administered'],
                'total_received': scraped_data['vaccines_total_received'],
                'total_first_doses_ordered':
                    scraped_data['vaccines_total_first_doses_ordered'],
                'total_second_doses_ordered':
                    scraped_data['vaccines_total_second_doses_ordered'],
                'as_of_date': vaccines_datestamp.strftime('%Y-%m-%d'),
            },
        }
    except Exception as e:
        raise ParseError('Unable to build row data: %s' % e) from e

    add_or_update_json_date_row(out_filename, row_result)


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
        ],
    },
]
