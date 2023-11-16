import os
import sys
import traceback
from contextlib import contextmanager
from importlib import import_module
from itertools import chain

from bc19live.dirs import DATA_DIR
from bc19live.errors import ParseError
from bc19live.http import load_http_cache, http_get, write_http_cache
from bc19live.utils import parse_csv


#: The list of dataset module names.
DATASET_MODULE_NAMES = [
    'butte_dashboard',
    'hospital_cases',
    'state_cases',
    'state_hospitals',
    'state_tests',
    'vaccination_stats',

    # These must be last.
    'timeline',
    'bc19_dashboard',
]


def _get_urls(urls, allow_cache):
    """Return responses and up-to-date information from URLs.

    This takes a dictionary of keys to URLs and fetches each one, returning
    information on the up-to-date status of each and the response payloads.

    If any URLs fails, an error will be logged and the URL information will
    be excluded from the results.

    Args:
        urls (dict):
            The dictionary of keys to URLs.

        allow_cache (bool):
            Whether to allow a cached entry to be used.

    Returns:
        tuple:
        A tuple of:

        1. A dictionary of keys to URL result dictionaries (each with
           ``up_to_date`` and ``response`` keys).
        2. The last HTTP session instance.
    """
    results = {}
    session = None
    responses = {}
    urls_up_to_date = {}

    for url_name, url in urls.items():
        session, response = \
            http_get(url,
                     allow_cache=allow_cache,
                     session=session)

        if response.status_code == 200:
            up_to_date = False
        elif response.status_code == 304:
            up_to_date = True
        else:
            sys.stderr.write('HTTP error %s while fetching %s: %s'
                             % (response.status_code, url,
                                response.text[:3000]))
            continue

        results[url_name] = {
            'response': response,
            'up_to_date': up_to_date,
        }

    return results, session


@contextmanager
def _open_local_sources(local_sources):
    """Open one or more local sources for reading.

    This will open the sources, yield to the caller, and then close them
    again.

    Args:
        local_sources (dict):
            A mapping of keys to filenames.

    Context:
        dict:
        A mapping of keys to file pointers.
    """
    fps = {}

    for source_name, local_source in local_sources.items():
        source_filename = os.path.join(DATA_DIR,
                                       local_source['format'],
                                       local_source['filename'])

        if not os.path.exists(source_filename):
            with open(source_filename, 'w') as out_fp:
                out_fp.write('[]')

        fps[source_name] = open(source_filename, 'r')

    try:
        yield fps
    finally:
        for fp in fps.values():
            fp.close()


def main():
    """Main function for building datasets.

    This accepts names of feeds on the command line to build, as well as a
    special ``--not-timeline`` argument that excludes the ``timeline.csv``,
    ``timeline.json``, and ``timeline.min.json`` files.

    Once the options are chosen, this will run through :py:data:`DATASETS` and
    handle pulling down files via HTTP(S), running them through a parser,
    possibly building exports, and then listing the states of that feed.

    HTTP responses are cached, to minimize traffic.
    """
    DATASETS_BY_MODULE = {
        _module_name: import_module('bc19live.datasets.%s'
                                    % _module_name).DATASETS
        for _module_name in DATASET_MODULE_NAMES
    }

    DATASETS = list(chain.from_iterable(
        _dataset
        for _dataset in DATASETS_BY_MODULE.values()
    ))

    DATASET_FILENAMES = {
        _dataset['filename']
        for _dataset in DATASETS
    }

    if '--not-timeline' in sys.argv:
        feeds_to_build = DATASET_FILENAMES - {
            'timeline.csv',
            'timeline.json',
            'bc19-dashboard.json',
        }
    elif len(sys.argv) > 1:
        # Include any filenames or dataset names specified in the arguments.
        feeds_to_build = set()

        for feed_name in sys.argv[1:]:
            if feed_name in DATASET_FILENAMES:
                # This is an explicit filename.
                feeds_to_build.add(feed_name)
            elif feed_name in DATASETS_BY_MODULE:
                # This is a dataset name. Add each filename within it.
                feeds_to_build.update(
                    _dataset['filename']
                    for _dataset in DATASETS_BY_MODULE[feed_name]
                )
            else:
                sys.stderr.write('Invalid dataset/filename specified: "%s"\n'
                                 % feed_name)
                sys.exit(1)
    else:
        feeds_to_build = DATASET_FILENAMES

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
        allow_cache = os.path.exists(out_filename)
        parser = info.get('parser')
        result = None
        up_to_date = False
        skipped = False

        if parser is None and info['format'] == 'csv':
            parser = parse_csv

        try:
            if 'url' in info:
                url_results, session = _get_urls(
                    urls={
                        'main': info['url'],
                    },
                    allow_cache=allow_cache)
                url_result = url_results.get('main')

                if not url_result:
                    continue

                if url_result['up_to_date']:
                    up_to_date = True
                else:
                    result = parser(info=info,
                                    response=url_result['response'],
                                    out_filename=out_filename,
                                    session=session)
            elif 'urls' in info:
                urls = info['urls']
                urls_results, session = _get_urls(
                    urls=urls,
                    allow_cache=allow_cache)

                if len(url_results) != len(urls):
                    # One of them failed. Bail.
                    continue

                all_up_to_date = all(
                    _url_response['up_to_date']
                    for _url_response in url_responses.values()
                )

                if all_up_to_date:
                    up_to_date = True
                else:
                    responses = {
                        _key: _value['response']
                        for _key, _value in urls_results.items()
                    }

                    result = parser(info=info,
                                    responses=responses,
                                    out_filename=out_filename,
                                    session=session)
            elif 'local_source' in info:
                local_sources = {
                    'main': info['local_source'],
                }

                with _open_local_sources(local_sources) as fps:
                    result = parser(info=info,
                                    in_fp=fps['main'],
                                    out_filename=out_filename)
            elif 'local_sources' in info:
                with _open_local_sources(info['local_sources']) as fps:
                    result = parser(info=info,
                                    in_fps=fps,
                                    out_filename=out_filename)
            else:
                sys.stderr.write('Invalid feed entry: %r\n' % info)
                continue
        except ParseError as e:
            sys.stderr.write('Data parse error while building %s: %s\n'
                             % (filename, e))

            if e.row is not None:
                sys.stderr.write('Row: %r\n' % e.row)

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
