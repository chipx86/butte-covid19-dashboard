import codecs
import csv
from datetime import datetime

from bc19live.errors import ParseError
from bc19live.utils import (add_or_update_json_date_row,
                            convert_json_to_csv,
                            parse_int)


def build_dataset(response, out_filename, **kwargs):
    """Parse the Oroville Union High School District COVID-19 dashboard.

    This exists as a spreadsheet on Google Sheets. It doesn't appear to be
    updated very often (as of January 14, 2021), and contains minimal
    information.

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
    SCHOOL_HEADER = 'School/Location'
    POP_HEADER = '# of Students/Staff*'
    STUDENTS_HEADER = 'Students'
    STAFF_HEADER = 'Staff'

    lines = list(response.iter_lines())

    # This is completely mangled in the CSV file, so let's fix things
    # up a bit.
    lines[0] = (
        '"%s","%s","%s","%s"' % (SCHOOL_HEADER, POP_HEADER, STUDENTS_HEADER,
                                 STAFF_HEADER)
    ).encode('utf-8')

    last_updated = None
    schools = {}
    result = {
        'schools': schools,
    }

    reader = csv.DictReader(codecs.iterdecode(lines, 'utf-8'),
                            delimiter=',')
    store_results = True

    for row in reader:
        school = row[SCHOOL_HEADER].replace('*', '')

        if store_results:
            pop = parse_int(row[POP_HEADER])
            students = parse_int(row[STUDENTS_HEADER])
            staff = parse_int(row[STAFF_HEADER])

            row_payload = {
                'population_at_site': pop,
                'total_cases': {
                    'staff': staff,
                    'students': students,
                },
            }

            if school == 'Total':
                result['totals'] = row_payload
                store_results = False
            else:
                schools[school] = row_payload
        elif school.startswith('Last updated'):
            last_updated = datetime.strptime(school, 'Last updated %B %d, %Y')
            break

    if last_updated is None:
        raise ParseError(
            'Could not find datestamp for Oroville Union High School District')

    result['date'] = last_updated.strftime('%Y-%m-%d')

    add_or_update_json_date_row(out_filename, result)

    return True


DATASETS = [
    {
        'filename': 'oroville-union-high-school-district.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/d/1uOghJGc0QCroA8e2xCaHIEYT-STgJtCgGpetVm6Tny0/gviz/tq?tqx=out:csv',
        'parser': build_dataset,
    },
    {
        'filename': 'oroville-union-high-school-district.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'oroville-union-high-school-district.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
        ] + [
            ('%s - %s Cases' % (_school, _cases_name),
             ('schools', _school, 'total_cases', _cases_key))
            for _school in ('Las Plumas High School',
                            'Oroville High School',
                            'Prospect High School',
                            'Oroville Adult School',
                            'Adult Transition Center',
                            'Independent Study',
                            'Other')
            for _cases_key, _cases_name in (('staff', 'Staff'),
                                            ('students', 'Student'),
                                            ('remote', 'Remote'))
        ],
    },
]
