DATASETS = [
    {
        'filename': 'state-cases-v2.csv',
        'format': 'csv',
        'url': 'https://data.chhs.ca.gov/dataset/f333528b-4d38-4814-bebb-12db1f10f535/resource/046cdd2b-31e5-4d34-9ed3-b48cdbc4be7a/download/covid19cases_test.csv',
        'csv': {
            'match_row': lambda row: (row['area_type'] == 'County' and
                                      row['area'] == 'Butte' and
                                      row['date']),
            'sort_by': 'date',
            'columns': [
                {
                    'name': 'date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {
                    'name': 'new_cases',
                    'source_column': 'cases',
                },
                {
                    'name': 'total_cases',
                    'source_column': 'cumulative_cases',
                },
                {
                    'name': 'new_reported_cases',
                    'source_column': 'cases',
                },
                {
                    'name': 'total_reported_cases',
                    'source_column': 'cumulative_cases',
                },
                {
                    'name': 'new_deaths',
                    'source_column': 'deaths',
                },
                {
                    'name': 'total_deaths',
                    'source_column': 'cumulative_deaths',
                },
                {
                    'name': 'new_reported_deaths',
                    'source_column': 'deaths',
                },
                {
                    'name': 'total_reported_deaths',
                    'source_column': 'cumulative_deaths',
                },
                {
                    'name': 'new_tests',
                    'source_column': 'total_tests',
                },
                {
                    'name': 'total_tests',
                    'source_column': 'cumulative_total_tests',
                },
                {
                    'name': 'new_positive_tests',
                    'source_column': 'positive_tests',
                },
                {
                    'name': 'total_positive_tests',
                    'source_column': 'cumulative_positive_tests',
                },
                {
                    'name': 'new_reported_tests',
                    'source_column': 'total_tests',
                },
            ],
        },
    },
]
