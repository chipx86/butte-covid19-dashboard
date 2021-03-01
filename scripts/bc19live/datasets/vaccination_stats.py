import json
from datetime import datetime

from bc19live.utils import add_or_update_json_date_row


def build_dataset(session, responses, out_filename, **kwargs):
    """Build JSON data for vaccination stats.

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
        'filename': 'vaccination-stats.json',
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
        'parser': build_dataset,
    },
]
