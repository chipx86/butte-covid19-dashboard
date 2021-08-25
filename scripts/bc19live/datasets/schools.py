import codecs
import csv
import json
from copy import deepcopy
from datetime import datetime, timedelta

from bc19live.utils import (build_missing_date_rows,
                            convert_json_to_csv,
                            parse_int,
                            safe_open_for_write)


def build_district_json(response, out_filename, info, **kwargs):
    """Build a dataset for a school district.

    This takes the data in the spreadsheet and builds a JSON dataset containing
    information on each school's cases.

    Args:
        response (requests.Response):
            The HTTP response containing the page.

        out_filename (str):
            The name of the outputted JSON file.

        info (dict):
            Information on the dataset.

        **kwargs (dict, unused):
            Unused keyword arguments passed to this parser.
    """
    DEFAULT_CASE_COUNTS_DATA = {
        'students_in_person': 0,
        'students_remote': 0,
        'staff_in_person': 0,
        'staff_remote': 0,
    }

    DEFAULT_SCHOOL_DATA = {
        'population_at_site': 0,
        'new_cases': DEFAULT_CASE_COUNTS_DATA.copy(),
        'total_cases': DEFAULT_CASE_COUNTS_DATA.copy(),
    }

    school_types = info['school_types']
    types_by_school = {
        _school: _school_type
        for _school_type, _schools in school_types.items()
        for _school in _schools
    }

    last_date = None
    last_date_row = None
    results = []
    total_in_district = 0

    reader = csv.DictReader(codecs.iterdecode(response.iter_lines(), 'utf-8'),
                            delimiter=',')

    for row in reader:
        date_str = row['Date']

        if not date_str:
            # This is a gap date in the spreadsheet to allow for skipping
            # weeks.
            continue

        date = datetime.strptime(date_str, '%m/%d/%Y')
        school = row['School']
        school_type = types_by_school[school]

        total_at_school = parse_int(row['Total Students/Staff at School'])
        total_in_district = max(
            total_in_district,
            parse_int(row['Total Students/Staff in District']))

        new_cases = {
            'students_in_person': int(row['New In-Person Student Cases']),
            'students_remote': int(row['New Remote Student Cases']),
            'staff_in_person': int(row['New In-Person Staff Cases']),
            'staff_remote': int(row['New Remote Staff Cases']),
        }

        if date == last_date:
            date_row = last_date_row
            district_wide_data = date_row['district_wide']
        else:
            if last_date is not None:
                results += build_missing_date_rows(cur_date=date,
                                                   latest_date=last_date)

                district_wide_data = deepcopy(last_date_row['district_wide'])
            else:
                district_wide_data = deepcopy(DEFAULT_SCHOOL_DATA)

            district_wide_data['new_cases'] = DEFAULT_CASE_COUNTS_DATA.copy()

            date_row = {
                'date': date.strftime('%Y-%m-%d'),
                'district_wide': district_wide_data,
            }

            for _school_type, _schools in school_types.items():
                school_type_data = {}
                date_row[_school_type] = school_type_data

                for _school in _schools:
                    if last_date_row is None:
                        school_type_data[_school] = \
                            deepcopy(DEFAULT_SCHOOL_DATA)
                    else:
                        # Copy over the entire previous row, and then set
                        # all the new cases to 0.
                        school_type_data[_school] = deepcopy(
                            last_date_row[_school_type][_school])

                    school_type_data[_school]['new_cases'] = \
                        DEFAULT_CASE_COUNTS_DATA.copy()

            results.append(date_row)
            last_date = date
            last_date_row = date_row

        # Set the new data.
        school_total_cases = date_row[school_type][school]['total_cases']
        district_total_cases = district_wide_data['total_cases']
        district_new_cases = district_wide_data['new_cases']

        for key, new_count in new_cases.items():
            school_total_cases[key] += new_count
            district_total_cases[key] += new_count
            district_new_cases[key] += new_count

        date_row[school_type][school].update({
            'new_cases': new_cases,
            'population_at_site': total_at_school,
        })
        date_row['district_wide']['population_at_site'] = total_in_district

    dataset = {
        'dates': results,
    }

    with safe_open_for_write(out_filename) as fp:
        json.dump(dataset,
                  fp,
                  indent=2,
                  sort_keys=True)


