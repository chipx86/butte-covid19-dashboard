import codecs
import csv
from datetime import datetime

from bc19live.utils import (add_or_update_json_date_row,
                            convert_json_to_csv,
                            parse_int)


def build_dataset(response, out_filename, **kwargs):
    """Parse the Chico Unified School District COVID-19 dashboard.

    This exists as a spreadsheet on Google Sheets. It's listed as updating
    weekly, though we'll pull it down daily in case any numbers change.

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
    school_type_map = {
        'Elementary Schools': 'elementary',
        'Junior Highs': 'junior_high',
        'High Schools': 'high_school',
        'State Preschools': 'state_preschools',
        'Other': 'other',
    }

    lines = list(response.iter_lines())[4:]
    lines[0] = b'Type' + lines[0]

    result = {}
    by_school_type = {}
    cur_section = None
    reader = csv.DictReader(codecs.iterdecode(lines, 'utf-8'),
                            delimiter=',')

    for row in reader:
        location = row['School/Location']

        if not location:
            # Empty line.
            continue

        pop_at_site = row['Total Students / Staff at Site*']

        if pop_at_site == 'N/A':
            pop_at_site = None
        else:
            pop_at_site = parse_int(pop_at_site)

        row_payload = {
            'population_at_site': pop_at_site,
            'total_cases': {
                'remote': parse_int(row['Online Learners / Independent Study']),
                'staff': parse_int(row['Staff']),
                'students': parse_int(row['Students']),
            },
        }

        if location == 'DISTRICT-WIDE TOTAL':
            result['district_wide'] = row_payload

            # We're done.
            break
        else:
            if row['Type']:
                cur_section = school_type_map[row['Type']]

            if location.startswith('State Funded Preschools'):
                location = 'State Funded Preschools'

            by_school_type.setdefault(cur_section, {})[location] = row_payload

    for school_type, locations in by_school_type.items():
        pop = 0
        remote_cases = 0
        staff_cases = 0
        students_cases = 0

        for location, row_payload in locations.items():
            cases_payload = row_payload['total_cases']

            pop += row_payload['population_at_site'] or 0
            remote_cases += cases_payload['remote'] or 0
            staff_cases += cases_payload['staff'] or 0
            students_cases += cases_payload['students'] or 0

        locations['totals'] = {
            'population_at_site': pop,
            'total_cases': {
                'remote': remote_cases,
                'staff': staff_cases,
                'students': students_cases,
            },
        }

    result.update(by_school_type)

    # It seems they update more than once a week, but the Last Updated may
    # not reflect this. For now, pull data in daily, and we'll find our for
    # ourselves.
    result['date'] = datetime.now().strftime('%Y-%m-%d')

    add_or_update_json_date_row(out_filename, result)

    return True


DATASETS = [
    {
        'filename': 'cusd.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/u/0/d/e/2PACX-1vSPLYKyOXjJQbvrnZtU9Op0uMoH84EKYP7pEp1ANCAw3yWg3LswQs5wfOSKFt5AukxPymzZ9QczlMDh/pub/sheet?headers=false&gid=2096611352&output=csv',
        'parser': build_dataset,
    },
    {
        'filename': 'cusd.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'cusd.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
        ] + [
            ('District - %s Cases' % _cases_name,
             ('district_wide', 'total_cases', _cases_key))
            for _cases_key, _cases_name in (('staff', 'Staff'),
                                            ('students', 'Student'),
                                            ('remote', 'Remote'))
        ] + [
            ('%s - %s Cases' % (_school_type, _cases_name),
             (_school_type_key, 'totals', 'total_cases', _cases_key))
            for _school_type_key, _school_type in (
                ('elementary', 'Elementary'),
                ('junior_high', 'Junior High'),
                ('high_school', 'High School'),
                ('other', 'Other')
            )
            for _cases_key, _cases_name in (('staff', 'Staff'),
                                            ('students', 'Student'),
                                            ('remote', 'Remote'))
        ] + [
            ('%s - %s Cases' % (_location, _cases_name),
             (_school_type_key, _location, 'total_cases', _cases_key))
            for _school_type_key, _locations in (
                ('elementary', (
                    'Chapman Elementary School',
                    'Citrus Elementary School',
                    'Emma Wilson Elementary School',
                    'Hooker Oak Elementary School',
                    'McManus Elementary School',
                    'Little Chico Creek Elementary School',
                    'Marigold/Loma Vista School',
                    'Neal Dow Elementary School',
                    'Parkview Elementary School',
                    'Rosedale Elementary School',
                    'Shasta Elementary School',
                    'Sierra View Elementary School',
                    'Oak Bridge Academy Elementary School (K-12)',
                )),
                ('junior_high', (
                    'Bidwell Junior High School',
                    'Chico Junior High School',
                    'Marsh Junior High School',
                )),
                ('high_school', (
                    'Chico High School',
                    'Pleasant Valley High School',
                    'Fair View High School',
                    'Oakdale/AFC/CAL',
                )),
                ('other', (
                    'Itinerant Staff',
                    'Non-School Campus',
                    'Online Learning',
                )),
                ('state_preschools', (
                    'State Funded Preschools',
                )),
            )
            for _location in _locations
            for _cases_key, _cases_name in (('staff', 'Staff'),
                                            ('students', 'Student'),
                                            ('remote', 'Remote'))
        ],
    },
]
