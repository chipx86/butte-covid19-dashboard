DATASETS = [
    {
        'filename': 'skilled-nursing-facilities-v3.csv',
        'format': 'csv',
        'url': 'https://raw.githubusercontent.com/datadesk/california-coronavirus-data/master/cdph-skilled-nursing-facilities.csv',
        'csv': {
            'match_row': lambda row: (
                row['county'] == 'Butte' and
                row['date'] not in ('2020-04-21', '2020-04-22', '2020-04-23')
            ),
            'validator': lambda results: results[0]['date'] == '2020-04-24',
            'sort_by': 'date',
            'unique_col': ('date', 'name'),
            'columns': [
                {
                    'name': 'date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {'name': 'name'},
                {'name': 'staff_confirmed_cases'},
                {'name': 'patients_confirmed_cases'},
                {'name': 'staff_confirmed_cases_note'},
                {'name': 'patients_confirmed_cases_note'},
                {'name': 'staff_deaths'},
                {'name': 'patients_deaths'},
                {'name': 'staff_deaths_note'},
                {'name': 'patients_deaths_note'},
            ],
        },
    },
]
