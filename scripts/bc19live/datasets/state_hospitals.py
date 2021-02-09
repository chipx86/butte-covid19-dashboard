DATASETS = [
    {
        'filename': 'state-hospitals-v3.csv',
        'format': 'csv',
        'url': 'https://data.ca.gov/dataset/529ac907-6ba1-4cb7-9aae-8966fc96aeef/resource/42d33765-20fd-44b8-a978-b083b7542225/download/hospitals_by_county.csv',
        'csv': {
            'match_row': lambda row: row['county'] == 'Butte',
            'validator': lambda results: results[0]['date'] == '2020-03-29',
            'sort_by': 'date',
            'unique_col': 'date',
            'columns': [
                {
                    'name': 'date',
                    'source_column': 'todays_date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {'name': 'hospitalized_covid_confirmed_patients'},
                {'name': 'hospitalized_suspected_covid_patients'},
                {'name': 'icu_covid_confirmed_patients'},
                {'name': 'icu_suspected_covid_patients'},
                {'name': 'all_hospital_beds'},
                {'name': 'icu_available_beds'},
            ],
        },
    },
]
