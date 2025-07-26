from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from bc19live.utils import (convert_json_to_csv,
                            safe_open_for_write)

if TYPE_CHECKING:
    import io
    from collections.abc import Mapping
    from typing import Any

    import requests


BASELINE_MONTHS = 12
MIN_BASELINE_COUNT = 5  # Minimum data points needed for baseline


def build_dataset(
    session: requests.Session,
    response: requests.Response,
    out_filename: str,
    **kwargs,
) -> None:
    data = json.loads(response.text)

    with open(out_filename, 'w') as fp:
        fp.write(json.dumps(sorted(
            data['result']['records'],
            key=lambda record: (
                (datetime.strptime(record['test_result_date'], '%m/%d/%Y')
                 .isoformat())
                if record['test_result_date']
                else ''
            )
        )))


def build_wastewater_levels(
    info: Mapping[str, Any],
    in_fp: io.IOBase,
    out_filename: str,
    **kwargs,
) -> None:
    reader = csv.DictReader(in_fp,
                            delimiter=',')

    # Read the historical wastewater data.
    rows_data: list[dict[str, Any]] = [
        {
            **row,
            'pcr_target_avg_conc': float(row['pcr_target_avg_conc']),
            'sample_collect_date': datetime.strptime(
                row['sample_collect_date'], '%Y-%m-%d'),
        }
        for row in reader
    ]

    # Group the data.
    grouped_data = defaultdict(list)

    for row in rows_data:
        key = (
            row['site_id'],
            row['data_source'],
            row['pcr_target'],
            row['major_lab_method'],
            row['pcr_target_units'],
        )
        grouped_data[key].append(row)

    # Compute the wastewater levels.
    results = []

    for key, rows in grouped_data.items():
        rows.sort(key=lambda row: row['sample_collect_date'])

        # Build a lookup by anchor date to avoid recomputing baselines
        # repeatedly.
        anchor_windows: dict[datetime, tuple[float, float] | None] = {}

        for row in rows:
            sample_date = row['sample_collect_date']

            year = sample_date.year

            if sample_date.month < 7:
                anchor_date = datetime(year, 1, 1)
            else:
                anchor_date = datetime(year, 7, 1)

            baseline_window_start = anchor_date - timedelta(days=365)

            # Cache baseline stats per anchor period
            if anchor_date not in anchor_windows:
                baseline_rows = [
                    x
                    for x in rows
                    if (baseline_window_start <=
                        x['sample_collect_date'] <
                        anchor_date)
                ]

                log_concs = [
                    math.log10(x['pcr_target_avg_conc'])
                    for x in baseline_rows
                    if x['pcr_target_avg_conc'] > 0
                ]

                if len(log_concs) < MIN_BASELINE_COUNT:
                    anchor_windows[anchor_date] = None  # not enough data
                else:
                    log_concs.sort()

                    percentile_index = len(log_concs) * 0.10
                    lower = int(math.floor(percentile_index))
                    upper = int(math.ceil(percentile_index))

                    if lower == upper:
                        baseline = log_concs[lower]
                    else:
                        frac = percentile_index - lower
                        baseline = (
                            (log_concs[lower] * (1 - frac)) +
                            (log_concs[upper] * frac)
                        )

                    std_dev = statistics.stdev(log_concs)
                    anchor_windows[anchor_date] = (baseline, std_dev)

            baseline_data = anchor_windows.get(anchor_date)

            if baseline_data is None:
                # Skip this sample, no valid baseline.
                continue

            baseline, std_dev = baseline_data

            if row['pcr_target_avg_conc'] <= 0:
                # Invalid value.
                continue

            log_val = math.log10(row['pcr_target_avg_conc'])

            if std_dev != 0:
                z = (log_val - baseline) / std_dev
            else:
                z = 0

            wval = math.exp(z)

            if wval <= 1.5:
                level = 'Very Low'
            elif wval <= 3:
                level = 'Low'
            elif wval <= 4.5:
                level = 'Moderate'
            elif wval <= 8:
                level = 'High'
            else:
                level = 'Very High'

            results.append({
                **row,
                'WVAL': round(wval, 3),
                'Z': round(z, 3),
                'activity_level': level,
                'baseline_anchor': anchor_date.date(),
                'baseline_window_start': baseline_window_start.date(),
                'log_conc': round(log_val, 3),
            })

    results.sort(key=lambda row: row['sample_collect_date'])

    # Output the results.
    with safe_open_for_write(out_filename) as out_fp:
        writer = csv.DictWriter(
            out_fp,
            fieldnames=[
                'test_result_date',
                'sample_collect_date',
                'sample_collect_time',
                'label_name',
                'wwtp_name',
                'site_id',
                'data_source',
                'flow_rate',
                'sample_location',
                'sample_location_specify',
                'population_served',
                'pcr_target',
                'pcr_target_units',
                'pcr_target_avg_conc',
                'pcr_target_std_error',
                'pcr_target_cl_95_lo',
                'pcr_target_cl_95_up',
                'pcr_target_below_lod',
                'major_lab_method',
                'rec_eff_target_name',
                'rec_eff_spike_matrix',
                'rec_eff_spike_conc',
                'lod_sewage',
                'WVAL',
                'Z',
                'activity_level',
                'baseline_anchor',
                'baseline_window_start',
                'log_conc',
            ])
        writer.writeheader()

        for row_result in results:
            writer.writerow(row_result)


