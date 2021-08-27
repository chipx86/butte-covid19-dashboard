import json
import os
import re
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


# This is hacky, having two, but it reduces date parsing in the main dashboard.
NEW_SCHOOL_YEAR_START = (8, 1)
NEW_SCHOOL_YEAR_START_STRS = ['08', '01']

SCHOOL_ID_ESCAPE_RE = re.compile(r'[^A-Za-z0-9]')


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


def build_bar_graph_data(rows, data_id, label, row_index=-1, get_value=None):
    """Return data used for an entry on a bar graph.

    Args:
        rows (list):
            The row data containing values for the bar graph entry.

        data_id (str):
            The ID identifying the entry.

        label (str):
            The label for the entry.

        row_index (int, optional):
            The index into the row data for the current value.

        get_value (callable, optional):
            A function for processing the value used in the entry. This
            defaults to returning the value as-is.

    Returns:
        dict:
        JSON data for the entry for the page.
    """
    if get_value is None:
        get_value = lambda row: row

    try:
        latest_row = rows[row_index]
        value = get_value(latest_row)
    except IndexError:
        value = 0

    try:
        prev_row = rows[row_index - 1]
        prev_value = get_value(prev_row)
    except IndexError:
        prev_value = 0

    return {
        'data_id': data_id,
        'label': label,
        'value': value,
        'relValue': norm_rel_value(value, prev_value),
    }


def build_counter_data(rows, get_value=None, row_index=-1, delta_days=[1],
                       is_pct=False):
    """Return data used for a counter.

    Args:
        rows (list):
            The row data containing values for the counter.

        get_value (callable, optional):
            A function for processing the value used in the counter. This
            defaults to returning the value as-is.

        row_index (int, optional):
            The index into the row data for the current value.

        delta_days (list of int, optional):
            The list of delta values to compute. These are relative offsets
            before ``row_index`` into ``rows``.

        is_pct (bool, optional):
            Whether the value represents a percentage.

    Returns:
        dict:
        JSON data for the counter for the page.
    """
    if get_value is None:
        get_value = lambda row: row

    rel_values = []

    if rows:
        if row_index < 0:
            row_index = len(rows) + row_index

        for num_days in delta_days:
            if row_index - num_days >= 0:
                rel_values.append(get_value(rows[row_index - num_days]))
            else:
                rel_values.append(0)

        value = get_value(rows[row_index])
    else:
        value = 0

    data = {
        'value': value,
        'relativeValues': rel_values,
    }

    if is_pct:
        data['isPct'] = True

    return data


