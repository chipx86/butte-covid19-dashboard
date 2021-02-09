import json
from datetime import datetime

from bc19live.tableau import TableauLoader
from bc19live.utils import add_or_update_json_date_row, convert_json_to_csv


def build_dataset(session, response, out_filename, **kwargs):
    """Parse the state resources dashboard and build a JSON file.

    Note:
        This is currently defunct, as this dashboard has been removed.

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
    # Set up the session and fetch the initial payloads.
    tableau_loader = TableauLoader(session=session,
                                   owner='COVID-19CountyProfile3',
                                   sheet='County Level Combined',
                                   orig_response=response)
    tableau_loader.bootstrap({
        'showParams': json.dumps({
            'unknownParams': 'County=Butte',
        }),
        'stickySessionKey': json.dumps({
            'workbookId': 6139600,
        }),
    })

    # NOTE: Ideally we'd look this up from "Last Updated Date", but I'm still
    #       unsure how these map into a dataValues with a negative
    #       aliasIndices. So while this isn't correct, it's sort of what
    #       we've got right now.
    data_dicts = tableau_loader.get_data_dicts()
    last_updated = datetime.strptime(
        sorted(data_dicts['datetime'])[-1],
        '%Y-%m-%d %H:%M:%S')

    if last_updated > datetime.now():
        # This isn't today's date. Skip it.
        return False

    data = tableau_loader.get_mapped_col_data({
        'Face Shields Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'face_shields',
                'value_index': 0,
            },
        },
        'Gloves Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'gloves',
                'value_index': 0,
            },
        },
        'Gowns Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'gowns',
                'value_index': 0,
            },
        },
        'ICU Beds Available BAN': {
            'AGG(ICU Availability)': {
                'data_type': 'real',
                'normalize': lambda value: int(round(value, 2) * 100),
                'result_key': 'icu_beds_pct',
                'value_index': 0,
            },
        },
        'N95 Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'n95_respirators',
                'value_index': 0,
            },
        },
        'Proc Masks Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'procedure_masks',
                'value_index': 0,
            },
        },
        'Sheet 42': {
            'SUM(Bed Reporting (Fixed))': {
                'data_type': 'integer',
                'result_key': 'beds',
                'value_index': 0,
            },
        },
        'Ventilators Available %': {
            'AGG(Ventilators Available %)': {
                'data_type': 'real',
                'normalize': lambda value: int(round(value, 2) * 100),
                'result_key': 'ventilators_pct',
                'value_index': 0,
            },
        },
    })
    data['date'] = last_updated.strftime('%Y-%m-%d')

    add_or_update_json_date_row(out_filename, data)


DATASETS = [
    {
        'filename': 'state-resources.json',
        'format': 'json',
        'url': (
            'https://public.tableau.com/views/COVID-19CountyProfile3/'
            'CountyLevelCombined?%3AshowVizHome=no&County=Butte'
        ),
        'parser': build_dataset,
    },
    {
        'filename': 'state-resources.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'state-resources.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Beds', ('beds',)),
            ('Face Shields', ('face_shields',)),
            ('Gloves', ('gloves',)),
            ('Gowns', ('gowns',)),
            ('N95 Respirators', ('n95_respirators',)),
            ('Procedure Masks', ('procedure_masks',)),
            ('ICU Beds Percent', ('icu_beds_pct',)),
            ('Ventilators Percent', ('ventilators_pct',)),
        ],
    },
]
