DATASETS = [
    {
        'filename': 'state-cases.csv',
        'format': 'csv',
        'url': (
            'https://data.ca.gov/dataset/590188d5-8545-4c93-a9a0-e230f0db7290/'
            'resource/926fd08f-cc91-4828-af38-bd45de97f8c3/download/'
            'statewide_cases.csv'
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
                {'name': 'totalcountconfirmed'},
                {'name': 'newcountconfirmed'},
                {'name': 'totalcountdeaths'},
                {'name': 'newcountdeaths'},
            ],
        },
    },
]
