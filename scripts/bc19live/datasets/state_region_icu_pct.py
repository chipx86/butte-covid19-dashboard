from bc19live.utils import convert_json_to_csv


DATASETS = [
    {
        'filename': 'state-region-icu-pct.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'stay-at-home.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
        ] + [
            (region, ('regions', region_key, 'icu_beds_available_pct'))
            for region, region_key in (('Bay Area', 'bay_area'),
                                       ('Greater Sacramento',
                                        'greater_sacramento'),
                                       ('Northern California',
                                        'northern_california'),
                                       ('San Joaquin Valley',
                                        'san_joaquin_valley'),
                                       ('Southern California',
                                        'southern_california'))
        ],
    },
]
