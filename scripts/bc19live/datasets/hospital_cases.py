import json
from datetime import datetime

from bc19live.errors import ParseError
from bc19live.tableau import TableauLoader
from bc19live.utils import add_or_update_json_date_row, convert_json_to_csv


def build_dataset(session, response, out_filename, **kwargs):
    """Parse the state hospitals dashboard and build a JSON file.

    This parses the Tableau dashboard containing information on Butte County's
    hospital status, which includes all patients (regardless of county of
    residency), along with the ICU numbers.

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
    def _get_col_data(label, total_pres_model_name, total_field_caption,
                      total_result_key='total', include_date=False,
                      expected_date=None):
        data = tableau_loader.get_mapped_col_data({
            total_pres_model_name: {
                total_field_caption: {
                    'data_type': 'integer',
                    'result_key': 'total',
                    'value_index': 0,
                },
            },
            'Map Patients': {
                'Hospital Name': {
                    'data_type': 'cstring',
                    'result_key': 'hospital_names',
                    'normalize': lambda name: hospital_keys.get(name, name),
                },
                'AGG(Selector KPI)': {
                    'data_type': 'integer',
                    'result_key': 'counts',
                },
            },
            'Updated on': {
                'MDY(MAX_AS_OF_DATE)': {
                    'data_type': 'integer',
                    'result_key': 'date',
                    'value_index': 0,
                },
            },
        })

        if expected_date is not None and data['date'] != expected_date:
            raise ParseError('Date for hospitalizations data changed during '
                             'data import. Try again.')

        hospital_names = data['hospital_names']
        counts = data['counts']

        if len(hospital_names) != len(counts):
            raise ParseError('Number of hospital names (%s) does not match '
                             'number of case counts (%s) for %s.'
                             % (len(hospital_names), len(counts), label))

        col_data = dict({
            total_result_key: data['total'],
        }, **dict(zip(hospital_names, counts)))

        if include_date:
            col_data['date'] = data['date']

        return col_data

    hospital_keys = {
        'Enloe Medical Center - Esplanade': 'enloe_hospital',
        'Oroville Hospital': 'oroville_hospital',
        'Orchard Hospital': 'orchard_hospital',
    }

    tableau_loader = TableauLoader(session=session,
                                   owner='COVID-19PublicDashboard',
                                   sheet='Covid-19 Hospitals',
                                   orig_response=response)
    tableau_loader.bootstrap({
        'showParams': json.dumps({
            'unknownParams': 'COUNTY=Butte',
        }),
        'stickySessionKey': json.dumps({
            'workbookId': 5911876,
        }),
    })

    result = {}

    # Load the patients view.
    patients_data = _get_col_data(
        label='positive patients',
        total_pres_model_name='Positive Patients',
        total_field_caption='SUM(Hospitalized Covid Confirmed Patients)',
        total_result_key='total_patients',
        include_date=True)

    date_raw = patients_data['date']
    date = datetime.strptime(date_raw, '%B %d, %Y')

    if date > datetime.now():
        # This isn't today's date. Skip it.
        return False

    result.update(patients_data)
    result['date'] = date.strftime('%Y-%m-%d')

    # Now load in information from the Suspected Patients view.
    tableau_loader.set_parameter_value(
        '[Parameters].[Select Measure (copy)_1581607928766861312]',
        'Suspected Patients')

    result['suspected_patients'] = _get_col_data(
        label='suspected patients',
        total_pres_model_name='Suspected Patients',
        total_field_caption='SUM(Hospitalized Suspected Covid Patients)',
        expected_date=date_raw)

    # Now load in information from the ICU Available Beds view.
    tableau_loader.set_parameter_value(
        '[Parameters].[Select Measure (copy)_1581607928766861312]',
        'ICU Available Beds')

    result['icu_beds_available'] = _get_col_data(
        label='available ICU beds',
        total_pres_model_name='ICU Available Beds',
        total_field_caption='SUM(Icu Available Beds)',
        expected_date=date_raw)

    # Now load in information from the ICU Positive Patients view.
    tableau_loader.set_parameter_value(
        '[Parameters].[Select Measure (copy)_1581607928766861312]',
        'ICU Positive Patients')

    result['icu_patients'] = _get_col_data(
        label='ICU patients',
        total_pres_model_name='ICU Positive Census',
        total_field_caption='SUM(Icu Covid Confirmed Patients)',
        expected_date=date_raw)

    # Now load in information from the ICU Suspected Patients view.
    #
    # XXX These are gone. Noticed August 24, 2023.
#    tableau_loader.set_parameter_value(
#        '[Parameters].[Select Measure (copy)_1581607928766861312]',
#        'ICU Suspected Patients')
#
#    result['icu_suspected_patients'] = _get_col_data(
#        label='ICU suspected patients',
#        total_pres_model_name='ICU Suspected Census',
#        total_field_caption='SUM(ICu Suspected Covid Patients)',
#        expected_date=date_raw)
    #result['icu_suspected_patients'] = {}

    add_or_update_json_date_row(out_filename, result)


DATASETS = [
    {
        'filename': 'hospital-cases.json',
        'format': 'json',
        'url': (
            'https://public.tableau.com/views/COVID-19HospitalsDashboard/'
            'Hospitals?&:showVizHome=no'
        ),
        'parser': build_dataset,
    },
    {
        'filename': 'hospital-cases.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'hospital-cases.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Patients: Enloe Hospital', ('enloe_hospital',)),
            ('Patients: Oroville Hospital', ('oroville_hospital',)),
            ('Patients: Orchard Hospital', ('orchard_hospital',)),
            ('Patients: Total', ('total_patients',)),
        ] + [
            ('%s: %s' % (_prefix, _hospital), (_type_key, _hospital_key))
            for _prefix, _type_key in (('Suspected', 'suspected_patients'),
                                       ('In ICU', 'icu_patients'),
                                       ('Suspected in ICU',
                                        'icu_suspected_patients'),
                                       ('Available ICU Beds',
                                        'icu_beds_available'))
            for _hospital, _hospital_key in (('Enloe Hospital',
                                              'enloe_hospital'),
                                             ('Oroville Hospital',
                                              'oroville_hospital'),
                                             ('Orchard Hospital',
                                              'orchard_hospital'),
                                             ('Total', 'total'))
        ],
    },
]
