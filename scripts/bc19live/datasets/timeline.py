import csv
import json
import os
import sys
from datetime import datetime, timedelta

from bc19live.utils import add_nested_key, safe_open_for_write


def build_dataset(info, in_fp, out_filename, **kwargs):
    """Parse the Google Sheets CSV export and build JSON data.

    This takes all the consolidated information from the main "Timeline Data"
    sheet in Google Sheets and generates a new JSON file used by the
    ```bc19_dashboard`` dataset for the https://bc19.live dashboard.

    Each header in the Google Sheets CSV file is expected to be a
    ``.``-delimited nested key path, which will be used when setting the
    appropriate key in the JSON file.

    Both a ``.json`` and a ``.min.json`` will be generated. The ``.min.json``
    is deprecated.

    Args:
        info (dict):
            Parser option information. This must define ``min_filename``.

        in_fp (file):
            A file pointer to the CSV file being read.

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
    timeline = []
    reader = csv.DictReader(in_fp, delimiter=',')

    for row in reader:
        date_info = {}
        timeline.append(date_info)

        for col_name, col_data in row.items():
            if col_name != 'row_id':
                if col_data == '':
                    col_data = None
                else:
                    try:
                        col_data = int(col_data)
                    except ValueError:
                        try:
                            col_data = float(col_data)
                        except ValueError:
                            pass

                add_nested_key(date_info, col_name, col_data)

    # We've hit issues where we've encountered empty data for the last few
    # days when pulling from the spreadsheet. That should not be happening.
    # Look for this and bail if we have to.
    found_cases = False

    for row in timeline[-3:]:
        if row['confirmed_cases']['total'] is not None:
            found_cases = True
            break

    if not found_cases:
        sys.stderr.write('Got an empty timeline dataset! Not writing.')
        return False

    payload = {
        'dates': timeline,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    with safe_open_for_write(out_filename) as fp:
        json.dump(payload,
                  fp,
                  sort_keys=True,
                  indent=2)

    min_filename = os.path.join(os.path.dirname(out_filename),
                                info['min_filename'])

    with safe_open_for_write(min_filename) as fp:
        json.dump(payload,
                  fp,
                  sort_keys=True,
                  separators=(',', ':'))

    return True


_report_data_date_str = (datetime.now() -
                         timedelta(days=1)).strftime('%Y-%m-%d')

DATASETS = [
    {
        'filename': 'timeline.csv',
        'format': 'csv',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRwJpCeZj4tsxMXqrHFDjIis5Znv-nI0kQk9enEAJAbYzZUBHm7TELQe0wl2huOYEkdaWLyR8N9k_uq/pub?gid=169564738&single=true&output=csv&_=%s' % datetime.timestamp(datetime.now()),
        'csv': {
            'end_if': lambda row: (
                row['confirmed_cases:total'] == '' and
                row['county_jail:inmates:population'] == ''
            ),
            'validators': [
                lambda results: (
                    len(results) > 0,
                    'No results found',
                ),
                lambda results: (
                    results[0]['date'] == '2020-03-20',
                    ('Start date was not 2020-03-20 (found %s)'
                     % results[0]['date']),
                ),
                lambda results: (
                    _report_data_date_str in (results[-1]['date'],
                                              results[-2]['date']),
                    ('Latest report data date (%s) not found in last two '
                     'rows (%s, %s)'
                     % (_report_data_date_str,
                        results[-1]['date'],
                        results[-2]['date'])),
                ),
                lambda results: (
                    results[-1]['confirmed_cases:total'] != '' or
                    results[-2]['confirmed_cases:total'] != '' or
                    results[-3]['confirmed_cases:total'] != '',
                    'Confirmed cases missing in last 3 rows',
                ),
                lambda results: (
                    results[-1]['deaths:total'] != '' or
                    results[-2]['deaths:total'] != '' or
                    results[-3]['deaths:total'] != '',
                    'Total deaths missing in last 3 rows',
                ),
            ],
            'skip_rows': 4,
            'default_type': 'int_or_blank',
            'columns': [
                {
                    'name': 'date',
                    'type': 'date',
                    'format': '%a, %b %d, %Y',
                },
                {'name': 'confirmed_cases:total_as_of_report'},
                {'name': 'confirmed_cases:total'},
                {
                    'name': 'confirmed_cases:delta_total',
                    'type': 'delta',
                    'delta_from': 'confirmed_cases:total',
                },
                {'name': 'in_isolation:current'},
                {
                    'name': 'in_isolation:delta_current',
                    'type': 'delta',
                    'delta_from': 'in_isolation:current',
                },
                {'name': 'in_isolation:total_released'},
                {
                    'name': 'in_isolation:delta_total_released',
                    'type': 'delta',
                    'delta_from': 'in_isolation:total_released',
                },
                {'name': 'deaths:total_as_of_report'},
                {'name': 'deaths:total'},
                {
                    'name': 'deaths:delta_total',
                    'type': 'delta',
                    'delta_from': 'deaths:total',
                },
                {'name': 'deaths:age_ranges_in_years:0-4'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_0-4',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:0-4',
                },
                {'name': 'deaths:age_ranges_in_years:5-12'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_5-12',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:5-12',
                },
                {'name': 'deaths:age_ranges_in_years:13-17'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_13-17',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:13-17',
                },
                {'name': 'deaths:age_ranges_in_years:18-24'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_18-24',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:18-24',
                },
                {'name': 'deaths:age_ranges_in_years:25-34'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_25-34',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:25-34',
                },
                {'name': 'deaths:age_ranges_in_years:35-44'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_35-44',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:35-44',
                },
                {'name': 'deaths:age_ranges_in_years:45-54'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_45-54',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:45-54',
                },
                {'name': 'deaths:age_ranges_in_years:55-64'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_55-64',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:55-64',
                },
                {'name': 'deaths:age_ranges_in_years:65-74'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_65-74',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:65-74',
                },
                {'name': 'deaths:age_ranges_in_years:75_plus'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_75_plus',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:75_plus',
                },
                {'name': 'deaths:age_ranges_in_years:0-17'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_0-17',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:0-17',
                },
                {'name': 'viral_tests:total'},
                {
                    'name': 'viral_tests:delta_total',
                    'type': 'delta',
                    'delta_from': 'viral_tests:total',
                },
                {'name': 'viral_tests:results'},
                {
                    'name': 'viral_tests:delta_results',
                    'type': 'delta',
                    'delta_from': 'viral_tests:results',
                },
                {'name': 'viral_tests:positive_results'},
                {
                    'name': 'viral_tests:delta_positive_results',
                    'type': 'delta',
                    'delta_from': 'viral_tests:positive_results',
                },
                {
                    'name': 'viral_tests:pos_rate',
                    'type': 'pct',
                },
                {'name': 'viral_tests:pending'},
                {
                    'name': 'viral_tests:delta_pending',
                    'type': 'delta',
                    'delta_from': 'viral_tests:pending',
                },
                {'name': 'hospitalizations:county_data:hospitalized'},
                {'name': 'hospitalizations:state_data:positive'},
                {
                    'name': 'hospitalizations:state_data:delta_positive',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:positive',
                },
                {'name': 'hospitalizations:state_data:suspected_positive'},
                {
                    'name': 'hospitalizations:state_data:delta_suspected_positive',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:suspected_positive',
                },
                {'name': 'hospitalizations:state_data:icu_positive'},
                {
                    'name': 'hospitalizations:state_data:delta_icu_positive',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:icu_positive',
                },
                {'name': 'hospitalizations:state_data:icu_suspected'},
                {
                    'name': 'hospitalizations:state_data:delta_icu_suspected',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:icu_suspected',
                },
                {'name': 'hospitalizations:state_data:enloe_hospital'},
                {
                    'name': 'hospitalizations:state_data:delta_enloe_hospital',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:enloe_hospital',
                },
                {'name': 'hospitalizations:state_data:oroville_hospital'},
                {
                    'name': 'hospitalizations:state_data:delta_oroville_hospital',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:oroville_hospital',
                },
                {'name': 'hospitalizations:state_data:orchard_hospital'},
                {
                    'name': 'hospitalizations:state_data:delta_orchard_hospital',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:orchard_hospital',
                },
                {'name': 'regions:biggs_gridley:cases'},
                {
                    'name': 'regions:biggs_gridley:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:biggs_gridley:cases',
                },
                {'name': 'regions:chico:cases'},
                {
                    'name': 'regions:chico:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:chico:cases',
                },
                {'name': 'regions:durham:cases'},
                {
                    'name': 'regions:durham:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:durham:cases',
                },
                {'name': 'regions:gridley:cases'},
                {
                    'name': 'regions:gridley:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:gridley:cases',
                },
                {'name': 'regions:oroville:cases'},
                {
                    'name': 'regions:oroville:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:oroville:cases',
                },
                {'name': 'regions:ridge:cases'},
                {
                    'name': 'regions:ridge:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:ridge:cases',
                },
                {'name': 'regions:other:cases'},
                {
                    'name': 'regions:other:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:other:cases',
                },
                {'name': 'age_ranges_in_years:0-4'},
                {
                    'name': 'age_ranges_in_years:delta_0-4',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:0-4',
                },
                {'name': 'age_ranges_in_years:5-12'},
                {
                    'name': 'age_ranges_in_years:delta_5-12',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:5-12',
                },
                {'name': 'age_ranges_in_years:13-17'},
                {
                    'name': 'age_ranges_in_years:delta_13-17',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:13-17',
                },
                {'name': 'age_ranges_in_years:18-24'},
                {
                    'name': 'age_ranges_in_years:delta_18-24',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:18-24',
                },
                {'name': 'age_ranges_in_years:25-34'},
                {
                    'name': 'age_ranges_in_years:delta_25-34',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:25-34',
                },
                {'name': 'age_ranges_in_years:35-44'},
                {
                    'name': 'age_ranges_in_years:delta_35-44',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:35-44',
                },
                {'name': 'age_ranges_in_years:45-54'},
                {
                    'name': 'age_ranges_in_years:delta_45-54',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:45-54',
                },
                {'name': 'age_ranges_in_years:55-64'},
                {
                    'name': 'age_ranges_in_years:delta_55-64',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:55-64',
                },
                {'name': 'age_ranges_in_years:65-74'},
                {
                    'name': 'age_ranges_in_years:delta_65-74',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:65-74',
                },
                {'name': 'age_ranges_in_years:75_plus'},
                {
                    'name': 'age_ranges_in_years:delta_75_plus',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:75_plus',
                },
                {'name': 'age_ranges_in_years:0-17'},
                {
                    'name': 'age_ranges_in_years:delta_0-17',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:0-17',
                },
                {'name': 'age_ranges_in_years:18-49'},
                {
                    'name': 'age_ranges_in_years:delta_18-49',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:18-49',
                },
                {'name': 'age_ranges_in_years:50-64'},
                {
                    'name': 'age_ranges_in_years:delta_50_64',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:50-64',
                },
                {'name': 'age_ranges_in_years:65_plus'},
                {
                    'name': 'age_ranges_in_years:delta_65_plus',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:65_plus',
                },
                {
                    'name': 'resources:state_data:icu_beds_pct',
                    'type': 'pct',
                },
                {
                    'name': 'resources:state_data:ventilators_pct',
                    'type': 'pct',
                },
                {'name': 'resources:state_data:n95_respirators'},
                {'name': 'resources:state_data:procedure_masks'},
                {'name': 'resources:state_data:gowns'},
                {'name': 'resources:state_data:face_shields'},
                {'name': 'resources:state_data:gloves'},
                {
                    'name': 'note',
                    'type': 'string',
                },
                {'name': 'skilled_nursing_facilities:current_patient_cases'},
                {'name': 'skilled_nursing_facilities:current_staff_cases'},
                {'name': 'skilled_nursing_facilities:total_patient_deaths'},
                {'name': 'skilled_nursing_facilities:total_staff_deaths'},
                {'name': 'county_jail:inmates:population'},
                {
                    'name': 'county_jail:inmates:delta_population',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:population',
                },
                {'name': 'county_jail:inmates:total_tests'},
                {
                    'name': 'county_jail:inmates:delta_total_tests',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:total_tests',
                },
                {'name': 'county_jail:inmates:total_positive'},
                {
                    'name': 'county_jail:inmates:delta_total_positive',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:total_positive',
                },
                {'name': 'county_jail:inmates:tests_pending'},
                {
                    'name': 'county_jail:inmates:delta_tests_pending',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:tests_pending',
                },
                {'name': 'county_jail:inmates:current_cases'},
                {
                    'name': 'county_jail:inmates:delta_current_cases',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:current_cases',
                },
                {'name': 'county_jail:inmates:total_recovered'},
                {
                    'name': 'county_jail:inmates:delta_total_recovered',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:total_recovered',
                },
                {'name': 'county_jail:staff:total_tests'},
                {
                    'name': 'county_jail:staff:delta_total_tests',
                    'type': 'delta',
                    'delta_from': 'county_jail:staff:total_tests',
                },
                {'name': 'county_jail:staff:current_cases'},
                {
                    'name': 'county_jail:staff:delta_current_cases',
                    'type': 'delta',
                    'delta_from': 'county_jail:staff:current_cases',
                },
                {
                    'name': 'monitoring:tier',
                    'type': 'string',
                },
                {
                    'name': 'monitoring:new_case_rate',
                    'type': 'real',
                },
                {
                    'name': 'monitoring:delta_new_case_rate',
                    'type': 'delta',
                    'delta_from': 'monitoring:new_case_rate',
                    'delta_type': 'real',
                },
                {
                    'name': 'monitoring:test_pos_rate',
                    'type': 'pct',
                },
                {
                    'name': 'monitoring:delta_test_pos_rate',
                    'type': 'delta',
                    'delta_from': 'monitoring:test_pos_rate',
                    'delta_type': 'pct',
                },
                {'name': 'vaccines:allocated'},
                {'name': 'vaccines:administered'},
                {'name': 'vaccines:first_doses_ordered'},
                {'name': 'vaccines:second_doses_ordered'},
                {'name': 'vaccines:received'},
                {'name': 'vaccines:chhs:administered:1_or_more_doses'},
                {
                    'name': 'vaccines:chhs:administered:1_or_more_doses_pct',
                    'type': 'pct',
                },
                {'name': 'vaccines:chhs:administered:fully'},
                {
                    'name': 'vaccines:chhs:administered:fully_pct',
                    'type': 'pct',
                },
                {'name': 'vaccines:chhs:administered:boosted'},
                {
                    'name': 'vaccines:chhs:administered:boosted_pct',
                    'type': 'pct',
                },
                {'name': 'vaccines:chhs:administered:total'},
                {'name': 'vaccines:chhs:administered:pfizer'},
                {'name': 'vaccines:chhs:administered:moderna'},
                {'name': 'vaccines:chhs:administered:j_and_j'},
                {'name': 'adult_senior_care:current_patient_cases'},
                {'name': 'adult_senior_care:current_staff_cases'},
                {'name': 'adult_senior_care:total_patient_deaths'},
                {'name': 'adult_senior_care:total_staff_deaths'},
                {
                    'name': 'vaccines:demographics:gender:male',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:gender:female',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:gender:unknown',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:age:0_11',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:age:12_17',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:age:18_49',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:age:50_64',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:age:65_plus',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:age:unknown',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:ethnicity:ai_an',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:ethnicity:asian_american',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:ethnicity:black',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:ethnicity:latino',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:ethnicity:nhpi',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:ethnicity:white',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:ethnicity:multi_race',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:ethnicity:other',
                    'type': 'pct',
                },
                {
                    'name': 'vaccines:demographics:ethnicity:unknown',
                    'type': 'pct',
                },
            ],
        },
    },
    {
        'filename': 'timeline.json',
        'min_filename': 'timeline.min.json',
        'format': 'json',
        'local_source': {
            'filename': 'timeline.csv',
            'format': 'csv',
        },
        'parser': build_dataset,
    },
]
