import codecs
import csv
import itertools
import json
from datetime import datetime

from bc19live.utils import (add_or_update_json_date_row,
                            build_missing_date_rows,
                            convert_json_to_csv,
                            parse_real,
                            safe_open_for_write)


STATE_START_DATE = datetime(year=2020, month=7, day=29)


def build_demographic_stats_json_dataset(session, response, out_filename,
                                         **kwargs):
    """Build JSON data for vaccination demographic stats.

    This parses the vaccination stats dataset and creates a dataset with
    all stats for Butte County.

    Args:
        session (requests.Session):
            The HTTP request session, for cookie management.

        response (requests.Respone):
            The HTTP response containing the CSV file.

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
    def _int_or_none(value):
        if value == 'None':
            return value

        return parse_real(value)

    lines = response.iter_lines()
    reader = csv.DictReader(codecs.iterdecode(lines, 'utf-8'),
                            delimiter=',')
    cur_date = None
    dates = {}

    category_map = {
        'Age Group': 'age',
        'Race/Ethnicity': 'ethnicity',
        'VEM Quartile': 'vem_quartiles',
    }

    for row in reader:
        if row['county'] != 'Butte':
            continue

        category_key = category_map.get(row['demographic_category'])

        if not category_key:
            continue

        date = row['administered_date']

        if datetime.strptime(date, '%Y-%m-%d') < STATE_START_DATE:
            continue

        demographic = row['demographic_value']

        info = dates.setdefault(date, {
            'age': {},
            'date': date,
            'ethnicity': {},
            'vem_quartiles': {},
        })

        payload = {
            'population': {
                'total': _int_or_none(row['est_population']),
            },
            'vaccinated': {
                'new_partial': _int_or_none(row['partially_vaccinated']),
                'total_partial':
                    _int_or_none(row['total_partially_vaccinated']),
                'new_full': _int_or_none(row['fully_vaccinated']),
                'total_full':
                    _int_or_none(row['cumulative_fully_vaccinated']),
                'total_one_plus_dose':
                    _int_or_none(row['cumulative_at_least_one_dose']),
            },
            'unvaccinated': {
                'total': _int_or_none(row['cumulative_unvax_total_pop']),
            },
        }

        if category_key != 'age':
            payload['population'].update({
                'total_age_12_plus': _int_or_none(row['est_age_12plus_pop']),
                'total_age_5_plus': _int_or_none(row['est_age_5plus_pop']),
            })

            payload['unvaccinated'].update({
                'total_age_12_plus':
                    _int_or_none(row['cumulative_unvax_12plus_pop']),
                'total_age_5_plus':
                    _int_or_none(row['cumulative_unvax_5plus_pop']),
            })

        payload = info[category_key][demographic] = payload

    # Add missing dates, since that's common with the vaccination stats.
    sorted_rows = (
        _info
        for _date, _info in sorted(dates.items(),
                                   key=lambda pair: pair[0])
    )
    results = []

    prev_date = None

    for row in sorted_rows:
        date = datetime.strptime(row['date'], '%Y-%m-%d')

        if prev_date is not None:
            results += build_missing_date_rows(cur_date=date,
                                               latest_date=prev_date)

        results.append(row)
        prev_date = date

    # Write the result.
    with safe_open_for_write(out_filename) as fp:
        json.dump(results,
                  fp,
                  sort_keys=True,
                  indent=2)

    return True


DATASETS = [
    {
        'filename': 'chhs-vaccinations-administered.csv',
        'format': 'csv',
        'url': (
            'https://data.chhs.ca.gov/dataset/e283ee5a-cf18-4f20-a92c-ee94a2866ccd/resource/130d7ba2-b6eb-438d-a412-741bde207e1c/download/covid19vaccinesbycounty.csv'
        ),
        'csv': {
            'match_row': lambda row: (
                row['county'] == 'Butte' and
                (datetime.strptime(row['administered_date'], '%Y-%m-%d') >=
                 STATE_START_DATE)
            ),
            'validator': lambda results: (
                len(results) > 0 and
                results[0]['date'] == STATE_START_DATE.strftime('%Y-%m-%d')
            ),
            'sort_by': 'date',
            'add_missing_dates': True,
            'columns': [
                {
                    'name': 'date',
                    'source_column': 'administered_date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {'name': 'total_doses'},
                {'name': 'cumulative_total_doses'},
                {
                    'name': 'pfizer_doses',
                    'default': 0,
                },
                {
                    'name': 'cumulative_pfizer_doses',
                    'default': 0,
                },
                {
                    'name': 'moderna_doses',
                    'default': 0,
                },
                {
                    'name': 'cumulative_moderna_doses',
                    'default': 0,
                },
                {
                    'name': 'jj_doses',
                    'default': 0,
                },
                {
                    'name': 'cumulative_jj_doses',
                    'default': 0,
                },
                {'name': 'partially_vaccinated'},
                {'name': 'total_partially_vaccinated'},
                {'name': 'fully_vaccinated'},
                {'name': 'cumulative_fully_vaccinated'},
                {'name': 'at_least_one_dose'},
                {'name': 'cumulative_at_least_one_dose'},
                {
                    'name': 'booster_recip_count',
                    'default': 0,
                },
                {
                    'name': 'cumulative_booster_recip_count',
                    'default': 0,
                },
            ],
        },
    },
    {
        'filename': 'vaccination-demographics-v3.json',
        'format': 'json',
        'url': 'https://data.chhs.ca.gov/dataset/e283ee5a-cf18-4f20-a92c-ee94a2866ccd/resource/71729331-2f09-4ea4-a52f-a2661972e146/download/covid19vaccinesbycountybydemographic.csv',
        'parser': build_demographic_stats_json_dataset,
    },
    {
        'filename': 'vaccination-demographics-ages.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'vaccination-demographics-v3.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
        ] + list(itertools.chain.from_iterable(
            [
                ('%s - Population' % age,
                 ('age', age, 'population', 'total')),
                ('%s - Unvaccinated' % age,
                 ('age', age, 'unvaccinated', 'total')),
                ('%s - Vaccinated - Total (Partial)' % age,
                 ('age', age, 'vaccinated', 'total_partial')),
                ('%s - Vaccinated - Total (Full)' % age,
                 ('age', age, 'vaccinated', 'total_full')),
                ('%s - Vaccinated - Total (1+ Doses)' % age,
                 ('age', age, 'vaccinated', 'total_one_plus_dose')),
                ('%s - Vaccinated - New (Partial)' % age,
                 ('age', age, 'vaccinated', 'new_partial')),
                ('%s - Vaccinated - New (Full)' % age,
                 ('age', age, 'vaccinated', 'new_full')),
            ]
            for age in ('Under 5', '5-11', '12-17', '18-49', '50-64', '65+')
        )),
    },
    {
        'filename': 'vaccination-demographics-ethnicity.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'vaccination-demographics-v3.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
        ] + list(itertools.chain.from_iterable(
            [
                ('%s - Population' % ethnicity,
                 ('ethnicity', ethnicity, 'population', 'total')),
                ('%s - Unvaccinated' % ethnicity,
                 ('ethnicity', ethnicity, 'unvaccinated', 'total')),
                ('%s - Vaccinated - Total (Partial)' % ethnicity,
                 ('ethnicity', ethnicity, 'vaccinated', 'total_partial')),
                ('%s - Vaccinated - Total (Full)' % ethnicity,
                 ('ethnicity', ethnicity, 'vaccinated', 'total_full')),
                ('%s - Vaccinated - Total (1+ Doses)' % ethnicity,
                 ('ethnicity', ethnicity, 'vaccinated',
                  'total_one_plus_dose')),
                ('%s - Vaccinated - New (Partial)' % ethnicity,
                 ('ethnicity', ethnicity, 'vaccinated', 'new_partial')),
                ('%s - Vaccinated - New (Full)' % ethnicity,
                 ('ethnicity', ethnicity, 'vaccinated', 'new_full')),
            ]
            for ethnicity in (
                'White',
                'Latino',
                'Asian',
                'Black or African American',
                'American Indian or Alaska Native',
                'Native Hawaiian or Other Pacific Islander',
                'Multiracial',
                'Other Race',
                'Unknown',
            )
        )),
    },
    {
        'filename': 'vaccination-demographics-vem-quartiles.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'vaccination-demographics-v3.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
        ] + list(itertools.chain.from_iterable(
            [
                ('%s - Population' % quartile,
                 ('vem_quartiles', quartile, 'population', 'total')),
                ('%s - Unvaccinated' % quartile,
                 ('vem_quartiles', quartile, 'unvaccinated', 'total')),
                ('%s - Vaccinated - Total (Partial)' % quartile,
                 ('vem_quartiles', quartile, 'vaccinated', 'total_partial')),
                ('%s - Vaccinated - Total (Full)' % quartile,
                 ('vem_quartiles', quartile, 'vaccinated', 'total_full')),
                ('%s - Vaccinated - Total (1+ Doses)' % quartile,
                 ('vem_quartiles', quartile, 'vaccinated',
                  'total_one_plus_dose')),
                ('%s - Vaccinated - New (Partial)' % quartile,
                 ('vem_quartiles', quartile, 'vaccinated', 'new_partial')),
                ('%s - Vaccinated - New (Full)' % quartile,
                 ('vem_quartiles', quartile, 'vaccinated', 'new_full')),
            ]
            for quartile in ('1', '2', '3', '4')
        )),
    },
]