DATASETS = [
    {
        'filename': 'wastewater-v2.json',
        'format': 'json',
        'url': 'https://data.chhs.ca.gov/api/3/action/datastore_search_sql?sql=SELECT%20%2A%20from%20%222742b824-3736-4292-90a9-7fad98e94c06%22%20WHERE%20%22pcr_target%22%3D%27sars-cov-2%27%20AND%20%22county_treatmentplant%22%3D%27Butte%27',
        'parser': build_dataset,
    },
    {
        'filename': 'wastewater-v2.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'wastewater-v2.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'rows_key': 'results.records',
        'match_row': lambda row: (
            row['test_result_date'] is not None
        ),
        'key_map': [
            ('test_result_date', {
                'type': 'date',
                'format': '%m/%d/%Y',
            }),
            ('sample_collect_date', {
                'type': 'date',
                'format': '%m/%d/%Y',
            }),
            ('sample_collect_time', ('sample_collect_time',)),
            ('label_name', ('label_name',)),
            ('wwtp_name', ('wwtp_name',)),
            ('site_id', ('site_id',)),
            ('data_source', ('data_source',)),
            ('flow_rate', ('flow_rate',)),
            ('sample_location', ('sample_location',)),
            ('sample_location_specify', ('sample_location_specify',)),
            ('population_served', ('population_served',)),
            ('pcr_target', ('pcr_target',)),
            ('pcr_target_units', ('pcr_target_units',)),
            ('pcr_target_avg_conc', ('pcr_target_avg_conc',)),
            ('pcr_target_std_error', ('pcr_target_std_error',)),
            ('pcr_target_cl_95_lo', ('pcr_target_cl_95_lo',)),
            ('pcr_target_cl_95_up', ('pcr_target_cl_95_up',)),
            ('pcr_target_below_lod', ('pcr_target_below_lod',)),
            ('major_lab_method', ('major_lab_method',)),
            ('rec_eff_target_name', ('rec_eff_target_name',)),
            ('rec_eff_spike_matrix', ('rec_eff_spike_matrix',)),
            ('rec_eff_spike_conc', ('rec_eff_spike_conc',)),
            ('lod_sewage', ('lod_sewage',)),
        ],
    },
    {
        'filename': 'wastewater-levels.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'wastewater-v2.csv',
            'format': 'csv',
        },
        'parser': build_wastewater_levels,
    },
    {
        'filename': 'cdc-wastewater-levels.csv',
        'format': 'csv',
        'url': 'https://www.cdc.gov/wcms/vizdata/NCEZID_DIDRI/SC2/nwsssc2sitemapnocoords.csv',
        'csv': {
            'match_row': lambda row: (
                row['State/Territory'] == 'California' and
                row['Counties_Served'] == 'Butte'
            ),
            'add_missing_dates': True,
            'columns': [
                {
                    'name': 'date',
                    'source_column': 'date_updated',
                    'type': 'date',
                    'format': '%Y-%m-%dT%H:%M:%S.%fZ',
                },
                {
                    'name': 'sewershed_id',
                    'source_column': 'Sewershed_ID',
                },
                {
                    'name': 'location',
                    'source_column': 'Sewershed_ID',
                    'transform_func': (
                        lambda row, src_name, data_type, col_info:
                            col_info['locations'].get(row[src_name],
                                                      'Unknown')
                    ),
                    'locations': {
                        'ID:95': 'Oroville',
                        'ID:96': 'Chico',
                    },
                },
                {
                    'name': 'level',
                    'source_column': 'WVAL_Category',
                },
                {
                    'name': 'population_served',
                    'source_column': 'Population_Served',
                },
                {
                    'name': 'reporting_week',
                    'source_column': 'Reporting_Week',
                },
            ],
        },
    },
]
