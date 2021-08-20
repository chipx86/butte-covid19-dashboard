import json
import os
from collections import OrderedDict
from datetime import datetime

from bc19live.utils import safe_open_for_write


DATASET_VERSION = 1


AGE_RANGE_INFO_MAP = {
    '0_4': {
        'source_key': '0-4',
    },
    '5_12': {
        'source_key': '5-12',
    },
    '13_17': {
        'source_key': '13-17',
    },
    '18_24': {
        'source_key': '18-24',
    },
    '25_34': {
        'source_key': '25-34',
    },
    '35_44': {
        'source_key': '35-44',
    },
    '45_54': {
        'source_key': '45-54',
    },
    '55_64': {
        'source_key': '55-64',
    },
    '65_74': {
        'source_key': '65-74',
    },
    '75_plus': {
        'source_key': '75_plus',
        'text': '75+',
    },

    # Legacy data, unpublished as of December 9, 2020.
    '0_17': {
        'legacy': True,
        'source_key': '0-17',
    },

    # Legacy data, unpublished as of July 9, 2020.
    '18_49': {
        'legacy': True,
        'source_key': '18-49',
    },
    '50_64': {
        'legacy': True,
        'source_key': '50-64',
    },
    '65_plus': {
        'legacy': True,
        'source_key': '65_plus',
        'text': '65+',
    },
}

# Ensure these are in sorted order.
AGE_RANGE_INFO_MAP = OrderedDict(
    pair
    for pair in sorted(AGE_RANGE_INFO_MAP.items(),
                       key=lambda pair: (pair[1].get('legacy', False),
                                         int(pair[0].split('_')[0])))
)

AGE_RANGE_KEYS = list(AGE_RANGE_INFO_MAP.keys())

REGIONS = [
    {
        'key': 'biggs_gridley',
        'label': 'Biggs, Gridley',
    },
    {
        'key': 'chico',
        'label': 'Chico',
    },
    {
        'key': 'durham',
        'label': 'Durham',
    },
    {
        'key': 'oroville',
        'label': 'Oroville',
    },
    {
        'key': 'ridge',
        'label': 'Paradise, Magalia...',
    },
    {
        'key': 'other',
        'label': 'Other',
    },
]

HOSPTIALS = [
    {
        'key': 'enloe_hospital',
        'label': 'Enloe Hospital',
    },
    {
        'key': 'oroville_hospital',
        'label': 'Oroville Hospital',
    },
    {
        'key': 'orchard_hospital',
        'label': 'Orchard Hospital',
    },
]


POPULATION = 217769


def norm_rel_value(value, prev_value):
    """Return a normalized number relative to another number.

    The relative value is the difference between the value and the previous
    value.

    Args:
        value (int):
            The "new" value.

        prev_value (int):
            The previous value that ``value`` is relative to. If ``None``,
            this function will simply return 0.

        hide_negative (bool, optional):
    """
    if prev_value is None:
        return 0

    return value - prev_value


