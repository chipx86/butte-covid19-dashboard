import codecs
import csv
import json
from datetime import datetime, timedelta

from bc19live.tableau import TableauLoader
from bc19live.utils import (convert_json_to_csv,
                            parse_real,
                            safe_open_for_write)


def build_dataset(session, responses, out_filename, **kwargs):
    """Parse the state tiers dashboard and build a JSON file.

    This parses the Tableau dashboard containing information on Butte County's
    tier status, and generates JSON data that can be consumed to track which
    tier we're in and what the numbers look like.

    Args:
        session (requests.Session):
            The HTTP request session, for cookie management.

        responses (dict):
            A mapping of keys to HTTP responses.

        out_filename (str):
            The filename for the JSON file to write.

        **kwargs (dict, unused):
            Unused keyword arguments passed to this parser.

    Returns:
        bool:
        ``True`` if the file was written, or ``False`` if skipped.

    Raises:
        ParseError:
            Expected data was missing or was in an unexpected format. Detailed
            information will be in the error message.
    """
    tiers = ['Widespread', 'Substantial', 'Moderate', 'Minimal']

    results = []
    metrics_reader = csv.DictReader(
        codecs.iterdecode(responses['metrics'].iter_lines(), 'utf-8'),
        delimiter=',')
    tiers_reader = csv.DictReader(
        codecs.iterdecode(responses['tiers'].iter_lines(), 'utf-8'),
        delimiter=',')

    metric_rows = [
        row
        for row in metrics_reader
        if row['county'] == 'Butte'
    ]
    metric_rows.reverse()

    tiers_by_date = {
        row['date']: int(row['tier'])
        for row in tiers_reader
        if row['county'] == 'Butte'
    }

    prev_date = None
    prev_tier = None
    tier_effective_date = None
    prev_info = None

    for metric_row in metric_rows:
        date_str = metric_row['date']
        date = datetime.strptime(date_str, '%Y-%m-%d')

        if prev_date is not None:
            for day in range(1, (date - prev_date).days):
                results.append(dict({
                    'date': (prev_date +
                             timedelta(days=day)).strftime('%Y-%m-%d'),
                    'effective_date': tier_effective_date.strftime('%Y-%m-%d'),
                }, **prev_info))

        prev_tier = tiers_by_date.get(date_str, prev_tier)

        equity_index = parse_real(metric_row['equity_index'],
                                  allow_blank=True)

        if equity_index:
            equity_index = equity_index / 100.0

        info = {
            'adjusted_cases_per_100k': parse_real(
                metric_row['adjusted_case_rate'],
                allow_blank=True),
            'cases_per_100k': parse_real(
                metric_row['percapita_case_rate'],
                allow_blank=True),
            'equity_index': equity_index,
            'pos_rate': parse_real(
                metric_row['positivity_rate'],
                allow_blank=True),
            'status': tiers[prev_tier - 1],
        }

        if info != prev_info:
            tier_effective_date = date

        results.append(dict({
            'date': date.strftime('%Y-%m-%d'),
            'effective_date': tier_effective_date.strftime('%Y-%m-%d'),
        }, **info))

        prev_info = info
        prev_date = date

    with safe_open_for_write(out_filename) as fp:
        json.dump(
            {
                'dates': results,
            },
            fp,
            indent=2,
            sort_keys=True)


DATASETS = [
    {
        'filename': 'state-tiers.json',
        'format': 'json',
        'urls': {
            'metrics': (
                'https://raw.githubusercontent.com/datadesk/'
                'california-coronavirus-data/master/cdph-reopening-metrics.csv'
            ),
            'tiers': (
                'https://raw.githubusercontent.com/datadesk/'
                'california-coronavirus-data/master/cdph-reopening-tiers.csv'
            ),
        },
        'parser': build_dataset,
    },
    {
        'filename': 'state-tiers-v2.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'state-tiers.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Effective Date', ('effective_date',)),
            ('Status', ('status',)),
            ('New Case Rate', ('cases_per_100k',)),
            ('Adjusted New Case Rate', ('adjusted_cases_per_100k',)),
            ('Positivity Rate', ('pos_rate',)),
            ('Health Equity', ('equity_index',)),
        ],
    },
]
