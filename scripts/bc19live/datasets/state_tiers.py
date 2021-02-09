import json
from datetime import datetime

from bc19live.tableau import TableauLoader
from bc19live.utils import add_or_update_json_date_row, convert_json_to_csv


def build_dataset(session, response, out_filename, **kwargs):
    """Parse the state tiers dashboard and build a JSON file.

    This parses the Tableau dashboard containing information on Butte County's
    tier status, and generates JSON data that can be consumed to track which
    tier we're in and what the numbers look like.

    Args:
        session (requests.Session):
            The HTTP request session, for cookie management.

        response (requests.Respone):
            The HTTP response containing the initial dashboard page.

        out_filename (str):
            The filename for the JSON file to write.

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
    tableau_loader = TableauLoader(session=session,
                                   owner='Planforreducingcovid-19',
                                   sheet='Plan for reducing covid-19',
                                   orig_response=response)
    tableau_loader.bootstrap({
        'showParams': json.dumps({
            'unknownParams': 'County=Butte',
        }),
        'stickySessionKey': json.dumps({
            'workbookId': 6582582,
        }),
    })

    data = tableau_loader.get_mapped_col_data({
        'Map': {
            'AGG(Avg Cases per Day per 100K)': {
                'data_type': 'real',
                'result_key': 'cases_per_100k',
                'value_index': 0,
                'normalize': lambda value: round(value, 2),
            },
            'AGG(Adj Avg Case Rate per Day per 100K)': {
                'data_type': 'real',
                'result_key': 'adjusted_cases_per_100k',
                'value_index': 0,
                'normalize': lambda value: round(value, 2),
            },
            'AGG(Test Positivity Rate)': {
                'data_type': 'real',
                'result_key': 'pos_rate',
                'value_index': 0,
                'normalize': lambda value: round(value, 5),
            },
            'Current tier': {
                'data_type': 'integer',
                'result_key': 'status',
                'value_index': 0,
            },
            'Effective date': {
                'data_type': 'cstring',
                'result_key': 'effective_date',
                'value_index': 0,
                'normalize': lambda date_str: (
                    datetime
                    .strptime(date_str, '(as of %m/%d/%y)')
                    .strftime('%Y-%m-%d')
                ),
            },
        },
    })
    data['date'] = tableau_loader.get_last_update_date().strftime('%Y-%m-%d')

    add_or_update_json_date_row(out_filename, data)


DATASETS = [
    {
        'filename': 'state-tiers.json',
        'format': 'json',
        'url': (
            'https://public.tableau.com/views/Planforreducingcovid-19/'
            'planforreducingcovid-19/?%3AshowVizHome=no&County=Butte'
        ),
        'parser': build_dataset,
    },
    {
        'filename': 'state-tiers-v2.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'state-tiers.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Effective Date', ('effective_date',)),
            ('Status', ('status',)),
            ('New Case Rate', ('cases_per_100k',)),
            ('Adjusted New Case Rate', ('adjusted_cases_per_100k',)),
            ('Positivity Rate', ('pos_rate',)),
        ],
    },
]
