import os
import sys
import traceback
from importlib import import_module
from itertools import chain

from bc19live.dirs import DATA_DIR
from bc19live.errors import ParseError
from bc19live.http import load_http_cache, http_get, write_http_cache
from bc19live.utils import parse_csv


#: The list of dataset module names.
DATASET_MODULE_NAMES = [
    'butte_county_jail',
    'butte_dashboard',
    'cusd',
    'hospital_cases',
    'oroville_union_high_district',
    'skilled_nursing_facilities',
    'state_cases',
    'state_hospitals',
    'state_region_icu_pct',
    'state_resources',
    'state_tiers',
    'stay_at_home',
    'timeline',
]


def main():
    """Main function for building datasets.

    This accepts names of feeds on the command line to build, as well as a
    special ``-not-timeline`` argument that excludes the ``timeline.csv``,
    ``timeline.json``, and ``timeline.min.json`` files.

    Once the options are chosen, this will run through :py:data:`DATASETS` and
    handle pulling down files via HTTP(S), running them through a parser,
    possibly building exports, and then listing the states of that feed.

    HTTP responses are cached, to minimize traffic.
    """
    dataset_modules = [
        import_module('bc19live.datasets.%s' % module_name)
        for module_name in DATASET_MODULE_NAMES
    ]

    DATASETS = list(chain.from_iterable(
        dataset_module.DATASETS
        for dataset_module in dataset_modules
    ))

    if '--not-timeline' in sys.argv:
        feeds_to_build = {
            feed['filename']
            for feed in DATASETS
        } - {'timeline.csv', 'timeline.json'}
    elif len(sys.argv) > 1:
        feeds_to_build = set(sys.argv[1:])
    else:
        feeds_to_build = {
            feed['filename']
            for feed in DATASETS
        }

    # Load in the stored HTTP cache, if it exists.
    load_http_cache()

    for info in DATASETS:
        filename = info['filename']

        if filename not in feeds_to_build:
            continue

        out_dir = os.path.join(DATA_DIR, info['format'])

        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        out_filename = os.path.join(out_dir, filename)
        parser = info.get('parser')
        result = None
        up_to_date = False
        skipped = False

        if parser is None and info['format'] == 'csv':
            parser = parse_csv

        try:
            if 'url' in info:
                url = info['url']

                session, response = \
                    http_get(url, allow_cache=os.path.exists(out_filename))

                if response.status_code == 200:
                    result = parser(info=info,
                                    response=response,
                                    out_filename=out_filename,
                                    session=session)
                elif response.status_code == 304:
                    up_to_date = True
                else:
                    sys.stderr.write('HTTP error %s while fetching %s: %s'
                                     % (response.status_code, filename,
                                        response.text))
                    continue
            elif 'urls' in info:
                urls = info['urls']
                session = None
                responses = {}
                urls_up_to_date = {}

                for url_name, url in urls.items():
                    session, response = \
                        http_get(url,
                                 allow_cache=os.path.exists(out_filename),
                                 session=session)

                    if response.status_code == 200:
                        urls_up_to_date[url_name] = False
                    elif response.status_code == 304:
                        urls_up_to_date[url_name] = True
                    else:
                        sys.stderr.write('HTTP error %s while fetching %s: %s'
                                         % (response.status_code, filename,
                                            response.text))
                        continue

                    responses[url_name] = response

                if len(responses) != len(urls):
                    # One of them failed. Bail.
                    continue
                elif all(urls_up_to_date.values()):
                    up_to_date = True
                else:
                    result = parser(info=info,
                                    responses=responses,
                                    out_filename=out_filename,
                                    session=session)
            elif 'local_source' in info:
                local_source = info['local_source']
                source_filename = os.path.join(DATA_DIR, local_source['format'],
                                               local_source['filename'])

                if not os.path.exists(source_filename):
                    with open(source_filename, 'w') as out_fp:
                        out_fp.write('[]')

                with open(source_filename, 'r') as in_fp:
                    result = parser(info=info,
                                    in_fp=in_fp,
                                    out_filename=out_filename)
            else:
                sys.stderr.write('Invalid feed entry: %r\n' % info)
                continue
        except ParseError as e:
            sys.stderr.write('Data parse error while building %s: %s\n'
                             % (filename, e))
            continue
        except Exception as e:
            sys.stderr.write('Unexpected error while building %s: %s\n'
                             % (filename, e))
            traceback.print_exc()
            continue

        skipped = (result is False)

        if up_to_date:
            print('Up-to-date: %s' % out_filename)
        elif skipped:
            print('Skipped %s' % out_filename)
        else:
            print('Wrote %s' % out_filename)


    # Write the new HTTP cache.
    write_http_cache()