def build_all_schools_json(in_fps, out_filename, info, **kwargs):
    """Build a dataset covering all schools in all districts.

    This processes all the built school district datasets and combines them
    into a single one.

    Args:
        in_fps (dict):
            A mapping of school district key to file pointer.

        out_filename (str):
            The name of the outputted JSON file.

        info (dict):
            Information on the dataset.

        **kwargs (dict, unused):
            Unused keyword arguments passed to this parser.
    """
    district_key_map = info['district_key_map']
    results_by_date = {}

    for district_key, in_fp in in_fps.items():
        school_rows = json.load(in_fp).get('dates', [])
        district_name = district_key_map[district_key]

        for row in school_rows:
            date = row['date']
            row = row.copy()
            del row['date']

            new_row = results_by_date.setdefault(date, {
                'date': date,
                'districts': {},
            })

            if row:
                new_row['districts'][district_name] = row

    results = [
        _row_data
        for _date, _row_data in sorted(results_by_date.items(),
                                       key=lambda _pair: _pair[0])
    ]

    with safe_open_for_write(out_filename) as fp:
        json.dump(results,
                  fp,
                  indent=2,
                  sort_keys=True)


DATASETS = [
    {
        'filename': 'schools-csuchico.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRUZCiEH2327_GwtD13qx-R6QpZOx5nv3UnnG-bFd-t-dwAv_OqYTiQLI55-vL_TfOsbsFtbK-lwJyx/pub/sheet?gid=530156977&output=csv',
        'parser': build_district_json,
        'school_types': {
            'college': [
                'Chico State',
            ],
        },
    },
    {
        'filename': 'schools-cusd.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRUZCiEH2327_GwtD13qx-R6QpZOx5nv3UnnG-bFd-t-dwAv_OqYTiQLI55-vL_TfOsbsFtbK-lwJyx/pub/sheet?gid=0&output=csv',
        'parser': build_district_json,
        'school_types': {
            'preschool': [
                'State Funded Preschools',
                'Preschools',
            ],
            'elementary': [
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
                'Oak Bridge Academy Elementary School',
            ],
            'junior_high': [
                'Bidwell Junior High School',
                'Chico Junior High School',
                'Marsh Junior High School',
            ],
            'high_school': [
                'Chico High School',
                'Pleasant Valley High School',
                'Fair View High School',
                'Oakdale/AFC/CAL',
            ],
            'other': [
                'Itinerant Staff',
                'Non-School Campus',
                'Online Learning',
            ],
        },
    },
    {
        'filename': 'schools-dusd.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRUZCiEH2327_GwtD13qx-R6QpZOx5nv3UnnG-bFd-t-dwAv_OqYTiQLI55-vL_TfOsbsFtbK-lwJyx/pub/sheet?gid=407839734&output=csv',
        'parser': build_district_json,
        'school_types': {
            'elementary': [
                'Durham Elementary School',
            ],
            'junior_high': [
                'Durham Intermediate School',
            ],
            'high_school': [
                'Durham High School',
            ],
        },
    },
    {
        'filename': 'schools-inspire.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRUZCiEH2327_GwtD13qx-R6QpZOx5nv3UnnG-bFd-t-dwAv_OqYTiQLI55-vL_TfOsbsFtbK-lwJyx/pub/sheet?gid=1222917900&output=csv',
        'parser': build_district_json,
        'school_types': {
            'high_school': [
                'Inspire',
            ],
        },
    },
    {
        'filename': 'schools-ocesd.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRUZCiEH2327_GwtD13qx-R6QpZOx5nv3UnnG-bFd-t-dwAv_OqYTiQLI55-vL_TfOsbsFtbK-lwJyx/pub/sheet?gid=814817652&output=csv',
        'parser': build_district_json,
        'school_types': {
            'preschool': [
                'Sierra Del Oro Preschool',
            ],
            'elementary': [
                'Oakdale Heights Elementary School',
                'Ophir Elementary School',
                'Stanford Avenue Elementary School',
                'Wyandotte Academy Elementary School',
            ],
            'junior_high': [
                'Central Middle School',
                'Ishi Hills Middle School',
            ],
            'other': [
                'District-wide Positions',
            ],
        },
    },
    {
        'filename': 'schools-ouhsd.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRUZCiEH2327_GwtD13qx-R6QpZOx5nv3UnnG-bFd-t-dwAv_OqYTiQLI55-vL_TfOsbsFtbK-lwJyx/pub/sheet?gid=636722915&output=csv',
        'parser': build_district_json,
        'school_types': {
            'high_school': [
                'Las Plumas High School',
                'Oroville High School',
                'Prospect High School',
            ],
            'other': [
                'Oroville Adult School',
                'Adult Transition Center',
                'Independent Study',
                'Other',
            ],
        },
    },
    {
        'filename': 'schools-puesd.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRUZCiEH2327_GwtD13qx-R6QpZOx5nv3UnnG-bFd-t-dwAv_OqYTiQLI55-vL_TfOsbsFtbK-lwJyx/pub/sheet?gid=1672949213&output=csv',
        'parser': build_district_json,
        'school_types': {
            'preschool': [
                'Honcut Preschool',
                'Helen Wilcox Preschool',
                'Palermo Preschool',
            ],
            'elementary': [
                'Honcut Elementary School',
                'Helen Wilcox Elementary School',
                'Golden Hills Elementary School',
                'Palermo School',
            ],
            'other': [
                'District-wide',
            ],
        },
    },
    {
        'filename': 'schools-pusd.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRUZCiEH2327_GwtD13qx-R6QpZOx5nv3UnnG-bFd-t-dwAv_OqYTiQLI55-vL_TfOsbsFtbK-lwJyx/pub/sheet?gid=584485570&output=csv',
        'parser': build_district_json,
        'school_types': {
            'preschool': [
            ],
            'elementary': [
                'Cedarwood Elementary School',
                'Paradise Ridge Elementary School',
                'Pine Ridge Elementary School',
            ],
            'high_school': [
                'Paradise High School',
                'Ridgeview High School',
            ],
            'other': [
                'Paradise e-Learning',
                'Non-School Campus',
            ],
        },
    },
    {
        'filename': 'schools.json',
        'format': 'json',
        'parser': build_all_schools_json,
        'local_sources': {
            'csuchico': {
                'filename': 'schools-csuchico.json',
                'format': 'json',
            },
            'cusd': {
                'filename': 'schools-cusd.json',
                'format': 'json',
            },
            'dusd': {
                'filename': 'schools-dusd.json',
                'format': 'json',
            },
            'inspire': {
                'filename': 'schools-inspire.json',
                'format': 'json',
            },
            'ocesd': {
                'filename': 'schools-ocesd.json',
                'format': 'json',
            },
            'ouhsd': {
                'filename': 'schools-ouhsd.json',
                'format': 'json',
            },
            'puesd': {
                'filename': 'schools-puesd.json',
                'format': 'json',
            },
            'pusd': {
                'filename': 'schools-pusd.json',
                'format': 'json',
            },
        },
        'district_key_map': {
            'csuchico': 'Chico State',
            'cusd': 'Chico Unified School District',
            'dusd': 'Durham Unified School District',
            'inspire': 'Inspire School',
            'ocesd': 'Oroville City Elementary School District',
            'ouhsd': 'Oroville Union High School District',
            'puesd': 'Palermo Union Elementary School District',
            'pusd': 'Paradise Unified School District',
        },
    },
]
