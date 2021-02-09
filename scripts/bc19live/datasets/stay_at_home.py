import json
from datetime import datetime

from bc19live.tableau import TableauLoader
from bc19live.utils import add_or_update_json_date_row, slugify


def build_dataset(session, response, out_filename, **kwargs):
    """Build JSON data for the California Stay-at-Home dashboard.

    This parses the Tableau Stay-At-Home Order dashboard, collecting
    information on each region, their Stay-at-Home active state, case rates,
    positivity rates, effective dates, and bed availability.

    It also collects general state-wide states, as shown in the dashboard,
    for posterity.

    Args:
        session (requests.Session):
            The HTTP request session, for cookie management.

        response (requests.Response):
            The HTTP response from the initial dashboard page.

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
    def _parse_effective_date(date_str):
        if not date_str:
            return None

        return (
            datetime.strptime(date_str, '%m/%d/%Y %H:%M %p')
            .strftime('%Y-%m-%d')
        )

    tableau_loader = TableauLoader(
        session=session,
        owner='COVID-19Planforreducingcovid-19wregionsmap',
        sheet='regionalmap',
        orig_response=response)

    tableau_loader.bootstrap({
        'stickySessionKey': json.dumps({
            'workbookId': 7014571,
        }),
    })

    data = tableau_loader.get_mapped_col_data({
        '% CA Population County Tiers': {
            'Current tier': {
                'data_type': 'integer',
                'result_key': 'pct_tiers_types',
            },
            'SUM(Population)': {
                'data_type': 'real',
                'result_key': 'pct_tiers_population',
                'normalize': lambda value: value * 100,
            },
        },
        '% CA Population SHO': {
            'Regional Stay At Home Order': {
                'data_type': 'integer',
                'result_key': 'pct_sho_active',
                'normalize': lambda value: value.strip().lower() == 'yes',
            },
            'SUM(Population)': {
                'data_type': 'real',
                'result_key': 'pct_sho_population',
                'normalize': lambda value: value * 100,
            },
        },
        'Last Updated Regional SHO': {
            'Sf Load Timestamp': {
                'data_type': 'datetime',
                'result_key': 'date',
                'value_index': 0,
                'normalize': lambda date_str: (
                    datetime.strptime(date_str, '%m/%d/%Y')
                ),
            },
        },
        'Regions Map': {
            'AGG(Avg Cases per Day per 100K)': {
                'data_type': 'real',
                'result_key': 'case_rate',
            },
            'AGG(Adj Avg Case Rate per Day per 100K)': {
                'data_type': 'real',
                'result_key': 'adjusted_case_rate',

                # Not 100% sure this is right, but it does seem to be 10x
                # the unadjusted rate.
                'normalize': lambda value: value / 10,
            },
            'AGG(Test Positivity Rate)': {
                'data_type': 'real',
                'result_key': 'test_pos_rate',
                'normalize': lambda value: value * 100,
            },
            'ATTR(Stay At Home Date Effective)': {
                'data_type': 'datetime',
                'result_key': 'stay_at_home_date',
                'normalize': _parse_effective_date,
            },
            'Region': {
                'data_type': 'cstring',
                'result_key': 'region_names',
            },
            'Regional Stay At Home Order': {
                'data_type': 'integer',
                'result_key': 'in_stay_at_home',
                'normalize': lambda value: value.strip().lower() == 'yes',
            },
            'SUM(Saho Icu Pct Avail)': {
                'data_type': 'real',
                'result_key': 'icu_beds_available_pct',
            },
        },
        'Percent of Population SHO': {
            'AGG(Counties)': {
                'data_type': 'integer',
                'result_key': 'pct_pop_num_counties',
            },
            'AGG(Regions)': {
                'data_type': 'integer',
                'result_key': 'pct_pop_num_regions',
            },
            'Regional Stay At Home Order': {
                'data_type': 'integer',
                'result_key': 'pct_pop_sho_active',
                'normalize': lambda value: value.strip().lower() == 'yes',
            },
            'SUM(Population)': {
                'data_type': 'integer',
                'result_key': 'pct_pop_sho_pop',
                'require_attrs': {
                    'isAutoSelect': True,
                },
                'normalize': lambda value: value * 100,
            },
        }
    })

    date = data['date']

    if date > datetime.now():
        # This isn't today's date. Skip it.
        return False

    case_rate = data['case_rate']
    adjusted_case_rate = data['adjusted_case_rate']
    in_stay_at_home = data['in_stay_at_home']
    stay_at_home_date = data['stay_at_home_date']
    icu_beds_available_pct = data['icu_beds_available_pct']
    test_pos_rate = data['test_pos_rate']

    pct_pop_sho_pop = dict(zip(data['pct_pop_sho_active'],
                               data['pct_pop_sho_pop']))
    pct_pop_num_counties = dict(zip(data['pct_pop_sho_active'],
                                    data['pct_pop_num_counties']))
    pct_pop_num_regions = dict(zip(data['pct_pop_sho_active'],
                                   data['pct_pop_num_regions']))
    pct_pop_sho_pop_pct = dict(zip(data['pct_sho_active'],
                                   data['pct_sho_population']))
    tiers_pop = dict(zip(data['pct_tiers_types'],
                         data['pct_tiers_population']))

    result = {
        'date': date.strftime('%Y-%m-%d'),
        'stats': {
            'stay_home_order': {
                key: {
                    'num_counties': pct_pop_num_counties[active],
                    'num_regions': pct_pop_num_regions[active],
                    'population': pct_pop_sho_pop[active],
                    'population_pct': pct_pop_sho_pop_pct[active],
                }
                for key, active in (('active', True),
                                    ('inactive', False))
            },
            'tiers': {
                tier.lower(): {
                    'population_pct': population_pct,
                }
                for tier, population_pct in tiers_pop.items()
            },
        },
        'regions': {
            slugify(region): {
                'adjusted_case_rate': adjusted_case_rate[i],
                'case_rate': case_rate[i],
                'icu_beds_available_pct': icu_beds_available_pct[i],
                'stay_at_home_active': in_stay_at_home[i],
                'stay_at_home_date': stay_at_home_date[i],
                'test_pos_rate': test_pos_rate[i],
            }
            for i, region in enumerate(data['region_names'])
        },
    }

    add_or_update_json_date_row(out_filename, result)


DATASETS = [
    {
        'filename': 'stay-at-home.json',
        'format': 'json',
        'url': (
            'https://public.tableau.com/views/'
            'COVID-19Planforreducingcovid-19wregionsmap/'
            'regionalmap/?%3AshowVizHome=no'
        ),
        'parser': build_dataset,
    },
]
