DATASETS = [
    {
        'filename': 'wastewater.csv',
        'format': 'csv',
        'url': 'https://data.cdc.gov/resource/2ew6-ywp6.csv?$query=SELECT%0A%20%20%60date_start%60%2C%0A%20%20%60date_end%60%2C%0A%20%20%60wwtp_id%60%2C%0A%20%20%60reporting_jurisdiction%60%2C%0A%20%20%60sample_location%60%2C%0A%20%20%60sample_location_specify%60%2C%0A%20%20%60key_plot_id%60%2C%0A%20%20%60county_names%60%2C%0A%20%20%60population_served%60%2C%0A%20%20%60ptc_15d%60%2C%0A%20%20%60detect_prop_15d%60%2C%0A%20%20%60percentile%60%2C%0A%20%20%60sampling_prior%60%2C%0A%20%20%60first_sample_date%60%0AWHERE%20caseless_eq%28%60county_fips%60%2C%20%2206007%22%29%0AORDER%20BY%20%60date_end%60%20ASC%20NULL%20LAST',
        'csv': {
            'columns': [
                {
                    'name': 'date_start',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {
                    'name': 'date_end',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {'name': 'wwtp_id'},
                {'name': 'sample_location'},
                {'name': 'sample_location_specify'},
                {'name': 'key_plot_id'},
                {'name': 'population_served'},
                {'name': 'ptc_15d'},
                {'name': 'detect_prop_15d'},
                {'name': 'percentile'},
                {'name': 'sampling_prior'},
                {'name': 'first_sample_date'},
            ],
        },
    }
]
