_note_map = {
    'staff_confirmed_cases_note': 'd',
    'patients_confirmed_cases_note': 'a',
    'staff_deaths_note': 'f',
    'patients_deaths_note': 'c',
}

def _gen_note(row, src_name, col_info, **kwargs):
    note_ids = row['note'].split(' ')
    col_note_id = _note_map[src_name]

    if col_note_id in note_ids:
        return '<11'

    return ''


def _normalize_count(row, src_name, col_info, **kwargs):
    value = row[src_name]

    if value == '':
        return 1

    return int(float(value))


DATASETS = [
    {
        'filename': 'skilled-nursing-facilities-v3.csv',
        'format': 'csv',
        #'url': 'https://raw.githubusercontent.com/datadesk/california-coronavirus-data/master/cdph-skilled-nursing-facilities.csv',
        'url': 'https://data.chhs.ca.gov/dataset/7759311f-1aa8-4ff6-bfbb-ba8f64290ae2/resource/d4d68f74-9176-4969-9f07-1546d81db5a7/download/covid19datanursinghome.csv',
        'csv': {
            'match_row': lambda row: (
                row['county'].upper() == 'BUTTE' and
                row['as_of_date'] not in ('2020-04-21', '2020-04-22',
                                          '2020-04-23')
            ),
            'validator': lambda results: results[0]['date'] == '2020-04-24',
            'sort_by': ('date', 'name'),
            'unique_col': ('date', 'name'),
            'add_missing_dates': True,
            'columns': [
                {
                    'name': 'date',
                    'source_column': 'as_of_date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {
                    'name': 'name',
                    'source_column': 'facility_name',
                    'transform_func': lambda row, src_name, **kwargs: (
                        row[src_name].upper()
                    ),
                },
                {
                    'name': 'staff_confirmed_cases',
                    'source_column': 'total_health_care_worker_cases',
                    'transform_func': _normalize_count,
                },
                {
                    'name': 'patients_confirmed_cases',
                    'source_column': 'total_resident_cases',
                    'transform_func': _normalize_count,
                },
                {
                    'name': 'staff_confirmed_cases_note',
                    'transform_func': _gen_note,
                },
                {
                    'name': 'patients_confirmed_cases_note',
                    'transform_func': _gen_note,
                },
                {
                    'name': 'staff_deaths',
                    'source_column': 'total_health_care_workers_deaths',
                    'transform_func': _normalize_count,
                },
                {
                    'name': 'patients_deaths',
                    'source_column': 'total_resident_deaths',
                    'transform_func': _normalize_count,
                },
                {
                    'name': 'staff_deaths_note',
                    'transform_func': _gen_note,
                },
                {
                    'name': 'patients_deaths_note',
                    'transform_func': _gen_note,
                },
            ],
        },
    },
]