def build_dashboard_dataset(info, in_fps, out_filename, **kwargs):
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
        if date.split('-')[1:] == NEW_SCHOOL_YEAR_START_STRS:
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
                    rows,
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
                    rows,
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
                    rows,
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
                    rows,
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
                    rows,
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
                rows,
                row_index=latest_cases_row_index,
                get_value=lambda row: row['confirmed_cases']['total'],
                delta_days=[1, 7, 14, 30]),
            'totalDeaths': build_counter_data(
                rows,
                row_index=latest_cases_row_index,
                get_value=lambda row: row['deaths']['total'],
                delta_days=[1, 7, 14, 30]),
            'inIsolation': build_counter_data(
                rows,
                row_index=latest_isolation_row_index,
                get_value=lambda row: row['in_isolation']['current'],
                delta_days=[1, 7, 14, 30]),
            'hospitalizedResidents': build_counter_data(
                rows,
                row_index=latest_county_hospital_row_index,
                get_value=lambda row: (
                    row['hospitalizations']['county_data']['hospitalized']
                )),
            'allHospitalized': build_counter_data(
                rows,
                row_index=latest_state_hospital_row_index,
                get_value=lambda row: (
                    row['hospitalizations']['state_data']['positive']
                )),
            'inICU': build_counter_data(
                rows,
                row_index=latest_state_hospital_row_index,
                get_value=lambda row: (
                    row['hospitalizations']['state_data']['icu_positive']
                )),
            'schoolYearNewStudentCasesTotal': build_counter_data(
                school_totals,
                row_index=len(school_totals) - 1,
                delta_days=[1, 7, 14],
                get_value=lambda row: row['students']),
            'schoolYearNewStaffCasesTotal': build_counter_data(
                school_totals,
                row_index=len(school_totals) - 1,
                delta_days=[1, 7, 14],
                get_value=lambda row: row['staff']),
            'vaccines1DosePct': build_counter_data(
                rows,
                row_index=latest_vaccines_chhs_row_index,
                get_value=lambda row: (
                    row['vaccines']['chhs']['administered']
                    ['1_or_more_doses_pct']
                ),
                delta_days=[1, 7, 14],
                is_pct=True),
            'vaccinesFullDosesPct': build_counter_data(
                rows,
                row_index=latest_vaccines_chhs_row_index,
                get_value=lambda row: (
                    row['vaccines']['chhs']['administered']['fully_pct']
                ),
                delta_days=[1, 7, 14],
                is_pct=True),
            'vaccinesAllocated': build_counter_data(
                rows,
                row_index=latest_vaccines_county_row_index,
                get_value=lambda row: row['vaccines']['allocated'],
                delta_days=[1, 7, 14]),
            'vaccinesAdministered': build_counter_data(
                rows,
                row_index=latest_vaccines_county_row_index,
                get_value=lambda row: row['vaccines']['administered'],
                delta_days=[1, 7, 14]),
            'vaccinesOrdered1': build_counter_data(
                rows,
                row_index=latest_vaccines_county_row_index,
                get_value=lambda row: row['vaccines']['first_doses_ordered'],
                delta_days=[1, 7, 14]),
            'vaccinesOrdered2': build_counter_data(
                rows,
                row_index=latest_vaccines_county_row_index,
                get_value=lambda row: row['vaccines']['second_doses_ordered'],
                delta_days=[1, 7, 14]),
            'vaccinesReceived': build_counter_data(
                rows,
                row_index=latest_vaccines_county_row_index,
                get_value=lambda row: row['vaccines']['received'],
                delta_days=[1, 7, 14]),
            'totalTests': build_counter_data(
                rows,
                row_index=latest_tests_row_index,
                get_value=lambda row: row['viral_tests']['total']),
            'positiveTestResults': build_counter_data(
                rows,
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
                rows,
                row_index=latest_jail_row_index,
                get_value=lambda row: (
                    row['county_jail']['inmates']['population']
                )),
            'jailInmateTotalTests': build_counter_data(
                rows,
                row_index=latest_jail_row_index,
                get_value=lambda row: (
                    row['county_jail']['inmates']['total_tests']
                )),
            'jailInmateCurCases': build_counter_data(
                rows,
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
                rows,
                row_index=latest_jail_row_index,
                get_value=lambda row: (
                    row['county_jail']['staff']['total_tests']
                )),
            'jailStaffTotalCases': build_counter_data(
                rows,
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


def build_schools_dataset(info, in_fps, out_filename, **kwargs):
    """Generate JSON data for the schools dashboard.

    This takes the generated main dashboard data and schools data and compiles
    it into a series of datasets that can be directly fed into the counters and
    graphs on the schools dashboard.

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
    class CaseGraphs:
        def __init__(self, skip_days=0):
            values = [0] * skip_days

            self.dates = ['date'] + values
            self.student_local_cases = ['students_local'] + values
            self.student_remote_cases = ['students_remote'] + values
            self.staff_local_cases = ['staff_local'] + values
            self.staff_remote_cases = ['staff_remote'] + values
            self.new_student_local_cases = ['new_students_local'] + values
            self.new_student_remote_cases = ['new_students_remote'] + values
            self.new_staff_local_cases = ['new_staff_local'] + values
            self.new_staff_remote_cases = ['new_staff_remote'] + values

            self.total_cases = [] + values
            self.student_cases = [] + values
            self.staff_cases = [] + values

            self.weekly_total_cases = [0]

    class CaseCounts:
        def __init__(self):
            self.student_local_cases = 0
            self.student_remote_cases = 0
            self.staff_local_cases = 0
            self.staff_remote_cases = 0

        @property
        def total_cases(self):
            return (self.student_local_cases +
                    self.student_remote_cases +
                    self.staff_local_cases +
                    self.staff_remote_cases)

    class CaseDataState:
        def __init__(self, skip_days=0):
            self.graphs = CaseGraphs(skip_days=skip_days)
            self.counts = CaseCounts()
            self.max_new_cases = 0
            self._pending_case_counts = CaseCounts()

        def add_cases(self, student_local_cases, student_remote_cases,
                      staff_local_cases, staff_remote_cases):
            counts = self.counts
            pending_counts = self._pending_case_counts

            counts.student_local_cases += student_local_cases
            counts.student_remote_cases += student_remote_cases
            counts.staff_local_cases += staff_local_cases
            counts.staff_remote_cases += staff_remote_cases

            pending_counts.student_local_cases += student_local_cases
            pending_counts.student_remote_cases += student_remote_cases
            pending_counts.staff_local_cases += staff_local_cases
            pending_counts.staff_remote_cases += staff_remote_cases

        def finalize_day(self):
            counts = self.counts
            graphs = self.graphs
            pending_counts = self._pending_case_counts

            graphs.new_student_local_cases.append(
                pending_counts.student_local_cases)
            graphs.new_student_remote_cases.append(
                pending_counts.student_remote_cases)
            graphs.new_staff_local_cases.append(
                pending_counts.staff_local_cases)
            graphs.new_staff_remote_cases.append(
                pending_counts.staff_remote_cases)

            graphs.student_local_cases.append(counts.student_local_cases)
            graphs.student_remote_cases.append(counts.student_remote_cases)
            graphs.staff_local_cases.append(counts.staff_local_cases)
            graphs.staff_remote_cases.append(counts.staff_remote_cases)

            total_cases = counts.total_cases

            graphs.total_cases.append(total_cases)
            graphs.student_cases.append(counts.student_local_cases +
                                        counts.student_remote_cases)
            graphs.staff_cases.append(counts.staff_local_cases +
                                      counts.staff_remote_cases)

            graphs.weekly_total_cases[-1] += total_cases

            self.max_new_cases = max(
                self.max_new_cases,
                (pending_counts.student_local_cases +
                 pending_counts.student_remote_cases +
                 pending_counts.staff_local_cases +
                 pending_counts.staff_remote_cases))

            self._pending_case_counts = CaseCounts()

        def finalize_week(self):
            self.graphs.weekly_total_cases.append(0)

    class SchoolState(CaseDataState):
        def __init__(self, school_id, school_name, *args, **kwargs):
            super().__init__(*args, **kwargs)

            self.id = school_id
            self.name = school_name

    class DistrictState(CaseDataState):
        def __init__(self, district_id, district_name, district_short_name):
            super().__init__()

            self.id = district_id
            self.name = district_name
            self.short_name = district_short_name

            self.schools = OrderedDict()
            self.school_types = OrderedDict()
            self.school_names = []

            self.total_cases_by_school = {}

            for school_type, school_name in info['school_types']:
                self.school_types[school_type] = CaseDataState()

        def add_cases(self, school, school_type, *cases):
            super().add_cases(*cases)

            self.schools[make_id(school)].add_cases(*cases)
            self.school_types[school_type].add_cases(*cases)

        def ensure_school(self, school_id, school_name):
            if school_id not in self.schools:
                self.schools[school_id] = SchoolState(school_id=school_id,
                                                      school_name=school_name)
                self.school_names.append(school_name)

        def finalize_day(self):
            super().finalize_day()

            for d in (self.schools, self.school_types):
                for state in d.values():
                    state.finalize_day()

        def finalize_week(self):
            super().finalize_week()

            for d in (self.schools, self.school_types):
                for state in d.values():
                    state.finalize_week()

    class SchoolYearState:
        def __init__(self, year, first_date):
            self.year = year
            self.first_date = first_date
            self.last_date = None

            self.total = CaseDataState()
            self.districts = {
                _district_id: DistrictState(
                    district_id=_district_id,
                    district_name=_district_info['full_name'],
                    district_short_name=_district_info['short_name'])
                for _district_id, _district_info in info['districts']
            }

            self.schools = {}
            self.school_types = {}
            self.num_days = 0

            self.week_districts_with_cases = [set()]
            self.week_district_schools_with_cases = {
                _district_id: [set()]
                for _district_id in self.districts.keys()
            }
            self.week_schools_with_cases = [set()]

        def add_cases(self, district, school, school_type,
                      student_local_cases, student_remote_cases,
                      staff_local_cases, staff_remote_cases):
            district_state = self.districts[district]
            school_state = self.ensure_school(district, school)
            school_type_state = self.ensure_school_type(district, school_type)

            cases = [
                student_local_cases,
                student_remote_cases,
                staff_local_cases,
                staff_remote_cases,
            ]

            district_state.add_cases(school, school_type, *cases)
            school_state.add_cases(*cases)
            school_type_state.add_cases(*cases)
            self.total.add_cases(*cases)

            if (student_local_cases > 0 or
                student_remote_cases > 0 or
                staff_local_cases > 0 or
                staff_remote_cases > 0):
                self.week_districts_with_cases[-1].add(district)
                self.week_district_schools_with_cases[district][-1].add(school)
                self.week_schools_with_cases[-1].add(school)

        def ensure_school_type(self, district, school_type):
            return self._ensure_case_state(self.school_types, school_type)

        def ensure_school(self, district, school_name):
            school_id = make_id(school_name)

            self.districts[district].ensure_school(school_id=school_id,
                                                   school_name=school_name)

            if school_id not in self.schools:
                self.schools[school_id] = SchoolState(school_id=school_id,
                                                      school_name=school_name,
                                                      skip_days=self.num_days)

            return self.schools[school_id]

        def _ensure_case_state(self, d, key):
            if key not in d:
                d[key] = CaseDataState(skip_days=self.num_days)

            return d[key]

        def finalize_day(self, date):
            self.last_date = date

            self.total.graphs.dates.append(date.strftime('%Y-%m-%d'))
            self.total.finalize_day()
            self.num_days += 1

            for d in (self.districts, self.schools, self.school_types):
                for state in d.values():
                    state.finalize_day()

        def finalize_week(self):
            self.total.finalize_week()

            self.week_districts_with_cases.append(set())
            self.week_schools_with_cases.append(set())

            for items in self.week_district_schools_with_cases.values():
                items.append(set())

            for d in (self.districts, self.schools, self.school_types):
                for state in d.values():
                    state.finalize_week()

    class GlobalState:
        def __init__(self):
            self.school_years = OrderedDict()
            self.cur_school_year_state = None

            self.district_ids_to_schools = {}
            self.district_ids_to_school_types = {}

            for district_id, district_info in info['districts']:
                self.district_ids_to_schools[district_id] = OrderedDict()
                self.district_ids_to_school_types[district_id] = OrderedDict()

        def add_school_year(self, year, first_date):
            school_year_state = SchoolYearState(year=year,
                                                first_date=first_date)
            self.school_years[year] = school_year_state
            self.cur_school_year_state = school_year_state

        def add_cases(self, district, school, school_type,
                      student_local_cases, student_remote_cases,
                      staff_local_cases, staff_remote_cases):
            assert self.cur_school_year_state

            district_schools = self.district_ids_to_schools[district]
            district_school_types = self.district_ids_to_school_types[district]

            if school not in district_schools:
                district_schools[make_id(school)] = school

            if school_type not in district_school_types:
                district_school_types[make_id(school_type)] = \
                    SCHOOL_TYPE_ID_NAME_MAP[school_type]

            self.cur_school_year_state.add_cases(
                district, school, school_type, student_local_cases,
                student_remote_cases, staff_local_cases,
                staff_remote_cases)

        def finalize_day(self, date):
            assert self.cur_school_year_state
            self.cur_school_year_state.finalize_day(date)

        def finalize_week(self):
            assert self.cur_school_year_state
            self.cur_school_year_state.finalize_week()

        def finalize(self):
            # Make sure that all school years and districts have the same
            # lists of schools.
            for district_id, schools in self.district_ids_to_schools.items():
                for school in schools:
                    for school_year_state in self.school_years.values():
                        school_year_state.ensure_school(district_id, school)

    def make_id(name):
        return SCHOOL_ID_ESCAPE_RE.sub('_', name)

    def make_graph_result(graphs):
        return {
            'studentLocalCases': graphs.student_local_cases,
            'studentRemoteCases': graphs.student_remote_cases,
            'staffLocalCases': graphs.staff_local_cases,
            'staffRemoteCases': graphs.staff_remote_cases,
            'newStudentLocalCases': graphs.new_student_local_cases,
            'newStudentRemoteCases': graphs.new_student_remote_cases,
            'newStaffLocalCases': graphs.new_staff_local_cases,
            'newStaffRemoteCases': graphs.new_staff_remote_cases,
        }

    def iter_districts(school_year):
        for district_id, district_info in info['districts']:
            district_key = district_info['full_name']
            state = school_year.districts.get(district_id)

            if state is not None:
                yield district_id, state

    DISTRICT_NAME_ID_MAP = {
        _district_info['full_name']: _district_id
        for _district_id, _district_info in info['districts']
    }

    SCHOOL_TYPE_ID_NAME_MAP = dict(info['school_types'])

    bc19_dashboard = json.loads(in_fps['bc19_dashboard'].read())
    rows = json.loads(in_fps['schools'].read())

    # Set up the initial state.
    first_school_year = 2020

    state = GlobalState()
    state.add_school_year(year=first_school_year,
                          first_date=datetime.strptime(rows[0]['date'],
                                                       '%Y-%m-%d'))

    for row in rows:
        date_str = row['date']
        date = datetime.strptime(date_str, '%Y-%m-%d')

        # Check if we need to reset the school_year. This will happen on
        # August 1st.
        if (date.month, date.day) == NEW_SCHOOL_YEAR_START:
            # New year, who dis?
            state.add_school_year(year=date.year,
                                  first_date=date)

        # Get the new student and staff counts for this date.
        for district, district_data in row.get('districts', {}).items():
            district_id = DISTRICT_NAME_ID_MAP[district]

            for school_type, schools in district_data.items():
                if school_type == 'district_wide':
                    continue

                for school, school_data in schools.items():
                    school_new_cases = school_data['new_cases']
                    state.add_cases(
                        district_id,
                        school,
                        school_type,
                        school_new_cases['students_in_person'],
                        school_new_cases['students_remote'],
                        school_new_cases['staff_in_person'],
                        school_new_cases['staff_remote'])

        state.finalize_day(date)

        if date.weekday() == 5:
            state.finalize_week()

    # Check if we're processing this in a new week. If so, then we need to
    # finalize again, once for each week that's elapsed, because we don't want
    # the last week's worth of data to show up as current.
    for i in range(datetime.today().isocalendar()[1] - date.isocalendar()[1]):
        school_year.finalize_week()

    state.finalize()

    school_years = state.school_years.values()

    import pprint
    pprint.pprint(state.cur_school_year_state.week_district_schools_with_cases)

    result = {
        'barGraphs': {
            _school_year.year: {
                'countyWide': {
                    'casesByDistrict': [
                        build_bar_graph_data(
                            _district.graphs.total_cases,
                            data_id=_district_id,
                            label=_district.short_name)
                        for (_district_id,
                             _district) in _school_year.districts.items()
                    ],
                    'casesByGradeLevel': [
                        build_bar_graph_data(
                            (_school_year.school_types[_key]
                             .graphs.total_cases),
                            data_id=_key,
                            label=_label)
                        for _key, _label in info['school_types']
                        if _key in _school_year.school_types
                    ],
                },
                'districts': {
                    _district_id: {
                        'casesBySchool': [
                            build_bar_graph_data(
                                _school.graphs.total_cases,
                                data_id=_school_id,
                                label=_school.name)
                            for (_school_id,
                                 _school) in _district.schools.items()
                        ],
                        'casesByGradeLevel': [
                            build_bar_graph_data(
                                _state.graphs.total_cases,
                                data_id=_key,
                                label=SCHOOL_TYPE_ID_NAME_MAP[_key])
                            for _key, _state in _district.school_types.items()
                        ],
                    }
                    for (_district_id,
                         _district) in _school_year.districts.items()
                },
            }
            for _school_year in school_years
        },
        'counters': {
            _school_year.year: {
                'countyWide': {
                    'districtsWithNewCases': build_counter_data(
                        _school_year.week_districts_with_cases,
                        get_value=lambda row: len(row)),
                    'schoolsWithNewCases': build_counter_data(
                        _school_year.week_schools_with_cases,
                        get_value=lambda row: len(row)),
                    'staffCases': build_counter_data(
                        _school_year.total.graphs.staff_cases,
                        delta_days=[1, 7, 14, 30]),
                    'studentCases': build_counter_data(
                        _school_year.total.graphs.student_cases,
                        delta_days=[1, 7, 14, 30]),
                },
                'districts': {
                    _district_id: {
                        'schoolsWithNewCases': build_counter_data(
                            (_school_year
                             .week_district_schools_with_cases[_district_id]),
                            get_value=lambda row: len(row)),
                        'staffCases': build_counter_data(
                            _district.graphs.staff_cases,
                            delta_days=[1, 7, 14, 30]),
                        'studentCases': build_counter_data(
                            _district.graphs.student_cases,
                            delta_days=[1, 7, 14, 30]),
                    }
                    for (_district_id,
                         _district) in _school_year.districts.items()
                },
                'schools': {
                    _school_id: {
                        'staffCases': build_counter_data(
                            _school.graphs.staff_cases,
                            delta_days=[1, 7, 14, 30]),
                        'studentCases': build_counter_data(
                            _school.graphs.student_cases,
                            delta_days=[1, 7, 14, 30]),
                    }
                    for _school_id, _school in _school_year.schools.items()
                },
            }
            for _school_year in school_years
        },
        'dates': {
            _school_year.year: {
                'first': _school_year.first_date.strftime('%Y-%m-%d'),
                'last': _school_year.last_date.strftime('%Y-%m-%d'),
                'rows': [],
            }
            for _school_year in school_years
        },
        'districts': dict(info['districts']),
        'latestRows': {},
        'maxValues': {
            _school_year.year: {
                'countyWide': {
                    'totalCases': _school_year.total.counts.total_cases,
                    'newCases': _school_year.total.max_new_cases,
                },
                'districts': {
                    _district_id: {
                        'totalCases': _district.counts.total_cases,
                        'newCases': _district.max_new_cases,
                    }
                    for (_district_id,
                         _district) in _school_year.districts.items()
                },
                'schools': {
                    _school: {
                        'totalCases': _state.counts.total_cases,
                        'newCases': _state.max_new_cases,
                    }
                    for _school, _state in _school_year.schools.items()
                },
            }
            for _school_year in school_years
        },
        'monitoringTier': bc19_dashboard['monitoringTier'],
        'reportTimestamp': bc19_dashboard['reportTimestamp'],
        'schools': {
            _district_id: {
                _school_id: _school_name
                for _school_id, _school_name in _schools.items()
            }
            for (_district_id,
                 _schools) in state.district_ids_to_schools.items()
        },
        'schoolTypes': state.district_ids_to_school_types,
        'schoolYears': [
            _school_year.year
            for _school_year in school_years
        ],
        'timelineGraphs': {
            _school_year.year: {
                'dates': _school_year.total.graphs.dates,
                'districts': {
                    _district_id: make_graph_result(_district.graphs)
                    for (_district_id,
                         _district) in _school_year.districts.items()
                },
                'schools': {
                    _school: make_graph_result(_state.graphs)
                    for _school, _state in _school_year.schools.items()
                },
                'schoolTypes': {
                    _school_type: make_graph_result(_state.graphs)
                    for (_school_type,
                         _state) in _school_year.school_types.items()
                },
                'countyWide': make_graph_result(_school_year.total.graphs),
            }
            for _school_year in school_years
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
        'parser': build_dashboard_dataset,
    },
    {
        'filename': 'bc19-schools.json',
        'min_filename': 'bc19-schools.%s.min.json' % DATASET_VERSION,
        'format': 'json',
        'local_sources': {
            'bc19_dashboard': {
                'filename': 'bc19-dashboard.json',
                'format': 'json',
            },
            'schools': {
                'filename': 'schools.json',
                'format': 'json',
            },
        },
        'parser': build_schools_dataset,
        'districts': [
            ('ccds', {
                'short_name': 'Chico Country Day School',
                'full_name': 'Chico Country Day School',
            }),
            ('csuchico', {
                'short_name': 'Chico State',
                'full_name': 'Chico State',
            }),
            ('cusd', {
                'short_name': 'Chico Unified',
                'full_name': 'Chico Unified School District',
                'source': 'http://www.chicousd.org/News/District-Wide-Safety-Info/COVID-19-Information/2021-Community-Dashboard/',
            }),
            ('dusd', {
                'short_name': 'Durham Unified',
                'full_name': 'Durham Unified School District',
                'source': 'http://durhamunified.org/dusd-covid-19-community-dashboard/',
            }),
            ('inspire', {
                'short_name': 'Inspire',
                'full_name': 'Inspire School',
                'source': 'https://docs.google.com/spreadsheets/d/1-DTOcPmoYiOK-9wPMqMFoT6D9ViFznb9H15lzx-yzBE/edit#gid=0',
            }),
            ('ocesd', {
                'short_name': 'Oroville City Elementary',
                'full_name': 'Oroville City Elementary School District',
                'source': 'https://www.ocesd.org/page/covid-community-information',
            }),
            ('ouhsd', {
                'short_name': 'Oroville Union High',
                'full_name': 'Oroville Union High School District',
                'source': 'https://www.ouhsd.org/Page/3178',
            }),
            ('puesd', {
                'short_name': 'Palermo Union Elementary',
                'full_name': 'Palermo Union Elementary School District',
                'source': 'https://drive.google.com/file/d/14vxZGZ9gsXc4-KpX0v16vk11w-qZz4Oq/view',
            }),
            ('pusd', {
                'short_name': 'Paradise Unified',
                'full_name': 'Paradise Unified School District',
                'source': 'https://www.pusdk12.org/COVID-19/Community-Dashboard/index.html',
            }),
        ],
        'school_types': [
            ('preschool', 'Preschool'),
            ('elementary', 'Elementary School'),
            ('junior_high', 'Junior High'),
            ('high_school', 'High School'),
            ('college', 'College'),
            ('other', 'Other'),
        ],
    },
]
