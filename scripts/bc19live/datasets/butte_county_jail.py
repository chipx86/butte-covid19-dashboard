import re
from datetime import datetime

from bc19live.errors import ParseError
from bc19live.utils import (add_or_update_json_date_row,
                            convert_json_to_csv)


def build_dataset(response, out_filename, **kwargs):
    """Parse the Butte County Jail page.

    The Butte County Jail page uses a simple template for their reporting.
    This parser looks for parts of that template and pulls out the numbers,
    generating useful JSON data.

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

    datestamp = datetime(month=months[m.group(1).lower()],
                         day=int(m.group(2)),
                         year=int(m.group(3)))

    if datestamp.date() != datetime.now().date():
        # This is stale data not from today. OR it might be new data but
        # the county forgot to update the datestamp. So don't risk
        # overwriting historical data, and instead bail.
        return False

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


DATASETS = [
    {
        'filename': 'butte-county-jail.json',
        'format': 'json',
        'url': 'https://www.buttecounty.net/sheriffcoroner/Covid-19',
        'parser': build_dataset,
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
]
