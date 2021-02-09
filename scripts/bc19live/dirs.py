import os


#: The root directory for all bc19.live files and directories.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

#: Location of the HTTP cached data file.
CACHE_FILE = os.path.join(ROOT_DIR, '.http-cache')

#: Location of the data export directory.
DATA_DIR = os.path.join(ROOT_DIR, 'htdocs', 'data')

#: Location of the CSV export directory.
CSV_DIR = os.path.join(DATA_DIR, 'csv')

#: Location of the JSON export directory.
JSON_DIR = os.path.join(DATA_DIR, 'json')
