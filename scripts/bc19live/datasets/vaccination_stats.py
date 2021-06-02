import json
from datetime import datetime

from bc19live.utils import (add_or_update_json_date_row,
                            convert_json_to_csv)


def build_demographic_stats_json_dataset(session, responses, out_filename,
                                         **kwargs):
    """Build JSON data for vaccination demographic stats.

    This parses the datasets that make up https://covid19.ca.gov/vaccines/
    and creates a dataset with all stats for Butte County.

    Args:
        session (requests.Session):
            The HTTP request session, for cookie management.

        responses (dict):
            A mapping of keys to HTTP responses.

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
    def _gen_data(key):
        return {
            row['CATEGORY']: row['METRIC_VALUE']
            for row in payloads[key]['data']
        }

    payloads = {}
    cur_date = None

    for key, response in responses.items():
        payload = json.loads(response.text)
        date = datetime.strptime(payload['meta']['LATEST_ADMIN_DATE'],
                                 '%Y-%m-%d')

        if (date > datetime.now() or
            (cur_date is not None and cur_date != date)):
            # This isn't today's date, or there's an inconsistency. Skip it.
            return False

        payloads[key] = payload
        cur_date = date

    add_or_update_json_date_row(out_filename, {
        'date': cur_date.strftime('%Y-%m-%d'),
        'age': _gen_data('age'),
        'ethnicity': _gen_data('ethnicity'),
        'genders': _gen_data('gender'),
    })

    return True


DATASETS = [
    {
        'filename': 'chhs-vaccinations-administered.csv',
        'format': 'csv',
        'url': (
            'https://data.chhs.ca.gov/dataset/'
            'e283ee5a-cf18-4f20-a92c-ee94a2866ccd/resource/'
            '130d7ba2-b6eb-438d-a412-741bde207e1c/download/'
            'covid19vaccinesbycounty.csv'
        ),
        'csv': {
            'match_row': lambda row: row['county'] == 'Butte',
            'sort_by': 'date',
            'columns': [
                {
                    'name': 'date',
                    'source_column': 'administered_date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {'name': 'total_doses'},
                {'name': 'cumulative_total_doses'},
                {'name': 'pfizer_doses'},
                {'name': 'cumulative_pfizer_doses'},
                {'name': 'moderna_doses'},
                {'name': 'cumulative_moderna_doses'},
                {'name': 'jj_doses'},
                {'name': 'cumulative_jj_doses'},
                {'name': 'partially_vaccinated'},
                {'name': 'total_partially_vaccinated'},
                {'name': 'fully_vaccinated'},
                {'name': 'cumulative_fully_vaccinated'},
                {'name': 'at_least_one_dose'},
                {'name': 'cumulative_at_least_one_dose'},
            ],
        },
    },
    {
        'filename': 'vaccination-demographics.json',
        'format': 'json',
        'urls': {
            'age': (
                'https://files.covid19.ca.gov/data/vaccine-equity/age/'
                'vaccines_by_age_butte.json'
            ),
            'ethnicity': (
                'https://files.covid19.ca.gov/data/vaccine-equity/'
                'race-ethnicity/vaccines_by_race_ethnicity_butte.json'
            ),
            'gender': (
                'https://files.covid19.ca.gov/data/vaccine-equity/gender/'
                'vaccines_by_gender_butte.json'
            ),
        },
        'parser': build_demographic_stats_json_dataset,
    },
    {
        'filename': 'vaccination-demographics-v2.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'vaccination-demographics.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Gender: Female', ('genders', 'Female')),
            ('Gender: Male', ('genders', 'Male')),
            ('Gender: Unknown/Undifferentiated',
             ('genders', 'Unknown/undifferentiated')),
            ('Age: 0-11', ('age', '0-11')),
            ('Age: 12-17', ('age', '12-17')),
            ('Age: 18-49', ('age', '18-49')),
            ('Age: 50-64', ('age', '50-64')),
            ('Age: 65+', ('age', '65+')),
            ('Age: Unknown', ('age', 'Unknown')),
            ('Ethnicity: American Indian/Alaska Native',
             ('ethnicity', 'American Indian or Alaska Native (AI/AN)')),
            ('Ethnicity: Asian American', ('ethnicity', 'Asian American')),
            ('Ethnicity: Black', ('ethnicity', 'Black')),
            ('Ethnicity: Latino', ('ethnicity', 'Latino')),
            ('Ethnicity: Multi-race', ('ethnicity', 'Multi-race')),
            ('Ethnicity: Native Hawaiian or Other Pacific Islander',
             ('ethnicity', 'Native Hawaiian or Other Pacific Islander (NHPI)')),
            ('Ethnicity: White', ('ethnicity', 'White')),
            ('Ethnicity: Other', ('ethnicity', 'Other')),
            ('Ethnicity: Unknown', ('ethnicity', 'Unknown')),
        ],
    },
]