def build_dataset(info, in_fps, out_filename, **kwargs):
    """Parse other datasets to generate JSON data for the dashboard.

    This takes the generated timeline data and compiles it into a dataset
    that can be directly fed into the counters and graphs on the dashboard,
    keeping file sizes down.

    Both a ``.json`` and a ``.min.json`` (actually used by the website) will
    be generated.

    Args:
        info (dict):
            Parser option information. This must define ``min_filename``.

        in_fps (dict):
            A mapping of all source names to file pointers.

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
    def build_bar_graph_data(data_id, label, row_index, get_value):
        latest_row = rows[row_index]
        prev_row = rows[row_index - 1]

        value = get_value(latest_row)
        prev_value = get_value(prev_row)

        return {
            'data_id': data_id,
            'label': label,
            'value': value,
            'relValue': norm_rel_value(value, prev_value),
        }

    def build_counter_data(get_value, row_index=-1, delta_days=[1],
                           is_pct=False, data_rows=None):
        if data_rows is None:
            data_rows = rows

        latest_row = data_rows[row_index]

        data = {
            'value': get_value(data_rows[row_index]),
            'relativeValues': [
                get_value(data_rows[max(0, row_index - num_days)])
                for num_days in delta_days
            ],
        }

        if is_pct:
            data['isPct'] = True

        return data

    timeline = json.loads(in_fps['timeline'].read())

    rows = timeline['dates']

    graph_dates = ['date']

    graph_total_cases = ['cases']
    graph_new_cases = ['new_cases']
    graph_total_deaths = ['total_deaths']
    graph_new_deaths = ['new_deaths']
    graph_one_week_new_case_rate = ['new_case_rate']

    graph_total_tests = ['total_tests']
    graph_new_tests = ['new_tests']
    graph_total_test_results = ['test_results']
    graph_negative_results = ['neg_results']
    graph_positive_results = ['pos_results']
    graph_test_pos_rate = ['test_pos_rate']

    graph_cases_in_biggs_gridley = ['biggs_gridley']
    graph_cases_in_chico = ['chico']
    graph_cases_in_durham = ['durham']
    graph_cases_in_gridley = ['gridley']
    graph_cases_in_oroville = ['oroville']
    graph_cases_in_ridge = ['ridge']
    graph_cases_in_other = ['other']

    graph_cases_by_age = OrderedDict()
    graph_deaths_by_age = OrderedDict()

    graph_in_isolation = ['in_isolation']
    graph_released_from_isolation = ['released_from_isolation']

    graph_hospitalizations = ['hospitalizations']
    graph_icu = ['icu']
    graph_hospitalized_residents = ['residents']

    graph_snf_cur_patient_cases = ['current_patient_cases']
    graph_snf_cur_staff_cases = ['current_staff_cases']
    graph_snf_total_patient_deaths = ['total_patient_deaths']
    graph_snf_total_staff_deaths = ['total_staff_deaths']
    graph_snf_new_patient_deaths = ['new_patient_deaths']
    graph_snf_new_staff_deaths = ['new_staff_deaths']

    graph_asc_cur_patient_cases = ['current_patient_cases']
    graph_asc_cur_staff_cases = ['current_staff_cases']
    graph_asc_total_patient_deaths = ['total_patient_deaths']
    graph_asc_total_staff_deaths = ['total_staff_deaths']
    graph_asc_new_patient_deaths = ['new_patient_deaths']
    graph_asc_new_staff_deaths = ['new_staff_deaths']

    graph_jail_pop = ['jail_inmate_pop']
    graph_jail_inmate_tests = ['jail_inmate_tests']
    graph_jail_inmate_pos_results = ['jail_inmate_pos_results']
    graph_jail_inmate_cur_cases = ['jail_inmate_cur_cases']
    graph_jail_staff_tests = ['jail_staff_tests']
    graph_jail_staff_total_cases = ['jail_staff_total_cases']

    graph_vaccines_1st_dose = ['vaccines_1st_dose']
    graph_vaccines_1st_dose_pct = ['vaccines_1st_dose_pct']
    graph_vaccines_full_doses = ['vaccines_full_doses']
    graph_vaccines_full_doses_pct = ['vaccines_full_doses_pct']

    graph_vaccines_1st_dose_rate = ['vaccines_1st_dose_rate']
    graph_vaccines_full_doses_rate = ['vaccines_full_doses_rate']

    graph_vaccines_administered_total = ['vaccines_administered_total']
    graph_vaccines_administered_pfizer = ['vaccines_administered_pfizer']
    graph_vaccines_administered_moderna = ['vaccines_administered_moderna']
    graph_vaccines_administered_jj = ['vaccines_administered_jj']

    graph_vaccines_gender_male = ['vaccines_male']
    graph_vaccines_gender_female = ['vaccines_female']
    graph_vaccines_gender_unknown = ['vaccines_unknown']

    graph_vaccines_age_0_11 = ['vaccines_0_11']
    graph_vaccines_age_12_17 = ['vaccines_12_17']
    graph_vaccines_age_18_49 = ['vaccines_18_49']
    graph_vaccines_age_50_64 = ['vaccines_50_64']
    graph_vaccines_age_65_plus = ['vaccines_65_plus']
    graph_vaccines_age_unknown = ['vaccines_unknown']

    graph_vaccines_ethnicity_ai_an = ['vaccines_ai_an']
    graph_vaccines_ethnicity_asian_american = ['vaccines_asian_american']
    graph_vaccines_ethnicity_black = ['vaccines_black']
    graph_vaccines_ethnicity_latino = ['vaccines_latino']
    graph_vaccines_ethnicity_white = ['vaccines_white']
    graph_vaccines_ethnicity_nhpi = ['vaccines_nhpi']
    graph_vaccines_ethnicity_multirace = ['vaccines_multirace']
    graph_vaccines_ethnicity_other = ['vaccines_other']
    graph_vaccines_ethnicity_unknown = ['vaccines_unknown']

    graph_notes = []

    monitoring_tier = None

    max_new_cases = 0
    max_new_deaths = 0
    max_total_cases = 0
    max_total_deaths = 0
    max_one_week_case_rate = 0
    max_viral_tests = 0
    max_hospitalizations_y = 0
    max_new_snf_deaths = 0
    max_cur_snf_cases = 0
    max_new_asc_deaths = 0
    max_cur_asc_cases = 0
    max_seven_day_pos_rate = 0
    max_jail_inmate_cur_cases = 0
    max_jail_inmate_pop = 0
    max_jail_staff_total_cases = 0
    max_vaccines_doses = 0
    max_vaccines_by_type = 0
    max_one_week_vaccines_rate = 0

    min_test_positivity_rate_date = '2020-04-10'
    found_min_test_positivity_rate_date = False

    latest_age_data_row_index = None
    latest_cases_row_index = None
    latest_county_hospital_row_index = None
    latest_death_by_age_row_index = None
    latest_deaths_row_index = None
    latest_isolation_row_index = None
    latest_jail_row_index = None
    latest_per_hospital_row_index = None
    latest_region_row_index = None
    latest_state_hospital_row_index = None
    latest_test_pos_rate_row_index = None
    latest_tests_row_index = None
    latest_vaccines_county_row_index = None
    latest_vaccines_chhs_row_index = None

    for key in AGE_RANGE_KEYS:
        norm_key = 'age_%s' % key

        graph_cases_by_age[key] = [norm_key]
        graph_deaths_by_age[key] = [norm_key]

    for i, row in enumerate(rows):
        date = row['date']
        graph_dates.append(date)

        confirmed_cases_data = row['confirmed_cases']
        deaths_data = row['deaths']
        viral_tests_data = row['viral_tests']
        regions_data = row['regions']
        cases_by_age_range_data = row['age_ranges_in_years']
        deaths_by_age_range_data = deaths_data['age_ranges_in_years']
        hospitalizations_data = row['hospitalizations']
        county_hospital_data = hospitalizations_data['county_data']
        state_hospital_data = hospitalizations_data['state_data']
        snf_data = row['skilled_nursing_facilities']
        asc_data = row['adult_senior_care']
        county_jail_data = row['county_jail']
        in_isolation_data = row['in_isolation']
        monitoring_data = row['monitoring']
        vaccines_data = row['vaccines']

        prev_day_row = rows[i - 1]
        week_ago_row = rows[i - 7]
        two_weeks_ago_row = rows[i - 14]

        # Confirmed cases
        confirmed_cases_total = confirmed_cases_data['total']
        delta_confirmed_cases = max(confirmed_cases_data['delta_total'] or 0,
                                    0)

        graph_total_cases.append(confirmed_cases_total)
        graph_new_cases.append(delta_confirmed_cases)

        max_new_cases = max(max_new_cases, delta_confirmed_cases or 0)
        max_total_cases = max(max_total_cases, confirmed_cases_total or 0)

        if confirmed_cases_total is not None:
            latest_cases_row_index = i

        # Deaths
        deaths_total = deaths_data['total']
        deaths_delta_total = deaths_data['delta_total']

        graph_total_deaths.append(deaths_total)
        graph_new_deaths.append(deaths_delta_total)

        max_new_deaths = max(max_new_deaths, deaths_delta_total or 0)
        max_total_deaths = max(max_total_deaths, deaths_total or 0)

        if deaths_total is not None:
            latest_deaths_row_index = i

        # 7-Day New Case Rate
        one_week_case_rate_i1 = i - 7
        one_week_case_rate = None

        if one_week_case_rate_i1 >= 0:
            one_week_case_rate_row1 = rows[one_week_case_rate_i1]
            one_week_case_rate_row2 = rows[i]
            one_week_case_rate_total1 = \
                one_week_case_rate_row1['confirmed_cases']['total']
            one_week_case_rate_total2 = \
                one_week_case_rate_row2['confirmed_cases']['total']

            if (one_week_case_rate_total1 is not None and
                one_week_case_rate_total2 is not None):
                one_week_case_rate = (
                    one_week_case_rate_total2 -
                    one_week_case_rate_total1) / 7 / (POPULATION / 100000)
                max_one_week_case_rate = max(max_one_week_case_rate,
                                             one_week_case_rate)

        graph_one_week_new_case_rate.append(one_week_case_rate)

        # Testing Data
        viral_tests_total = viral_tests_data['total']
        viral_tests_delta_total = viral_tests_data['delta_total']
        viral_tests_results = viral_tests_data['results'] or 0
        viral_tests_pos_results = viral_tests_data['positive_results']
        viral_tests_delta_pos_results = \
            viral_tests_data['delta_positive_results']

        graph_total_tests.append(viral_tests_total)
        graph_new_tests.append(viral_tests_delta_total)
        graph_total_test_results.append(viral_tests_results)

        if viral_tests_results and viral_tests_pos_results is not None:
            graph_negative_results.append(viral_tests_results -
                                          viral_tests_delta_pos_results)
            graph_positive_results.append(viral_tests_delta_pos_results)
        else:
            graph_negative_results.append(0)
            graph_positive_results.append(0)

        if (viral_tests_total is not None and
            viral_tests_delta_total is not None):
            max_viral_tests = max(max_viral_tests, viral_tests_delta_total)

        if viral_tests_results is not None and viral_tests_total is not None:
            latest_tests_row_index = i

        # Cases By Region
        graph_cases_in_biggs_gridley.append(
            regions_data['biggs_gridley']['cases'])
        graph_cases_in_chico.append(regions_data['chico']['cases'])
        graph_cases_in_durham.append(regions_data['durham']['cases'])
        graph_cases_in_gridley.append(regions_data['gridley']['cases'])
        graph_cases_in_oroville.append(regions_data['oroville']['cases'])
        graph_cases_in_other.append(regions_data['other']['cases'])
        graph_cases_in_ridge.append(regions_data['ridge']['cases'])

        if regions_data['chico']['cases'] is not None:
            latest_region_row_index = i

        # Cases/Deaths By Age
        found_case_by_age = False
        found_death_by_age = False

        for key in AGE_RANGE_KEYS:
            source_key = AGE_RANGE_INFO_MAP[key]['source_key']
            case_by_age = cases_by_age_range_data.get(source_key)
            death_by_age = deaths_by_age_range_data.get(source_key)

            graph_cases_by_age[key].append(case_by_age)
            graph_deaths_by_age[key].append(death_by_age)

            if case_by_age is not None:
                found_case_by_age = True

            if death_by_age is not None:
                found_death_by_age = True

        if found_case_by_age:
            latest_age_data_row_index = i

        if found_death_by_age:
            latest_death_by_age_row_index = i

        # People In Isolation
        current_in_isolation = in_isolation_data['current']

        graph_in_isolation.append(current_in_isolation)
        graph_released_from_isolation.append(
            in_isolation_data['total_released'])

        if current_in_isolation is not None:
            latest_isolation_row_index = i

        # Hospitalizations
        state_hospital_positive = state_hospital_data['positive']
        county_hospital_positive = county_hospital_data['hospitalized']

        graph_hospitalizations.append(state_hospital_positive)
        graph_icu.append(state_hospital_data['icu_positive'])
        graph_hospitalized_residents.append(county_hospital_positive)

        max_hospitalizations_y = max(max_hospitalizations_y,
                                     state_hospital_positive or 0,
                                     county_hospital_positive or 0)

        if county_hospital_positive is not None:
            latest_county_hospital_row_index = i

        if state_hospital_positive is not None:
            latest_state_hospital_row_index = i

        if state_hospital_data['enloe_hospital'] is not None:
            latest_per_hospital_row_index = i

        # Skilled Nursing Facilities
        snf_cur_patient_cases = snf_data['current_patient_cases']
        snf_cur_staff_cases = snf_data['current_staff_cases']
        snf_total_patient_deaths = snf_data['total_patient_deaths']
        snf_total_staff_deaths = snf_data['total_staff_deaths']

        graph_snf_cur_patient_cases.append(snf_cur_patient_cases)
        graph_snf_cur_staff_cases.append(snf_cur_staff_cases)
        graph_snf_total_patient_deaths.append(snf_total_patient_deaths)
        graph_snf_total_staff_deaths.append(snf_total_staff_deaths)

        if (snf_cur_patient_cases is not None and
            snf_cur_staff_cases is not None):
            max_cur_snf_cases = max(
                max_cur_snf_cases,
                (snf_cur_patient_cases + snf_cur_staff_cases))

        if (i > 0 and
            snf_total_patient_deaths is not None and
            snf_total_staff_deaths is not None):
            prev_snf = prev_day_row['skilled_nursing_facilities']

            snf_new_patient_deaths = (snf_total_patient_deaths -
                                      (prev_snf['total_patient_deaths'] or 0))
            snf_new_staff_deaths = (snf_total_staff_deaths -
                                    (prev_snf['total_staff_deaths'] or 0))
        else:
            snf_new_patient_deaths = snf_total_patient_deaths
            snf_new_staff_deaths = snf_total_staff_deaths

        graph_snf_new_patient_deaths.append(snf_new_patient_deaths)
        graph_snf_new_staff_deaths.append(snf_new_staff_deaths)

        max_new_snf_deaths = max(
            max_new_snf_deaths,
            (snf_new_patient_deaths or 0) + (snf_new_staff_deaths or 0))

        # Adult/Senior Care Facilities
        asc_cur_patient_cases = asc_data['current_patient_cases']
        asc_cur_staff_cases = asc_data['current_staff_cases']
        asc_total_patient_deaths = asc_data['total_patient_deaths']
        asc_total_staff_deaths = asc_data['total_staff_deaths']

        graph_asc_cur_patient_cases.append(asc_cur_patient_cases)
        graph_asc_cur_staff_cases.append(asc_cur_staff_cases)
        graph_asc_total_patient_deaths.append(asc_total_patient_deaths)
        graph_asc_total_staff_deaths.append(asc_total_staff_deaths)

        if (asc_cur_patient_cases is not None and
            asc_cur_staff_cases is not None):
            max_cur_asc_cases = max(
                max_cur_asc_cases,
                (asc_cur_patient_cases + asc_cur_staff_cases))

        if (i > 0 and
            asc_total_patient_deaths is not None and
            asc_total_staff_deaths is not None):
            prev_asc = prev_day_row['adult_senior_care']

            asc_new_patient_deaths = (asc_total_patient_deaths -
                                      (prev_asc['total_patient_deaths'] or 0))
            asc_new_staff_deaths = (asc_total_staff_deaths -
                                    (prev_asc['total_staff_deaths'] or 0))
        else:
            asc_new_patient_deaths = asc_total_patient_deaths
            asc_new_staff_deaths = asc_total_staff_deaths

        graph_asc_new_patient_deaths.append(asc_new_patient_deaths)
        graph_asc_new_staff_deaths.append(asc_new_staff_deaths)

        max_new_asc_deaths = max(
            max_new_asc_deaths,
            (asc_new_patient_deaths or 0) + (asc_new_staff_deaths or 0))

        # 7-Day Test Positivity Rate
        if (not found_min_test_positivity_rate_date and
            date == min_test_positivity_rate_date):
            found_min_test_positivity_rate_date = True

        viral_tests_pos_rate = viral_tests_data['pos_rate']
        graph_test_pos_rate.append(viral_tests_pos_rate)

        if viral_tests_pos_rate is not None:
            max_seven_day_pos_rate = max(max_seven_day_pos_rate,
                                         viral_tests_pos_rate)
            latest_test_pos_rate_row_index = i

        # Notable Events
        note = row['note']

        if note:
            graph_notes.append({
                'value': date,
                'text': note,
            })

        # County Jail
        jail_inmates_data = county_jail_data['inmates']
        jail_staff_data = county_jail_data['staff']
        jail_inmate_cur_cases = jail_inmates_data['current_cases']
        jail_inmate_pop = jail_inmates_data['population']
        jail_staff_total_cases = jail_staff_data['total_positive']

        graph_jail_pop.append(jail_inmate_pop)
        graph_jail_inmate_tests.append(jail_inmates_data['total_tests'])
        graph_jail_inmate_pos_results.append(
            jail_inmates_data['total_positive'])
        graph_jail_inmate_cur_cases.append(jail_inmate_cur_cases)
        graph_jail_staff_tests.append(jail_staff_data['total_tests'])
        graph_jail_staff_total_cases.append(jail_staff_total_cases)

        max_jail_inmate_cur_cases = max(max_jail_inmate_cur_cases,
                                        jail_inmate_cur_cases or 0)
        max_jail_inmate_pop = max(max_jail_inmate_pop,
                                  jail_inmate_pop or 0)
        max_jail_staff_total_cases = max(max_jail_staff_total_cases,
                                         jail_staff_total_cases or 0)

        if jail_inmate_pop is not None:
            latest_jail_row_index = i

        # Monitoring Tier
        if monitoring_data and monitoring_data['tier']:
            monitoring_tier = monitoring_data['tier']

        # Vaccines
        vaccines_administered = vaccines_data['chhs']['administered']
        one_or_more_doses = vaccines_administered['1_or_more_doses']
        one_or_more_doses_pct = vaccines_administered['1_or_more_doses_pct']
        full_doses = vaccines_administered['fully']
        full_doses_pct = vaccines_administered['fully_pct']

        if one_or_more_doses_pct is not None:
            one_or_more_doses_pct = round(one_or_more_doses_pct, 2)

        if full_doses_pct is not None:
            full_doses_pct = round(full_doses_pct, 2)

        if one_or_more_doses_pct is not None and full_doses_pct is not None:
            latest_vaccines_chhs_row_index = i

        graph_vaccines_1st_dose.append(one_or_more_doses)
        graph_vaccines_1st_dose_pct.append(one_or_more_doses_pct)
        graph_vaccines_full_doses.append(full_doses)
        graph_vaccines_full_doses_pct.append(full_doses_pct)

        vaccines_administered_total = vaccines_administered['total']
        vaccines_pfizer = vaccines_administered['pfizer']
        vaccines_moderna = vaccines_administered['moderna']
        vaccines_jj = vaccines_administered['j_and_j']

        graph_vaccines_administered_total.append(vaccines_administered_total)
        graph_vaccines_administered_pfizer.append(vaccines_pfizer)
        graph_vaccines_administered_moderna.append(vaccines_moderna)
        graph_vaccines_administered_jj.append(vaccines_jj)

        max_vaccines_doses = max(
            max_vaccines_doses,
            one_or_more_doses or 0,
            full_doses or 0)

        max_vaccines_by_type = max(max_vaccines_by_type,
                                   vaccines_pfizer or 0,
                                   vaccines_moderna or 0,
                                   vaccines_jj or 0)

        vaccine_demographics = vaccines_data['demographics']
        vaccine_gender = vaccine_demographics['gender']
        vaccine_age = vaccine_demographics['age']
        vaccine_ethnicity = vaccine_demographics['ethnicity']

        graph_vaccines_gender_male.append(vaccine_gender['male'])
        graph_vaccines_gender_female.append(vaccine_gender['female'])
        graph_vaccines_gender_unknown.append(vaccine_gender['unknown'])

        graph_vaccines_age_0_11.append(vaccine_age['0_11'])
        graph_vaccines_age_12_17.append(vaccine_age['12_17'])
        graph_vaccines_age_18_49.append(vaccine_age['18_49'])
        graph_vaccines_age_50_64.append(vaccine_age['50_64'])
        graph_vaccines_age_65_plus.append(vaccine_age['65_plus'])
        graph_vaccines_age_unknown.append(vaccine_age['unknown'])

        graph_vaccines_ethnicity_ai_an.append(vaccine_ethnicity['ai_an'])
        graph_vaccines_ethnicity_asian_american.append(
            vaccine_ethnicity['asian_american'])
        graph_vaccines_ethnicity_black.append(vaccine_ethnicity['black'])
        graph_vaccines_ethnicity_latino.append(vaccine_ethnicity['latino'])
        graph_vaccines_ethnicity_white.append(vaccine_ethnicity['white'])
        graph_vaccines_ethnicity_nhpi.append(vaccine_ethnicity['nhpi'])
        graph_vaccines_ethnicity_multirace.append(
            vaccine_ethnicity['multi_race'])
        graph_vaccines_ethnicity_other.append(vaccine_ethnicity['other'])
        graph_vaccines_ethnicity_unknown.append(vaccine_ethnicity['unknown'])

        if vaccines_data and vaccines_data['allocated']:
            latest_vaccines_county_row_index = i

        # 7-Day Vaccines Rate
        one_week_vaccines_rate_i1 = i - 7
        one_week_vaccines_1_dose_rate = None
        one_week_vaccines_full_doses_rate = None

        if one_week_vaccines_rate_i1 >= 0:
            one_week_vaccines_rate_row1 = rows[one_week_vaccines_rate_i1]
            one_week_vaccines_rate_row2 = rows[i]
            one_week_vaccines_rate_1_dose_total_1 = (
                one_week_vaccines_rate_row1
                ['vaccines']['chhs']['administered']['1_or_more_doses']
            )
            one_week_vaccines_rate_1_dose_total_2 = (
                one_week_vaccines_rate_row2
                ['vaccines']['chhs']['administered']['1_or_more_doses']
            )
            one_week_vaccines_rate_full_doses_total_1 = (
                one_week_vaccines_rate_row1
                ['vaccines']['chhs']['administered']['fully']
            )
            one_week_vaccines_rate_full_doses_total_2 = (
                one_week_vaccines_rate_row2
                ['vaccines']['chhs']['administered']['fully']
            )

            if (one_week_vaccines_rate_1_dose_total_1 is not None and
                one_week_vaccines_rate_1_dose_total_2 is not None):
                one_week_vaccines_1_dose_rate = (
                    one_week_vaccines_rate_1_dose_total_2 -
                    one_week_vaccines_rate_1_dose_total_1)

            if (one_week_vaccines_rate_full_doses_total_1 is not None and
                one_week_vaccines_rate_full_doses_total_2 is not None):
                one_week_vaccines_full_doses_rate = (
                    one_week_vaccines_rate_full_doses_total_2 -
                    one_week_vaccines_rate_full_doses_total_1)

            max_one_week_vaccines_rate = max(
                max_one_week_vaccines_rate,
                one_week_vaccines_1_dose_rate or 0,
                one_week_vaccines_full_doses_rate or 0)

        graph_vaccines_1st_dose_rate.append(one_week_vaccines_1_dose_rate)
        graph_vaccines_full_doses_rate.append(
            one_week_vaccines_full_doses_rate)

    latest_rows = {
        'ages': latest_age_data_row_index,
        'cases': latest_cases_row_index,
        'countyHospitals': latest_county_hospital_row_index,
        'deaths': latest_deaths_row_index,
        'deathsByAge': latest_death_by_age_row_index,
        'jail': latest_jail_row_index,
        'isolation': latest_isolation_row_index,
        'perHospital': latest_per_hospital_row_index,
        'regions': latest_region_row_index,
        'stateHospitals': latest_state_hospital_row_index,
        'testPosRate': latest_test_pos_rate_row_index,
        'tests': latest_tests_row_index,
        'vaccines': latest_vaccines_county_row_index,
    }

    for key, index in latest_rows.items():
        if index is None:
            raise ParseError('Could not find latest row index for "%s"' % key)

    latest_cases_row = rows[latest_cases_row_index]
    latest_confirmed_cases = latest_cases_row['confirmed_cases']

    # Process the school data.
    schools_data = json.loads(in_fps['schools'].read())

    schools_date_pad = [None] * (
        datetime.strptime(schools_data[0]['date'], '%Y-%m-%d') -
        datetime.strptime(rows[0]['date'], '%Y-%m-%d')).days

    # Set up the graphs, and pad the beginning.
    graph_schools_semester_student_local_cases = \
        ['semester_students_local'] + schools_date_pad
    graph_schools_semester_student_remote_cases = \
        ['semester_students_remote'] + schools_date_pad
    graph_schools_semester_staff_local_cases = \
        ['semester_staff_local'] + schools_date_pad
    graph_schools_semester_staff_remote_cases = \
        ['semester_staff_remote'] + schools_date_pad

    graph_schools_new_student_local_cases = \
        ['new_students_local'] + schools_date_pad
    graph_schools_new_student_remote_cases = \
        ['new_students_remote'] + schools_date_pad
    graph_schools_new_staff_local_cases = \
        ['new_staff_local'] + schools_date_pad
    graph_schools_new_staff_remote_cases = \
        ['new_staff_remote'] + schools_date_pad

    schools_total_student_local_cases = 0
    schools_total_student_remote_cases = 0
    schools_total_staff_local_cases = 0
    schools_total_staff_remote_cases = 0
    schools_semester_student_local_cases = 0
    schools_semester_student_remote_cases = 0
    schools_semester_staff_local_cases = 0
    schools_semester_staff_remote_cases = 0

    school_totals = []

    max_new_school_cases = 0
    max_semester_school_cases = 0

    for row in schools_data:
        date = row['date']

        # Check if we need to reset the semester. This will happen on
        # August 1st.
        if date.split('-')[1:] == ['08', '01']:
            # New year, who dis?
            schools_semester_student_local_cases = 0
            schools_semester_student_remote_cases = 0
            schools_semester_staff_local_cases = 0
            schools_semester_staff_remote_cases = 0

        # Get the new student and staff counts for this date.
        row_student_local_new = 0
        row_student_remote_new = 0
        row_staff_local_new = 0
        row_staff_remote_new = 0

        for district, district_data in row.get('districts', {}).items():
            district_new_cases = district_data['district_wide']['new_cases']

            row_student_local_new += district_new_cases['students_in_person']
            row_student_remote_new += district_new_cases['students_remote']
            row_staff_local_new += district_new_cases['staff_in_person']
            row_staff_remote_new += district_new_cases['staff_remote']

        # Add to the totals and graph.
        schools_total_student_local_cases += row_student_local_new
        schools_total_student_remote_cases += row_student_remote_new
        schools_total_staff_local_cases += row_staff_local_new
        schools_total_staff_remote_cases += row_staff_remote_new

        schools_semester_student_local_cases += row_student_local_new
        schools_semester_student_remote_cases += row_student_remote_new
        schools_semester_staff_local_cases += row_staff_local_new
        schools_semester_staff_remote_cases += row_staff_remote_new

        graph_schools_new_student_local_cases.append(row_student_local_new)
        graph_schools_new_student_remote_cases.append(row_student_remote_new)
        graph_schools_new_staff_local_cases.append(row_staff_local_new)
        graph_schools_new_staff_remote_cases.append(row_staff_remote_new)

        max_semester_school_cases = max(
            max_semester_school_cases,
            schools_semester_student_local_cases +
            schools_semester_student_remote_cases +
            schools_semester_staff_local_cases +
            schools_semester_staff_remote_cases)
        max_new_school_cases = max(
            max_new_school_cases,
            row_student_local_new +
            row_student_remote_new +
            row_staff_local_new +
            row_staff_remote_new)

        graph_schools_semester_student_local_cases.append(
            schools_semester_student_local_cases)
        graph_schools_semester_student_remote_cases.append(
            schools_semester_student_remote_cases)
        graph_schools_semester_staff_local_cases.append(
            schools_semester_staff_local_cases)
        graph_schools_semester_staff_remote_cases.append(
            schools_semester_staff_remote_cases)

        school_totals.append({
            'students': (schools_semester_student_local_cases +
                         schools_semester_student_remote_cases),
            'staff': (schools_semester_staff_local_cases +
                      schools_semester_staff_remote_cases),
        })

    # Now pad the end, to get it to align with the timeline data.
    school_end_date = datetime.strptime(schools_data[-1]['date'], '%Y-%m-%d')
    timeline_end_date = datetime.strptime(rows[-1]['date'], '%Y-%m-%d')

    if school_end_date < timeline_end_date:
        schools_date_pad = [None] * (timeline_end_date - school_end_date).days

        graph_schools_semester_student_local_cases += schools_date_pad
        graph_schools_semester_student_remote_cases += schools_date_pad
        graph_schools_semester_staff_local_cases += schools_date_pad
        graph_schools_semester_staff_remote_cases += schools_date_pad

        graph_schools_new_student_local_cases += schools_date_pad
        graph_schools_new_student_remote_cases += schools_date_pad
        graph_schools_new_staff_local_cases += schools_date_pad
        graph_schools_new_staff_remote_cases += schools_date_pad

    result = {
        'barGraphs': {
            'byHospital': [
                build_bar_graph_data(
                    data_id=_info['key'],
                    label=_info['label'],
                    row_index=latest_per_hospital_row_index,
                    get_value=lambda row: (
                        row['hospitalizations']['state_data'][_info['key']]
                    ))
                for _info in HOSPTIALS
            ],
            'casesByAge': [
                build_bar_graph_data(
                    data_id=_key,
                    label=_info.get('text', _key.replace('_', '-')),
                    row_index=latest_death_by_age_row_index,
                    get_value=lambda row: (
                        row['age_ranges_in_years'].get(_info['source_key'])
                    ))
                for _key, _info in AGE_RANGE_INFO_MAP.items()
                if not _info.get('legacy', False)
            ],
            'deathsByAge': [
                build_bar_graph_data(
                    data_id=_key,
                    label=_info.get('text', _key.replace('_', '-')),
                    row_index=latest_death_by_age_row_index,
                    get_value=lambda row: (
                        row['deaths']['age_ranges_in_years']
                        .get(_info['source_key'])
                    ))
                for _key, _info in AGE_RANGE_INFO_MAP.items()
                if not _info.get('legacy', False)
            ],
            'mortalityRate': [
                build_bar_graph_data(
                    data_id=_key,
                    label=_info.get('text', _key.replace('_', '-')),
                    row_index=latest_death_by_age_row_index,
                    get_value=lambda row: (
                        (row['deaths']['age_ranges_in_years']
                         .get(_info['source_key'], 0)) /
                        (row['age_ranges_in_years']
                         .get(_info['source_key'], 0)) * 100
                    ))
                for _key, _info in AGE_RANGE_INFO_MAP.items()
                if not _info.get('legacy', False)
            ],
            'casesByRegion': [
                build_bar_graph_data(
                    data_id=_info['key'],
                    label=_info['label'],
                    row_index=latest_region_row_index,
                    get_value=lambda row: (
                        row['regions'][_info['key']]['cases']
                    ))
                for _info in REGIONS
            ],
        },
        'counters': {
            'totalCases': build_counter_data(
                row_index=latest_cases_row_index,
                get_value=lambda row: row['confirmed_cases']['total'],
                delta_days=[1, 7, 14, 30]),
            'totalDeaths': build_counter_data(
                row_index=latest_cases_row_index,
                get_value=lambda row: row['deaths']['total'],
                delta_days=[1, 7, 14, 30]),
            'inIsolation': build_counter_data(
                row_index=latest_isolation_row_index,
                get_value=lambda row: row['in_isolation']['current'],
                delta_days=[1, 7, 14, 30]),
            'hospitalizedResidents': build_counter_data(
                row_index=latest_county_hospital_row_index,
                get_value=lambda row: (
                    row['hospitalizations']['county_data']['hospitalized']
                )),
            'allHospitalized': build_counter_data(
                row_index=latest_state_hospital_row_index,
                get_value=lambda row: (
                    row['hospitalizations']['state_data']['positive']
                )),
            'inICU': build_counter_data(
                row_index=latest_state_hospital_row_index,
                get_value=lambda row: (
                    row['hospitalizations']['state_data']['icu_positive']
                )),
            'schoolYearNewStudentCasesTotal': build_counter_data(
                data_rows=school_totals,
                row_index=len(school_totals) - 1,
                get_value=lambda row: row['students']),
            'schoolYearNewStaffCasesTotal': build_counter_data(
                data_rows=school_totals,
                row_index=len(school_totals) - 1,
                get_value=lambda row: row['staff']),
            'vaccines1DosePct': build_counter_data(
                row_index=latest_vaccines_chhs_row_index,
                get_value=lambda row: (
                    row['vaccines']['chhs']['administered']
                    ['1_or_more_doses_pct']
                ),
                delta_days=[1, 7, 14],
                is_pct=True),
            'vaccinesFullDosesPct': build_counter_data(
                row_index=latest_vaccines_chhs_row_index,
                get_value=lambda row: (
                    row['vaccines']['chhs']['administered']['fully_pct']
                ),
                delta_days=[1, 7, 14],
                is_pct=True),
            'vaccinesAllocated': build_counter_data(
                row_index=latest_vaccines_county_row_index,
                get_value=lambda row: row['vaccines']['allocated'],
                delta_days=[1, 7, 14]),
            'vaccinesAdministered': build_counter_data(
                row_index=latest_vaccines_county_row_index,
                get_value=lambda row: row['vaccines']['administered'],
                delta_days=[1, 7, 14]),
            'vaccinesOrdered1': build_counter_data(
                row_index=latest_vaccines_county_row_index,
                get_value=lambda row: row['vaccines']['first_doses_ordered'],
                delta_days=[1, 7, 14]),
            'vaccinesOrdered2': build_counter_data(
                row_index=latest_vaccines_county_row_index,
                get_value=lambda row: row['vaccines']['second_doses_ordered'],
                delta_days=[1, 7, 14]),
            'vaccinesReceived': build_counter_data(
                row_index=latest_vaccines_county_row_index,
                get_value=lambda row: row['vaccines']['received'],
                delta_days=[1, 7, 14]),
            'totalTests': build_counter_data(
                row_index=latest_tests_row_index,
                get_value=lambda row: row['viral_tests']['total']),
            'positiveTestResults': build_counter_data(
                row_index=latest_cases_row_index,
                get_value=lambda row: row['confirmed_cases']['total']),
            'positiveTestRate': {
                'value': (
                    # Offset by 1 due to the ID at the start of the graph.
                    graph_test_pos_rate[latest_test_pos_rate_row_index + 1]
                ),
                'relativeValues': [
                    graph_test_pos_rate[latest_test_pos_rate_row_index],
                ],
                'isPct': True,
            },
            'jailInmatePop': build_counter_data(
                row_index=latest_jail_row_index,
                get_value=lambda row: (
                    row['county_jail']['inmates']['population']
                )),
            'jailInmateTotalTests': build_counter_data(
                row_index=latest_jail_row_index,
                get_value=lambda row: (
                    row['county_jail']['inmates']['total_tests']
                )),
            'jailInmateCurCases': build_counter_data(
                row_index=latest_jail_row_index,
                get_value=lambda row: (
                    row['county_jail']['inmates']['current_cases']
                )),
            'jailInmatePosRate': {
                'value': (
                    # Offset by 1 due to the ID at the start of the graph.
                    graph_jail_inmate_cur_cases[latest_jail_row_index + 1] /
                    graph_jail_pop[latest_jail_row_index + 1] * 100
                ),
                'relativeValues': [
                    graph_jail_inmate_cur_cases[latest_jail_row_index] /
                    graph_jail_pop[latest_jail_row_index] * 100
                ],
                'isPct': True,
            },
            'jailStaffTotalTests': build_counter_data(
                row_index=latest_jail_row_index,
                get_value=lambda row: (
                    row['county_jail']['staff']['total_tests']
                )),
            'jailStaffTotalCases': build_counter_data(
                row_index=latest_jail_row_index,
                get_value=lambda row: (
                    row['county_jail']['staff']['total_positive']
                )),
        },
        'dates': {
            'first': rows[0]['date'],
            'last': rows[-1]['date'],
            'rows': {
                _key: rows[_index]['date']
                for _key, _index in latest_rows.items()
            },
        },
        'latestRows': latest_rows,
        'maxValues': {
            'jailInmateCurCases': max_jail_inmate_cur_cases,
            'jailInmatePopulation': max_jail_inmate_pop,
            'jailStaffTotalCases': max_jail_staff_total_cases,
            'newCases': max_new_cases,
            'newDeaths': max_new_deaths,
            'semesterSchoolCases': max_semester_school_cases,
            'newSchoolCases': max_new_school_cases,
            'totalCases': max_total_cases,
            'totalDeaths': max_total_deaths,
            'hospitalizations': max_hospitalizations_y,
            'snf': max_cur_snf_cases,
            'newSNFDeaths': max_new_snf_deaths,
            'adultSeniorCareCases': max_cur_snf_cases,
            'newAdultSeniorCareDeaths': max_new_snf_deaths,
            'sevenDayPosRate': max_seven_day_pos_rate,
            'oneWeekCaseRate': max_one_week_case_rate,
            'oneWeekVaccinesRate': max_one_week_vaccines_rate,
            'vaccinesAdministered': max_vaccines_doses,
            'vaccinesAdministeredByType': max_vaccines_by_type,
            'viralTests': max_viral_tests,
        },
        'monitoringTier': monitoring_tier,
        'reportTimestamp': timeline['timestamp'],
        'timelineGraphs': {
            'adultSeniorCare': {
                'curPatientCases': graph_asc_cur_patient_cases,
                'curStaffCases': graph_asc_cur_staff_cases,
                'newPatientDeaths': graph_asc_new_patient_deaths,
                'newStaffDeaths': graph_asc_new_staff_deaths,
            },
            'ageRanges': list(graph_cases_by_age.values()),
            'cases': {
                'newCases': graph_new_cases,
                'totalCases': graph_total_cases,
                'oneWeekNewCaseRate': graph_one_week_new_case_rate,
            },
            'dates': graph_dates,
            'deaths': {
                'byAge': graph_deaths_by_age,
                'newDeaths': graph_new_deaths,
                'totalDeaths': graph_total_deaths,
            },
            'hospitalizations': {
                'icu': graph_icu,
                'residents': graph_hospitalized_residents,
                'total': graph_hospitalizations,
            },
            'isolation': {
                'current': graph_in_isolation,
                'released': graph_released_from_isolation,
            },
            'jail': {
                'inmateCurCases': graph_jail_inmate_cur_cases,
                'inmatePopulation': graph_jail_pop,
                'inmatePosResults': graph_jail_inmate_pos_results,
                'inmateTests': graph_jail_inmate_tests,
                'staffTests': graph_jail_staff_tests,
                'staffTotalCases': graph_jail_staff_total_cases,
            },
            'notes': graph_notes,
            'regions': {
                'biggsGridley': graph_cases_in_biggs_gridley,
                'chico': graph_cases_in_chico,
                'durham': graph_cases_in_durham,
                'gridley': graph_cases_in_gridley,
                'oroville': graph_cases_in_oroville,
                'other': graph_cases_in_other,
                'ridge': graph_cases_in_ridge,
            },
            'schools': {
                'newStudentCasesLocal': graph_schools_new_student_local_cases,
                'newStudentCasesRemote':
                    graph_schools_new_student_remote_cases,
                'newStaffCasesLocal': graph_schools_new_staff_local_cases,
                'newStaffCasesRemote': graph_schools_new_staff_remote_cases,
                'semesterStudentCasesLocal':
                    graph_schools_semester_student_local_cases,
                'semesterStudentCasesRemote':
                    graph_schools_semester_student_remote_cases,
                'semesterStaffCasesLocal':
                    graph_schools_semester_staff_local_cases,
                'semesterStaffCasesRemote':
                    graph_schools_semester_staff_remote_cases,
            },
            'snf': {
                'curPatientCases': graph_snf_cur_patient_cases,
                'curStaffCases': graph_snf_cur_staff_cases,
                'newPatientDeaths': graph_snf_new_patient_deaths,
                'newStaffDeaths': graph_snf_new_staff_deaths,
            },
            'vaccines': {
                'firstDoses': graph_vaccines_1st_dose,
                'fullDoses': graph_vaccines_full_doses,
                'firstDosesPct': graph_vaccines_1st_dose_pct,
                'fullDosesPct': graph_vaccines_full_doses_pct,
                'administeredTotal': graph_vaccines_administered_total,
                'administeredPfizer': graph_vaccines_administered_pfizer,
                'administeredModerna': graph_vaccines_administered_moderna,
                'administeredJJ': graph_vaccines_administered_jj,
                'age': {
                    '0_11': graph_vaccines_age_0_11,
                    '12_17': graph_vaccines_age_12_17,
                    '18_49': graph_vaccines_age_18_49,
                    '50_64': graph_vaccines_age_50_64,
                    '65_plus': graph_vaccines_age_65_plus,
                    'unknown': graph_vaccines_age_unknown,
                },
                'ethnicity': {
                    'aian': graph_vaccines_ethnicity_ai_an,
                    'asianAmerican':
                        graph_vaccines_ethnicity_asian_american,
                    'black': graph_vaccines_ethnicity_black,
                    'latino': graph_vaccines_ethnicity_latino,
                    'multirace': graph_vaccines_ethnicity_multirace,
                    'nhpi': graph_vaccines_ethnicity_nhpi,
                    'other': graph_vaccines_ethnicity_other,
                    'unknown': graph_vaccines_ethnicity_unknown,
                    'white': graph_vaccines_ethnicity_white,
                },
                'gender': {
                    'male': graph_vaccines_gender_male,
                    'female': graph_vaccines_gender_female,
                    'unknown': graph_vaccines_gender_unknown,
                },
                'oneWeek1DoseRate': graph_vaccines_1st_dose_rate,
                'oneWeekFullDosesRate': graph_vaccines_full_doses_rate,
            },
            'viralTests': {
                'negativeResults': graph_negative_results,
                'newTests': graph_new_tests,
                'positiveResults': graph_positive_results,
                'results': graph_total_test_results,
                'testPositivityRate': graph_test_pos_rate,
                'total': graph_total_tests,
            },
        },
    }

    with safe_open_for_write(out_filename) as fp:
        json.dump(result,
                  fp,
                  sort_keys=True,
                  indent=2)

    min_filename = os.path.join(os.path.dirname(out_filename),
                                info['min_filename'])

    with safe_open_for_write(min_filename) as fp:
        json.dump(result,
                  fp,
                  sort_keys=True,
                  separators=(',', ':'))

    return True


DATASETS = [
    {
        'filename': 'bc19-dashboard.json',
        'min_filename': 'bc19-dashboard.%s.min.json' % DATASET_VERSION,
        'format': 'json',
        'local_sources': {
            'schools': {
                'filename': 'schools.json',
                'format': 'json',
            },
            'timeline': {
                'filename': 'timeline.json',
                'format': 'json',
            },
        },
        'parser': build_dataset,
    },
]
