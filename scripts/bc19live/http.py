import json

import requests

from bc19live.dirs import CACHE_FILE


#: The user agent that this script will identify as.
#:
#: This helps create the appearance that a browser, not a Python script, is
#: fetching content from the servers, making it less likely to be blocked or
#: to receive legacy content.
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36'
)


http_cache = {}


def load_http_cache():
    """Load the HTTP cache from disk."""
    try:
        with open(CACHE_FILE, 'r') as fp:
            http_cache.update(json.load(fp))
    except Exception:
        http_cache.clear()


def write_http_cache():
    """Write the HTTP cache to disk."""
    with open(CACHE_FILE, 'w') as fp:
        json.dump(http_cache, fp)


def http_get(url, allow_cache=True, session=None):
    """Perform a HTTP GET request to a server.

    This will handle looking up and storing cache details, along with setting
    up session management and standard headers.

    Args:
        url (str):
            The URL to retrieve.

        allow_cache (bool, optional):
            Whether to allow HTTP cache management.

        session (requests.Session, optional):
            An existing session to use. If not provided, one will be created.

    Returns:
        tuple:
        A 2-tuple containing:

        1. The requests session.
        2. The response.
    """
    if session is None:
        session = requests.Session()

    session.headers['User-Agent'] = USER_AGENT

    headers = {}

    if allow_cache and url in http_cache:
        try:
            headers['If-None-Match'] = http_cache[url]['etag']
        except KeyError:
            pass

    response = session.get(url, headers=headers)

    if response.headers.get('etag') and response.status_code == 200:
        http_cache[url] = {
            'etag': response.headers['etag'],
        }

    return session, response


