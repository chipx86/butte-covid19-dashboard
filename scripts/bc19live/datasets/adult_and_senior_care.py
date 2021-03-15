DATASETS = [
    {
        'filename': 'adult-and-senior-care.csv',
        'format': 'csv',
        'url': (
            'https://raw.githubusercontent.com/datadesk/california-coronavirus-data/master/cdph-adult-and-senior-care-facilities.csv'
        ),
        'csv': {
            'match_row': lambda row: row['county'] == 'Butte',
            'sort_by': 'date',
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

