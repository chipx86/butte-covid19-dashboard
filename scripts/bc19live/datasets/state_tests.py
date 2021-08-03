DATASETS = [
    {
        'filename': 'state-tests.csv',
        'format': 'csv',
        'url': 'https://data.chhs.ca.gov/dataset/f333528b-4d38-4814-bebb-12db1f10f535/resource/046cdd2b-31e5-4d34-9ed3-b48cdbc4be7a/download/covid19cases_test.csv',
        'csv': {
            'match_row': lambda row: (row['area'] == 'Butte' and
                                      row['date'] != ''),
            'sort_by': 'date',
            'columns': [
                {
                    'name': 'date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {
                    'name': 'total_tests',
                    'type': 'real',
                },
                {
                    'name': 'cumulative_total_tests',
                    'type': 'real',
                },
                {
                    'name': 'positive_tests',
                    'type': 'real',
                },
                {
                    'name': 'cumulative_positive_tests',
                    'type': 'real',
                },
                {
                    'name': 'reported_tests',
                    'type': 'real',
                },
            ],
        },
    },
]
