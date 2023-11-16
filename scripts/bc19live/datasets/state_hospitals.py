DATASETS = [
    {
        'filename': 'state-hospitals-v3.csv',
        'format': 'csv',
        'url': 'https://data.chhs.ca.gov/dataset/2df3e19e-9ee4-42a6-a087-9761f82033f6/resource/47af979d-8685-4981-bced-96a6b79d3ed5/download/covid19hospitalbycounty.csv',
        'csv': {
            'match_row': lambda row: row['county'] == 'Butte',
            'validator': lambda results: results[0]['date'] == '2020-03-29',
            'sort_by': 'date',
            'unique_col': 'date',
            'add_missing_dates': True,
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
