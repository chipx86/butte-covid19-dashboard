#!/usr/bin/env python3
"""Builds datasets for the bc19.live dashboard from public COVID-19 sources.

This script is responsible for going through a number of public sources,
consisting of CSV files, JSON feeds, Tableau dashboards, and web pages, and
building/validating new datasets that can be pulled in to analyze the COVID-19
situation in Butte County.
"""

import codecs
import csv
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from urllib.parse import quote

import requests


#: Location of the HTTP cached data file.
CACHE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                          '.http-cache'))

#: Location of the data export directory.
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        '..', 'htdocs', 'data'))

#: Location of the CSV export directory.
CSV_DIR = os.path.join(DATA_DIR, 'csv')

#: Location of the JSON export directory.
JSON_DIR = os.path.join(DATA_DIR, 'json')


http_cache = {}


#: The user agent that this script will identify as.
#:
#: This helps create the appearance that a browser, not a Python script, is
#: fetching content from the servers, making it less likely to be blocked or
#: to receive legacy content.
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36'
)


class ParseError(Exception):
    """Error parsing or extracting data from a dataset."""


class TableauPresModel(object):
    """Wrapper around a Tableau dashboard's presentation model.

    The presentation model is a JSON structure containing all the data that's
    used to render a Tableau dashboard. It's broken down into panes containing
    rows and columns, which themselves contain labels, data types, and
    references to data in typed, deduplicated data dictionaries.

    This class helps provide easy access to the data, allowing the caller to
    think about the information they want to retrieve, rather than the parsing
    gymanstics needed to get it.
    """

    def __init__(self, loader, payload):
        """Initialize the presentation model.

        Args:
            loader (TableauLoader):
                The parent Tableau dashboard loader that created this.

            payload (dict):
                The deserialized presentation model data.
        """
        self.loader = loader
        self.payload = payload

    @property
    def all_data_columns(self):
        """The list of all data columns in this model.

        Data columns contain metadata on the data (such as a data type) that
        backs the presentation model, and references to the pane(s) containing
        the data value(s).

        Type:
            list of dict
        """
        return (
            self.payload
            ['presModelHolder']
            ['genVizDataPresModel']
            ['paneColumnsData']
            ['vizDataColumns']
        )

    @property
    def all_pane_columns(self):
        """The list of all pane column lists in this model.

        Each entry here is a list of pane columns of a given pane index.
        The entry itself is really the list of pane columns, and contains
        information used to locate data values for a column.

        Type:
            list of list
        """
        return (
            self.payload
            ['presModelHolder']
            ['genVizDataPresModel']
            ['paneColumnsData']
            ['paneColumnsList']
        )

    def get_pane_columns(self, pane_index):
        """Return all pane columns for a given pane index.

        Args:
            pane_index (int):
                The index for the pane.

        Returns:
            list of dict:
            The list of pane columns.

        Raises:
            IndexError:
                The pane index is invalid.
        """
        return self.all_pane_columns[pane_index]['vizPaneColumns']

    def get_mapped_col_data(self, cols):
        """Return data from the model based on the given criteria.

        This allows callers to specify a list of columns to extract data
        from, giving the expected field caption, data type, value index,
        and the desired key for the resulting dictionary. It takes care of
        parsing the appropriate data from the presentation model, validating
        it, and generating results.

        Args:
            cols (dict):
                A dictionary mapping field captions to query information.
                The query information should contain:

                ``data_type`` (str):
                    The expected data type for the column.

                ``normalize`` (callable, optional):
                    A function used to normalize the value(s).

                ``result_key`` (str, optional):
                    The key to set in the resulting dictionary. This defaults
                    to the field caption.

                ``value_index`` (int, optional):
                    The index in the values list for the column. If not
                    provided, a list of all values are returned.

        Returns:
            dict:
            A dictionary of results, mapping keys to values.

        Raises:
            ParseError:
                The data type for a column did not match, or keys were missing.
                Details are in the error message.
        """
        data_dicts = self.loader.get_data_dicts()
        result = {}

        for col_data in self.all_data_columns:
            caption = col_data.get('fieldCaption')

            if caption and caption in cols:
                col_info = cols[caption]
                data_type = col_data.get('dataType')

                if data_type != col_info['data_type']:
                    raise ParseError(
                        'Expected data type "%s" for column "%s", but got '
                        '"%s" instead.'
                        % (col_info['data_type'], caption, data_type))

                data_type_dict = data_dicts.get(data_type, [])
                cstring_dict = data_dicts['cstring']
                col_index = col_data['columnIndices'][0]
                pane_index = col_data['paneIndices'][0]

                result_key = col_info.get('result_key', caption)
                pane_columns = self.get_pane_columns(pane_index)
                value_index = col_info.get('value_index')
                normalize = col_info.get('normalize', lambda value: value)

                alias_indices = pane_columns[col_index]['aliasIndices']

                def _get_value(alias_index):
                    # I may be wrong, but I believe if an alias index is < 0,
                    # then it's a reference to a display for a value in the
                    # cstring data dict instead. It has to be converted to a
                    # positive value and then converted from a 1-based index
                    # to a 0-based index.
                    if alias_index < 0:
                        return data_dicts['cstring'][-alias_index - 1]
                    else:
                        return data_type_dict[alias_index]

                if value_index is None:
                    result[result_key] = [
                        normalize(_get_value(i))
                        for i in alias_indices
                    ]
                else:
                    result[result_key] = normalize(
                        _get_value(alias_indices[value_index]))

        expected_keys = set(
            col_info.get('result_key', col_key)
            for col_key, col_info in cols.items()
        )

        missing_keys = expected_keys - set(result.keys())

        if missing_keys:
            raise ParseError('The following keys could not be found: %s'
                             % ', '.join(sorted(missing_keys)))

        return result


class TableauLoader(object):
    """Loads a public Tableau workbook and parses results.

    This is used to extract data from a public Tableau workbook/dashboard that
    doesn't otherwise offer any kind of exportable CSV/JSON/etc. dataaset.

    It works by pretending to be a web browser, fetching the various data
    payloads that the server sends, parsing it, and providing helpful accessors
    so the caller can easily fetch information from it.
    """

    def __init__(self, session, owner, sheet, orig_response):
        """Initialize the loader.

        Once initialized, the caller is responsible for calling
        :py:meth:`bootstrap` to load the data.

        Args:
            session (requests.Session):
                The existing HTTP session, used for cookie management.

            owner (str):
                The owner name for the Tableau workbook, as found in the URL.

            sheet (str):
                The sheet name for the Tableau workbook, as found in the URL.

            orig_response (requests.Response):
                The HTTP response used to fetch the initial Tableau workbook
                webpage. This is used to fetch metadata used to fetch the
                related payloads.
        """
        self.session = session
        self.owner = owner
        self.sheet = sheet
        self.sheet_urlarg = self.sheet.replace(' ', '')
        self.session_id = orig_response.headers['x-session-id']
        self.referer = orig_response.url
        self.raw_bootstrap_payload1 = None
        self.raw_bootstrap_payload2 = None
        self.base_url = None
        self._data_pres_model_map = None
        self._data_dicts = {}

    def get_workbook_metadata(self):
        """Return metadata on the workbook.

        The first time this is called, an HTTP request will be performed to
        fetch the metadata. Subsequent calls will return cached data.

        Returns:
            dict:
            The workbook metadata.
        """
        if not hasattr(self, '_workbook_metadata'):
            response = self.session.get(
                'https://public.tableau.com/profile/api/workbook/%s'
                % self.owner)

            self._workbook_metadata = response.json()

        return self._workbook_metadata

    def get_last_update_date(self):
        """Return the date the workbook was last updated.

        The first time this is called, an HTTP request will be performed to
        fetch the metadata. Subsequent calls will return cached data.

        Returns:
            datetime.datetime:
            The date the workbook was last updated.
        """
        metadata = self.get_workbook_metadata()
        return datetime.fromtimestamp(metadata['lastUpdateDate'] / 1000)

    def bootstrap(self, extra_params={}):
        """Bootstrap the loader.

        This is required after initializing the loader. It will initiate an
        HTTP request to fetch the two payloads backing the workbook, parsing
        the raw data behind those payloads out and storing them for later
        deserialization.

        Args:
            extra_params (dict, optional):
                Additional HTTP POST data to pass, used to specify additional
                settings the caller needs to fetch the workbook.
        """
        self.base_url = ('https://public.tableau.com/vizql/w/%s/v/%s/'
                         % (self.owner, self.sheet_urlarg))

        response = self._session_post(
            path='bootstrapSession/sessions/%s' % self.session_id,
            data=dict({
                'sheet_id': self.sheet,
            }, **extra_params))

        # The response contains two JSON payloads, each prefixed by a length.
        data = response.text
        i = data.find(';')
        length = int(data[:i])
        self.raw_bootstrap_payload1 = data[i + 1:length + i + 1]

        data = data[length + i + 1:]
        i = data.find(';')
        length = int(data[:i])
        self.raw_bootstrap_payload2 = data[i + 1:length + i + 1]

        self.bootstrap_payload2 = json.loads(self.raw_bootstrap_payload2)

        pres_model_map = (
            self.bootstrap_payload2
            ['secondaryInfo']
            ['presModelMap']
        )

        self._data_pres_model_map = (
            pres_model_map
            ['vizData']
            ['presModelHolder']
            ['genPresModelMapPresModel']
            ['presModelMap']
        )

        self._data_segments = (
            pres_model_map
            ['dataDictionary']
            ['presModelHolder']
            ['genDataDictionaryPresModel']
            ['dataSegments']
        )

        self._build_data_dicts()

    def set_parameter_value(self, name, value):
        """Set a parameter value on the server.

        This will trigger a reload of any new data dictionary or presentation
        model information.

        Note:
            The data this reloads is limited to the needs of this script, and
            is not complete. It also makes assumptions that may not always be
            true. If you're using this in your own script, you may have work
            to do here.

        Args:
            name (str):
                The name of the parameter to set.

            value (str):
                The parameter value.
        """
        response = self._session_post(
            path='sessions/%s/commands/tabdoc/set-parameter-value'
                 % self.session_id,
            data={
                'globalFieldName': name,
                'valueString': value,
                'useUsLocale': 'false',
            })

        data = response.json()
        app_pres_model_data = (
            data
            ['vqlCmdResponse']
            ['layoutStatus']
            ['applicationPresModel']
        )

        if 'dataDictionary' in app_pres_model_data:
            # Append the new data dictionaries.
            self._data_segments.update(
                app_pres_model_data
                ['dataDictionary']
                ['dataSegments']
            )
            self._build_data_dicts()

        # Update all the presentation models for the new state.
        model_map = self._data_pres_model_map
        zones = (
            app_pres_model_data
            ['workbookPresModel']
            ['dashboardPresModel']
            ['zones']
        )

        for zone_id, zone_info in zones.items():
            try:
                worksheet = zone_info['worksheet']
                viz_data = zone_info['presModelHolder']['visual']['vizData']
            except KeyError:
                continue

            model_map[worksheet]['presModelHolder']['genVizDataPresModel'] = \
                viz_data

    def get_data_dicts(self, expected_counts={}):
        """Return the data dictionaries from the workbook.

        Args:
            expected_counts (dict, optional):
                The expected number of items in each typed data dictionary,
                for validation purposes.

        Returns:
            dict:
            A dictionary mapping data types to lists of values.
        """
        data_dicts = self._data_dicts

        for key, count in expected_counts.items():
            value_count = len(data_dicts[key])

            if value_count != count:
                raise ParseError('Unexpected number of %s data values: %s'
                                 % (key, value_count))

        return data_dicts

    def get_pres_model(self, model_key):
        """Return a presentation model from the workbook.

        Args:
            model_key (str):
                The key identifying the presentation model.

        Returns:
            TableauPresModel:
            The resulting presentation model.

        Raises:
            ParseError:
                The presentation model could not be found.
        """
        try:
            return TableauPresModel(
                loader=self,
                payload=self._data_pres_model_map[model_key])
        except KeyError:
            raise ParseError('Could not find "%s" in presModelMap' % model_key)

    def get_mapped_col_data(self, models_to_cols):
        """Return data from presentation models based on the given criteria.

        This wraps :py:meth:`TableauPresModel.get_mapped_col_data`, allowing
        data to be returned from multiple presentation models at once.

        Args:
            models_to_cols (dict):
                A dictionary of presentation model names to query dictionaries
                (as would normally be provided to
                :py:meth:`TableauPresModel.get_mapped_col_data`).

        Returns:
            dict:
            A dictionary of results, mapping keys to values.

        Raises:
            ParseError:
                The data type for a column did not match, or keys were missing,
                or a presentation model was missing. Details are in the error
                message.
        """
        result = {}

        for model_key, cols in models_to_cols.items():
            pres_model = self.get_pres_model(model_key)
            result.update(pres_model.get_mapped_col_data(cols))

        return result

    def _build_data_dicts(self):
        """Build type-mapped data dictionaries from official data segments.

        This will loop through all data segments, building a single normalized
        dictionary mapping data dictionary types to lists of values.

        The resulting dictionary is updated in-place. Callers do not need to
        re-fetch a data dictionary.

        This must be called any time the list of data segments change in any
        way.
        """
        new_data_dicts = {}

        for key, segment_info in sorted(self._data_segments.items(),
                                        key=lambda pair: int(pair[0])):
            for item in segment_info['dataColumns']:
                new_data_dicts.setdefault(item['dataType'], []).extend(
                    item['dataValues'])

        # Update in-place so existing references continue to work.
        self._data_dicts.clear()
        self._data_dicts.update(new_data_dicts)

    def _session_post(self, path, data={}):
        """Perform an HTTP POST for the Tableau session.

        Args:
            path (str):
                The path to append to the base URL.

            data (dict, optional):
                HTTP POST data to send.

        Returns:
            requests.Response:
            The resulting HTTP response.
        """
        return self.session.post(
            '%s%s' % (self.base_url, path),
            data=data,
            headers={
                'Accept': 'text/javascript',
                'Referer': self.referer,
                'X-Requested-With': 'XMLHttpRequest',
                'x-tsi-active-tab': self.sheet,
                'x-tsi-supports-accepted': 'true',
            })


@contextmanager
def safe_open_for_write(filename):
    """Safely open a file for writing.

    This will write to a temp file, and then rename it to the destination
    file upon completion. This ensures that anything reading the file will not
    receive an empty, partially-written, or truncated file.

    Args:
        filename (str):
            The name of the file to write.

    Context:
        object:
        The file pointer.
    """
    temp_filename = '%s.tmp' % filename

    with open(temp_filename, 'w') as fp:
        yield fp

    os.rename(temp_filename, filename)


def convert_csv_to_tsv(filename):
    """Convert a CSV file to TSV.

    This provides an alternative feed in the event that Google Sheets cannot
    read from a CSV file (a bug that seems to have been introduced the
    week of December 7).

    Args:
        filename (str):
            The filename of the CSV file.
    """
    out_filename = filename.replace('.csv', '.tsv')

    with open(filename, 'r') as in_fp:
        rows = csv.reader(in_fp)

        with safe_open_for_write(out_filename) as out_fp:
            csv.writer(out_fp, dialect='excel-tab').writerows(rows)


def http_get(url, allow_cache=True):
    """Perform a HTTP GET request to a server.

    This will handle looking up and storing cache details, along with setting
    up session management and standard headers.

    Args:
        url (str):
            The URL to retrieve.

        allow_cache (bool, optional):
            Whether to allow HTTP cache management.

    Returns:
        tuple:
        A 2-tuple containing:

        1. The requests session.
        2. The response.
    """
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


def slugify(s):
    """Return a string, slugified.

    This will lowercase the string and replace anything non-alphanumeric with
    an underscore.

    Args:
        s (str):
            The string to slugify.

    Returns:
        str:
        The slugified string.
    """
    return re.sub('[^A-Za-z0-9]', '_', s.strip().lower())


def add_nested_key(d, full_key, value):
    """Add a nested key path to a dictionary.

    This takes a ``.``-separated key path, creating nested dictionaries as
    needed, and assigning the provided value to the final key in that
    dictionary.

    Args:
        d (dict):
            The dictionary to set the key in.

        full_key (str):
            The ``.``-separated key path.

        value (object):
            The value to set.
    """
    keys = full_key.split(':')

    for key in keys[:-1]:
        d = d.setdefault(key, {})

    d[keys[-1]] = value


def parse_int(value, allow_blank=False):
    """Parse an integer from a string.

    This handles integers formatted with ``,`` separators and empty strings.

    Args:
        value (int or str):
            The value to parse.

        allow_blank (bool, optional):
            Whether to allow a blank value. If set, the value will be
            returned as-is if an empty string. Otherwise, a blank value will
            default to 0.

    Returns:
        int or str:
        The parsed integer, or the string if it's empty and
        ``allow_blank=True`` is passed.

    Raises:
        ValueError:
            The string did not contain an integer.
    """
    if ((allow_blank and value == '') or
        isinstance(value, int)):
        return value

    value = value.replace(',', '')

    return int(value or 0)


def parse_real(value, allow_blank=False):
    """Parse a real/float from a string.

    This handles reals formatted with ``,`` separators and empty strings.

    Args:
        value (float or str):
            The value to parse.

        allow_blank (bool, optional):
            Whether to allow a blank value. If set, the value will be
            returned as-is if an empty string. Otherwise, a blank value will
            default to 0.

    Returns:
        float or str:
        The parsed real/float, or the string if it's empty and
        ``allow_blank=True`` is passed.

    Raises:
        ValueError:
            The string did not contain a real/float.
    """
    if ((allow_blank and value == '') or
        isinstance(value, float)):
        return value

    value = value.replace(',', '')

    return float(value or 0)


def parse_pct(value):
    """Parse a percentage from a string.

    This will convert a ``X%`` value to a float.

    Args:
        value (str):
            The value to parse.

    Returns:
        float:
        The parsed percentage as a float, or an empty string if provided.

    Raises:
        ValueError:
            The string did not contain a float.
    """
    return parse_real(value.replace('%', ''), allow_blank=True)


def parse_csv_value(value, data_type, col_info):
    """Parse a value from a CSV file.

    This takes in a value and data type, along with parser-specified
    information on the expectations for that column, and returns a value.

    This accepts several data types:

    ``date``:
        Parses a date/time (as specified in ``col_info['format']``,
        returning a ``YYYY-MM-DD`` string value.

    ``int``:
        Parses a string, returning an integer. This supports ``,``-delimited
        numbers.

    ``int_or_blank``:
        Parses a string, returning an integer. If the string was blank, it
        will be returned as-is. This supports ``,``-delimited numbers.

    ``real``:
        Parses a string, returning a real/float. This supports ``,``-delimited
        numbers.

    ``pct``:
        Parses a ``X%`` string, returning a float. This supports
        ``,``-delimited numbers.

    ``string``:
        Returns a string as-is.

    Args:
        value (str):
            The value to parse.

        data_type (str):
            The data type to parse.

        col_info (dict):
            The column information, used to specify additional options for
            a data type.

    Returns:
        object:
        The parsed value.

    Raises:
        ParseError:
            The data could not be parsed correctly. Details are in the error
            message.
    """
    if data_type == 'date':
        try:
            value = (
                datetime.strptime(value, col_info['format'])
                .strftime('%Y-%m-%d')
            )
        except Exception:
            raise ParseError('Unable to parse date "%s" using format '
                             '"%s"'
                             % (value, col_info['format']))
    elif data_type == 'int_or_blank':
        try:
            value = parse_int(value, allow_blank=True)
        except ValueError:
            raise ParseError(
                'Expected %r to be an integer or empty string.'
                % value)
    elif data_type == 'int':
        try:
            value = parse_int(value)
        except ValueError:
            raise ParseError('Expected %r to be an integer.'
                             % value)
    elif data_type == 'real':
        try:
            value = parse_real(value)
        except ValueError:
            raise ParseError('Expected %r to be an integer.'
                             % value)
    elif data_type == 'pct':
        try:
            value = parse_pct(value)
        except ValueError:
            raise ParseError('Expected %r to be a percentage.'
                             % value)
    elif data_type == 'string' or data_type is None:
        pass
    else:
        raise ParseError('Unexpected data type %s' % data_type)

    return value


def add_or_update_json_date_row(filename, row_data, date_field='date'):
    """Add a new row of data for a date, or update an existing one.

    This will effectively append a new date row to a new or existing JSON file,
    or update the last row if it matches the given date.

    The JSON file must be a dictionary with a ``dates`` key, mapping to a list
    of rows. Dates must be in YYYY-MM-DD format.

    If rows were missing for dates between the last row's date and the current
    date, they will be added as blank rows with only the date field set.

    Args:
        filename (str):
            The name of the file to write to.

        row_data (dict):
            Data for the row.

        date_field (str, optional):
            The name of the field in the row data that references the date.
    """
    date_key = row_data[date_field]

    if os.path.exists(filename):
        with open(filename, 'r') as fp:
            try:
                dataset = json.load(fp)
            except Exception as e:
                raise ParseError('Unable to load existing dataset: %s', e)
    else:
        dataset = {
            'dates': [],
        }

    dates_data = dataset['dates']

    try:
        latest_date_key = dates_data[-1][date_field]
    except (IndexError, KeyError):
        latest_date_key = None

    if latest_date_key == date_key:
        dates_data[-1] = row_data
    else:
        # See if we have days we're missing. If so, we need to fill in the
        # gaps. This is mainly to keep the spreadsheet rows aligned.
        if latest_date_key is not None:
            cur_date = datetime.strptime(date_key, '%Y-%m-%d')
            latest_date = datetime.strptime(latest_date_key, '%Y-%m-%d')

            for day in range(1, (cur_date - latest_date).days):
                dates_data.append({
                    date_field: (latest_date +
                                 timedelta(days=day)).strftime('%Y-%m-%d'),
                })

        dates_data.append(row_data)

    with safe_open_for_write(filename) as fp:
        json.dump(dataset,
                  fp,
                  indent=2,
                  sort_keys=True)


def parse_butte_dashboard(response, out_filename, **kwargs):
    """Parse the Butte County dashboard.

    This extracts case, fatalities, hospitalization, demographics, and testing
    information from the Butte County COVID-19 dashboard, hosted on Infogram.
    It's built to work around quirks that may show up from time to time, and
    to cancel out if any data appears to be missing.

    Infogram pages contain a JSON payload of data used to generate the
    dashboard. These consist of entities, which contain information for some
    part of the dashboard. An entity may be broken into blocks that each
    contain a label and a value, or may contain chart data.

    If the current timestamp on the dashboard doesn't match today's date, the
    dashboard state will not be loaded.

    Args:
        response (requests.Response):
            The HTTP response containing the page.

        out_filename (str):
            The name of the outputted JSON file.

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
    def get_entity(entity_id):
        """Return an entity from the page's dashboard data.

        Args:
            entity_id (str):
                The unique ID of the entity.

        Returns:
            dict:
            The entity's payload data.

        Raises:
            KeyError:
                The entity ID was not found.
        """
        return (
            dashboard_data['elements']['content']['content']
            ['entities'][entity_id]
        )

    def get_counter_value(entity_id, expected_labels, label_first=False):
        """Return a value from a counter entity.

        This is used for entities like "Confirmed Cases". It will look for a
        label matching one of the possible expected labels and try to return
        the associated number.

        Args:
            entity_id (str):
                The unique ID of the counter entity.

            expected_labels (list of str):
                The list of labels that can match the entity.

            label_first (bool, optional):
                Whether the label is listed before the value.

        Returns:
            int:
            The counter value.

        Raises:
            ParseError:
                The entity could not be found.
        """
        entity = get_entity(entity_id)
        blocks = entity['props']['content']['blocks']

        value = None

        if blocks[0]['text'].lower() in expected_labels:
            value = blocks[1]['text']
        elif len(blocks) > 1 and blocks[1]['text'].lower() in expected_labels:
            value = blocks[0]['text']
        else:
            # They probably broke the labels/values again. Let's try to
            # find the label *in* the value.
            for label in expected_labels:
                for i in (0, 1):
                    if len(blocks) >= i and label in blocks[0]['text'].lower():
                        value = (
                            blocks[0]['text']
                            .lower()
                            .split(label)[0]
                            .strip()
                        )

            if value is None:
                found_labels = [
                    block['text'].lower()
                    for block in blocks
                ]

                raise ParseError(
                    'Expected one of label %r to be one of %r for '
                    'entity %s'
                    % (found_labels, expected_labels, entity_id))

        # This won't always be "pending", but the idea is that we're trying
        # to gracefully handle when there's an issue with some value coming
        # from the county or state.
        if 'pending' in value.lower():
            return None

        try:
            return int(value.replace(',', ''))
        except Exception:
            raise ParseError('Expected value %r for entity %s to be int, '
                             'got %s'
                             % (value, entity_id, type(value)))

    def get_chart_info(entity_id, label_col=0, value_col=1):
        """Return information from a chart.

        This will extract a chart's data, returning a mapping of chart axis
        labels to values.

        Args:
            entity_id (str):
                The unique ID of the counter entity.

            label_col (int, optional):
                The column index containing the label. This defaults to the
                first column.

            value_col (int, optional):
                The column index containing the value. This defaults to the
                second column.

        Returns:
            dict:
            A dictionary mapping chart labels to values.
        """
        entity = get_entity(entity_id)
        data = entity['props']['chartData']['data'][0]

        result = {}

        whitespace_re = re.compile('\s+')

        for row in data[1:]:
            try:
                value = int(row[value_col])
            except IndexError:
                # This column may not exist in this field, due to no value
                # provided yet in the graph data.
                value = 0

            key = whitespace_re.sub(' ', row[label_col])
            result[key] = value

        return result

    m = re.search(r'window.infographicData=(.*);</script>', response.text)

    if not m:
        raise ParseError('Unable to find infographicData in Butte Dashboard')

    try:
        dashboard_data = json.loads(m.group(1))
    except Exception as e:
        raise ParseError('Unable to parse infographicData in Butte Dashboard: '
                         '%s'
                         % e)

    try:
        entity = get_entity('7758d945-3baa-414b-8672-fb348d435436')
    except KeyError:
        raise ParseError('Unable to find datestamp entity in Butte Dashboard')

    m = re.search(r'as of (\d+)/(\d+)/(\d{4})',
                  entity['props']['content']['blocks'][0]['text'],
                  re.I)

    if not m:
        raise ParseError('Unable to find datestamp in Butte Dashboard')

    datestamp = datetime(month=int(m.group(1)),
                         day=int(m.group(2)),
                         year=int(m.group(3)))

    if datestamp.date() != datetime.now().date():
        # This is stale data not from today. OR it might be new data but
        # the county forgot to update the datestamp on it *again*. So don't
        # risk overwriting historical data, and instead bail.
        return False

    COUNTER_KEYS_TO_ENTITIES = {
        'confirmed_cases': {
            'labels': ['confirmed cases'],
            'entity_id': '15b62ec3-79df-492a-9171-f92c09dbe3c4',
        },
        'in_isolation': {
            'labels': ['currently in isolation'],
            'entity_id': '569b986d-bb02-48dc-ae00-15b58b58f712',
        },
        'released_from_isolation': {
            'labels': ['released from isolation', 'recovered'],
            'entity_id': 'f335bb23-9900-4acf-854a-8214e532c1de',
        },
        'deaths': {
            'labels': ['death', 'deaths'],
            'entity_id': '9c8d7a74-c196-40b5-a2e5-3bd643bbae8b',
        },
        'daily_viral_test_results': {
            'labels': ['daily viral test results', 'daily viral tests'],
            'entity_id': '50f7771c-d7fb-49bf-8fb6-604ff802d2d9',
        },
        'total_viral_tests': {
            'labels': ['total viral tests'],
            'entity_id': 'bdc32af3-587c-462b-b88a-367835d6bf8b',
        },
        'hospitalized': {
            'labels': ['currently hospitalized'],
            'entity_id': '3f7e639a-c67b-48b3-8b29-f552c9a30dcf',
        },
    }

    CHART_KEYS_TO_ENTITIES = {
        'by_age': ('9ba3a895-019a-4e68-99ec-0eb7b5bd026c', 1),
        'deaths_by_age': ('9ba3a895-019a-4e68-99ec-0eb7b5bd026c', 2),
        'by_region': ('b26b9acd-b036-40bc-bbbe-68667dd338e4', 1),
    }

    scraped_data = {
        key: get_counter_value(info['entity_id'],
                               expected_labels=info['labels'])
        for key, info in COUNTER_KEYS_TO_ENTITIES.items()
    }
    scraped_data.update({
        key: get_chart_info(entity_id, value_col=value_col)
        for key, (entity_id, value_col) in CHART_KEYS_TO_ENTITIES.items()
    })

    try:
        by_age = scraped_data['by_age']
        by_region = scraped_data['by_region']
        deaths_by_age = scraped_data['deaths_by_age']

        # As of Monday, September 28, 2020, the county has changed the By Ages
        # graph to show the non-fatal vs. fatal cases, instead of total vs.
        # fatal. To preserve the information we had, we need to add the deaths
        # back in.
        for key in list(by_age.keys()):
            by_age[key] += deaths_by_age[key]

        row_result = {
            'date': datestamp.strftime('%Y-%m-%d'),
            'confirmed_cases': scraped_data['confirmed_cases'],
            'deaths': scraped_data['deaths'],
            'deaths_by': {
                'age_ranges_in_years': {
                    '0-4': deaths_by_age['0-4 Years'],
                    '5-12': deaths_by_age['5-12 Years'],
                    '13-17': deaths_by_age['13-17 Years'],
                    '18-24': deaths_by_age['18-24 Years'],
                    '25-34': deaths_by_age['25-34 Years'],
                    '35-44': deaths_by_age['35-44 Years'],
                    '45-54': deaths_by_age['45-54 Years'],
                    '55-64': deaths_by_age['55-64 Years'],
                    '65-74': deaths_by_age['65-74 Years'],
                    '75_plus': deaths_by_age['75+ Years'],

                    # Legacy
                    '0-17': (deaths_by_age['0-4 Years'] +
                             deaths_by_age['5-12 Years'] +
                             deaths_by_age['13-17 Years']),
                },
            },
            'in_isolation': {
                'current': scraped_data['in_isolation'],
                'total_released': scraped_data['released_from_isolation'],
            },
            'viral_tests': {
                'total': scraped_data['total_viral_tests'],
                'results': scraped_data['daily_viral_test_results'],
            },
            'hospitalized': {
                'current': scraped_data['hospitalized'],
            },
            'age_ranges_in_years': {
                '0-4': by_age['0-4 Years'],
                '5-12': by_age['5-12 Years'],
                '13-17': by_age['13-17 Years'],
                '18-24': by_age['18-24 Years'],
                '25-34': by_age['25-34 Years'],
                '35-44': by_age['35-44 Years'],
                '45-54': by_age['45-54 Years'],
                '55-64': by_age['55-64 Years'],
                '65-74': by_age['65-74 Years'],
                '75_plus': by_age['75+ Years'],

                # Legacy
                '0-17': (by_age['0-4 Years'] +
                         by_age['5-12 Years'] +
                         by_age['13-17 Years']),
                '18-49': None,
                '50-64': None,
                '65_plus': by_age['65-74 Years'] + by_age['75+ Years'],
            },
            'regions': {
                'biggs_gridley': by_region['Biggs/Gridley'],
                'chico': by_region['Chico'],
                'durham': by_region['Durham'],
                'oroville': by_region['Oroville'],
                'other': by_region['Other'],
                'ridge': by_region['Ridge Communities'],

                # Legacy
                'gridley': None,
            },
        }
    except Exception as e:
        raise ParseError('Unable to build row data: %s' % e)

    add_or_update_json_date_row(out_filename, row_result)


def parse_butte_county_jail(response, out_filename, **kwargs):
    """Parse the Butte County Jail page.

    The Butte County Jail page uses a simple template for their reporting.
    This parser looks for parts of that template and pulls out the numbers,
    generating useful JSON data.

    Args:
        response (requests.Response):
            The HTTP response containing the page.

        out_filename (str):
            The name of the outputted JSON file.

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
    # Try to find the rough section of content we want to search within.
    m = re.search(r'(DAILY COVID-19.*)ENHANCED CLEANING',
                  response.text,
                  re.S)

    if not m:
        raise ParseError(
            'Could not find COVID-19 section for Butte County Jail.')

    content = m.group(1)

    m = re.search(r'DAILY COVID-19 UPDATE FOR ([A-Za-z]+) (\d+), (20\d{2}) '
                  r'\(Updated',
                  content)

    if not m:
        raise ParseError(
            'Unable to find update datestamp for Butte County Jail')

    months = {
        'january': 1,
        'february': 2,
        'march': 3,
        'april': 4,
        'may': 5,
        'june': 6,
        'july': 7,
        'august': 8,
        'september': 9,
        'october': 10,
        'november': 11,
        'december': 12,
    }

    datestamp_str = '%s %s, %s' % (m.group(1), m.group(2), m.group(3))
    datestamp = datetime(month=months[m.group(1).lower()],
                         day=int(m.group(2)),
                         year=int(m.group(3)))

    if datestamp.date() != datetime.now().date():
        # This is stale data not from today. OR it might be new data but
        # the county forgot to update the datestamp. So don't risk
        # overwriting historical data, and instead bail.
        return False

    def get_int(pattern):
        m = re.search(pattern, content)

        if not m:
            raise ParseError('Unable to find "%s" in Butte County Jail')

        try:
            return int(m.group(1))
        except ValueError:
            raise ParseError('Value for "%s" in Butte County Jail was not an '
                             'int!')

    inmates_data = {
        'current_population': get_int(r'inmate population as of '
                                      r'[A-Za-z]+ \d+, 20\d{2}: (\d+)'),
        'current_cases': get_int(r'currently has (\d+) positive '
                                 r'in-custody inmate'),
        'pending_tests': get_int(r'has (\d+) inmate COVID-19 tests pending'),
        'total_negative': get_int(r'(\d+) negative'),
        'total_recovered': get_int(r'(\d+) recovered'),
        'total_tests': get_int(r'Estimate of (\d+) total inmate tests'),
    }

    staff_data = {
        'total_tests': get_int(r'conducted (\d+) tests on staff'),
        'total_cases': get_int('total of (\d+) staff cases'),
        'total_recovered': get_int('(\d+) of those have recovered and '
                                   'returned to work'),
    }

    inmates_data['total_positive'] = \
        inmates_data['total_tests'] - inmates_data['total_negative']

    add_or_update_json_date_row(out_filename, {
        'date': datestamp.strftime('%Y-%m-%d'),
        'inmates': inmates_data,
        'staff': staff_data,
    })


def parse_cusd(response, out_filename, **kwargs):
    """Parse the Chico Unified School District COVID-19 dashboard.

    This exists as a spreadsheet on Google Sheets. It's listed as updating
    weekly, though we'll pull it down daily in case any numbers change.

    Args:
        response (requests.Response):
            The HTTP response containing the page.

        out_filename (str):
            The name of the outputted JSON file.

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
    school_type_map = {
        'Elementary Schools': 'elementary',
        'Junior Highs': 'junior_high',
        'High Schools': 'high_school',
        'State Preschools': 'state_preschools',
        'Other': 'other',
    }

    lines = list(response.iter_lines())[4:]
    lines[0] = b'Type' + lines[0]

    result = {}
    by_school_type = {}
    cur_section = None
    reader = csv.DictReader(codecs.iterdecode(lines, 'utf-8'),
                            delimiter=',')

    for row in reader:
        location = row['School/Location']

        if not location:
            # Empty line.
            continue

        pop_at_site = row['Total Students / Staff at Site*']

        if pop_at_site == 'N/A':
            pop_at_site = None
        else:
            pop_at_site = parse_int(pop_at_site)

        row_payload = {
            'population_at_site': pop_at_site,
            'total_cases': {
                'remote': parse_int(row['Online Learners / Independent Study']),
                'staff': parse_int(row['Staff']),
                'students': parse_int(row['Students']),
            },
        }

        if location == 'DISTRICT-WIDE TOTAL':
            result['district_wide'] = row_payload

            # We're done.
            break
        else:
            if row['Type']:
                cur_section = school_type_map[row['Type']]

            if location.startswith('State Funded Preschools'):
                location = 'State Funded Preschools'

            by_school_type.setdefault(cur_section, {})[location] = row_payload

    for school_type, locations in by_school_type.items():
        pop = 0
        remote_cases = 0
        staff_cases = 0
        students_cases = 0

        for location, row_payload in locations.items():
            cases_payload = row_payload['total_cases']

            pop += row_payload['population_at_site'] or 0
            remote_cases += cases_payload['remote'] or 0
            staff_cases += cases_payload['staff'] or 0
            students_cases += cases_payload['students'] or 0

        locations['totals'] = {
            'population_at_site': pop,
            'total_cases': {
                'remote': remote_cases,
                'staff': staff_cases,
                'students': students_cases,
            },
        }

    result.update(by_school_type)

    # It seems they update more than once a week, but the Last Updated may
    # not reflect this. For now, pull data in daily, and we'll find our for
    # ourselves.
    result['date'] = datetime.now().strftime('%Y-%m-%d')

    add_or_update_json_date_row(out_filename, result)

    return True


def convert_json_to_csv(info, in_fp, out_filename, **kwargs):
    """A parser that converts a JSON file to CSV.

    This loads a JSON file and, based on a mapping of nested key paths to
    columns, generates a new CSV file.

    The key map is defined in the parser info options as ``key_map``. Each
    key is a ``.``-separated key path within a row's data in the JSON file,
    and each value is a CSV header name.

    Args:
        info (dict):
            Parser option information. This must define ``key_map``.

        in_fp (file):
            A file pointer to the JSON file being read.

        out_filename (str):
            The filename for the CSV file to write.

        **kwargs (dict, unused):
            Unused keyword arguments passed to this parser.
    """
    def _get_key_value(d, paths):
        for path in paths:
            d = d.get(path)

            if d is None:
                break

        return d

    key_map = info['key_map']
    dataset = json.load(in_fp) or {}

    with safe_open_for_write(out_filename) as fp:
        csv_writer = csv.DictWriter(
            fp,
            fieldnames=[
                key_entry[0]
                for key_entry in key_map
            ])
        csv_writer.writeheader()

        for row in dataset.get('dates', []):
            csv_writer.writerow({
                key: _get_key_value(row, paths)
                for key, paths in key_map
            })

    convert_csv_to_tsv(out_filename)


def build_timeline_json(info, in_fp, out_filename, **kwargs):
    """Parse the Google Sheets CSV export and build JSON data for the website.

    This takes all the consolidated information from the main "Timeline Data"
    sheet in Google Sheets and generates a new JSON file for consumption by
    the https://bc19.live dashboard.

    Each header in the Google Sheets CSV file is expected to be a
    ``.``-delimited nested key path, which will be used when setting the
    appropriate key in the JSON file.

    Both a ``.json`` and a ``.min.json`` (actually used by the website) will
    be generated.

    Args:
        info (dict):
            Parser option information. This must define ``min_filename``.

        in_fp (file):
            A file pointer to the CSV file being read.

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
    timeline = []
    reader = csv.DictReader(in_fp, delimiter=',')

    for row in reader:
        date_info = {}
        timeline.append(date_info)

        for col_name, col_data in row.items():
            if col_name != 'row_id':
                if col_data == '':
                    col_data = None
                else:
                    try:
                        col_data = int(col_data)
                    except ValueError:
                        try:
                            col_data = float(col_data)
                        except ValueError:
                            pass

                add_nested_key(date_info, col_name, col_data)

    # We've hit issues where we've encountered empty data for the last few
    # days when pulling from the spreadsheet. That should not be happening.
    # Look for this and bail if we have to.
    found_cases = False

    for row in timeline[-3:]:
        if row['confirmed_cases']['total'] is not None:
            found_cases = True
            break

    if not found_cases:
        sys.stderr.write('Got an empty timeline dataset! Not writing.')
        return False

    payload = {
        'dates': timeline,
    }

    with safe_open_for_write(out_filename) as fp:
        json.dump(payload,
                  fp,
                  sort_keys=True,
                  indent=2)

    min_filename = os.path.join(os.path.dirname(out_filename),
                                info['min_filename'])

    with safe_open_for_write(min_filename) as fp:
        json.dump(payload,
                  fp,
                  sort_keys=True,
                  separators=(',', ':'))

    return True


def build_state_region_icu_pct_json(response, out_filename, **kwargs):
    """Build JSON data for the California Region-specific ICU availability.

    California provides a table on their Shelter In Place page with the
    ICU bed availability percentages for the 5 regions established in the
    state. This parses out that data into something that can be pulled in
    elsewhere.

    Args:
        response (requests.Response):
            The HTTP response containing the page.

        out_filename (str):
            The name of the outputted JSON file.

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
    m = re.search(r'(ICU bed % available as of .*)Questions and answers',
                  response.text,
                  re.S)

    if not m:
        raise ParseError('Could not find the ICU information section')

    content = m.group(1)

    m = re.search(r'as of ([A-Za-z]+ \d+, \d{4}) for the 5 regions:',
                  content,
                  re.S)

    if not m:
        raise ParseError('Could not find the ICU capacity date information.')

    datestamp = datetime.strptime(m.group(1), '%B %d, %Y')

    if datestamp.date() != datetime.now().date():
        return False

    regions = re.findall(r'<tr>\s*'
                         r'<td>([^<]+)</td>\s*'
                         r'<td>[^<]*</td>\s*'
                         r'<td>\s*(?:<strong>)?([\d\.]+%)(?:</strong>)?\s*</td>',
                         content)

    if not regions:
        raise ParseError('Could not find the regions information')

    add_or_update_json_date_row(out_filename, dict({
        'date': datestamp.strftime('%Y-%m-%d'),
    }, **{
        slugify(region): parse_pct(pct)
        for region, pct in regions
    }))


def build_state_resources_json(session, response, out_filename, **kwargs):
    """Parse the state resources dashboard and build a JSON file.

    Note:
        This is currently defunct, as this dashboard has been removed.

    Args:
        session (requests.Session):
            The HTTP request session, for cookie management.

        response (requests.Respone):
            The HTTP response containing the initial dashboard page.

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
    # Set up the session and fetch the initial payloads.
    tableau_loader = TableauLoader(session=session,
                                   owner='COVID-19CountyProfile3',
                                   sheet='County Level Combined',
                                   orig_response=response)
    tableau_loader.bootstrap({
        'showParams': json.dumps({
            'unknownParams': 'County=Butte',
        }),
        'stickySessionKey': json.dumps({
            'workbookId': 6139600,
        }),
    })

    # NOTE: Ideally we'd look this up from "Last Updated Date", but I'm still
    #       unsure how these map into a dataValues with a negative
    #       aliasIndices. So while this isn't correct, it's sort of what
    #       we've got right now.
    data_dicts = tableau_loader.get_data_dicts()
    last_updated = datetime.strptime(
        sorted(data_dicts['datetime'])[-1],
        '%Y-%m-%d %H:%M:%S')

    if last_updated > datetime.now():
        # This isn't today's date. Skip it.
        return False

    data = tableau_loader.get_mapped_col_data({
        'Face Shields Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'face_shields',
                'value_index': 0,
            },
        },
        'Gloves Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'gloves',
                'value_index': 0,
            },
        },
        'Gowns Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'gowns',
                'value_index': 0,
            },
        },
        'ICU Beds Available BAN': {
            'AGG(ICU Availability)': {
                'data_type': 'real',
                'normalize': lambda value: int(round(value, 2) * 100),
                'result_key': 'icu_beds_pct',
                'value_index': 0,
            },
        },
        'N95 Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'n95_respirators',
                'value_index': 0,
            },
        },
        'Proc Masks Distributed': {
            'AGG(TableCalc Filled)': {
                'data_type': 'integer',
                'result_key': 'procedure_masks',
                'value_index': 0,
            },
        },
        'Sheet 42': {
            'SUM(Bed Reporting (Fixed))': {
                'data_type': 'integer',
                'result_key': 'beds',
                'value_index': 0,
            },
        },
        'Ventilators Available %': {
            'AGG(Ventilators Available %)': {
                'data_type': 'real',
                'normalize': lambda value: int(round(value, 2) * 100),
                'result_key': 'ventilators_pct',
                'value_index': 0,
            },
        },
    })
    data['date'] = last_updated.strftime('%Y-%m-%d')

    add_or_update_json_date_row(out_filename, data)


def build_state_tiers_json(session, response, out_filename, **kwargs):
    """Parse the state tiers dashboard and build a JSON file.

    This parses the Tableau dashboard containing information on Butte County's
    tier status, and generates JSON data that can be consumed to track which
    tier we're in and what the numbers look like.

    Args:
        session (requests.Session):
            The HTTP request session, for cookie management.

        response (requests.Respone):
            The HTTP response containing the initial dashboard page.

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
    tableau_loader = TableauLoader(session=session,
                                   owner='Planforreducingcovid-19',
                                   sheet='Plan for reducing covid-19',
                                   orig_response=response)
    tableau_loader.bootstrap({
        'showParams': json.dumps({
            'unknownParams': 'County=Butte',
        }),
        'stickySessionKey': json.dumps({
            'workbookId': 6582582,
        }),
    })

    data = tableau_loader.get_mapped_col_data({
        'Map': {
            'AGG(Avg Cases per Day per 100K)': {
                'data_type': 'real',
                'result_key': 'cases_per_100k',
                'value_index': 0,
                'normalize': lambda value: round(value, 2),
            },
            'AGG(Adj Avg Case Rate per Day per 100K)': {
                'data_type': 'real',
                'result_key': 'adjusted_cases_per_100k',
                'value_index': 0,
                'normalize': lambda value: round(value, 2),
            },
            'AGG(Test Positivity Rate)': {
                'data_type': 'real',
                'result_key': 'pos_rate',
                'value_index': 0,
                'normalize': lambda value: round(value, 5),
            },
            'Current tier': {
                'data_type': 'integer',
                'result_key': 'status',
                'value_index': 0,
            },
            'Effective date': {
                'data_type': 'cstring',
                'result_key': 'effective_date',
                'value_index': 0,
                'normalize': lambda date_str: (
                    datetime
                    .strptime(date_str, '(as of %m/%d/%y)')
                    .strftime('%Y-%m-%d')
                ),
            },
        },
    })
    data['date'] = tableau_loader.get_last_update_date().strftime('%Y-%m-%d')

    add_or_update_json_date_row(out_filename, data)


def build_hospital_cases_json(session, response, out_filename, **kwargs):
    """Parse the state hospitals dashboard and build a JSON file.

    This parses the Tableau dashboard containing information on Butte County's
    hospital status, which includes all patients (regardless of county of
    residency), along with the ICU numbers.

    Args:
        session (requests.Session):
            The HTTP request session, for cookie management.

        response (requests.Respone):
            The HTTP response containing the initial dashboard page.

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
    def _get_col_data(label, total_pres_model_name, total_field_caption,
                      total_result_key='total', include_date=False,
                      expected_date=None):
        data = tableau_loader.get_mapped_col_data({
            total_pres_model_name: {
                total_field_caption: {
                    'data_type': 'integer',
                    'result_key': 'total',
                    'value_index': 0,
                },
            },
            'Map Patients': {
                'Hospital Name': {
                    'data_type': 'cstring',
                    'result_key': 'hospital_names',
                    'normalize': lambda name: hospital_keys.get(name, name),
                },
                'AGG(Selector KPI)': {
                    'data_type': 'real',
                    'result_key': 'counts',
                },
            },
            'Updated on': {
                'max loaded timestamp': {
                    'data_type': 'datetime',
                    'result_key': 'date',
                    'value_index': 0,
                },
            },
        })

        if expected_date is not None and data['date'] != expected_date:
            raise ParseError('Date for hospitalizations data changed during '
                             'data import. Try again.')

        hospital_names = data['hospital_names']
        counts = data['counts']

        if len(hospital_names) != len(counts):
            raise ParseError('Number of hospital names (%s) does not match '
                             'number of case counts (%s) for %s.'
                             % (len(hospital_names), len(counts), label))

        col_data = dict({
            total_result_key: data['total'],
        }, **dict(zip(hospital_names, counts)))

        if include_date:
            col_data['date'] = data['date']

        return col_data

    hospital_keys = {
        'Enloe Medical Center - Esplanade': 'enloe_hospital',
        'Oroville Hospital': 'oroville_hospital',
        'Orchard Hospital': 'orchard_hospital',
    }

    tableau_loader = TableauLoader(session=session,
                                   owner='COVID-19PublicDashboard',
                                   sheet='Covid-19 Hospitals',
                                   orig_response=response)
    tableau_loader.bootstrap({
        'showParams': json.dumps({
            'unknownParams': 'COUNTY=Butte',
        }),
        'stickySessionKey': json.dumps({
            'workbookId': 5911876,
        }),
    })

    result = {}

    # Load the patients view.
    patients_data = _get_col_data(
        label='positive patients',
        total_pres_model_name='Positive Patients',
        total_field_caption='SUM(Hospitalized Covid Confirmed Patients)',
        total_result_key='total_patients',
        include_date=True)

    date_raw = patients_data['date']
    date = datetime.strptime(date_raw, '%m/%d/%Y')

    if date > datetime.now():
        # This isn't today's date. Skip it.
        return False

    result.update(patients_data)
    result['date'] = date.strftime('%Y-%m-%d')

    # Now load in information from the Suspected Patients view.
    tableau_loader.set_parameter_value(
        '[Parameters].[Select Measure (copy)_1581607928766861312]',
        'Suspected Patients')

    result['suspected_patients'] = _get_col_data(
        label='suspected patients',
        total_pres_model_name='Suspected Patients',
        total_field_caption='SUM(Hospitalized Suspected Covid Patients)',
        expected_date=date_raw)

    # Now load in information from the ICU Available Beds view.
    tableau_loader.set_parameter_value(
        '[Parameters].[Select Measure (copy)_1581607928766861312]',
        'ICU Available Beds')

    result['icu_beds_available'] = _get_col_data(
        label='available ICU beds',
        total_pres_model_name='ICU Available Beds',
        total_field_caption='SUM(Icu Available Beds)',
        expected_date=date_raw)

    # Now load in information from the ICU Positive Patients view.
    tableau_loader.set_parameter_value(
        '[Parameters].[Select Measure (copy)_1581607928766861312]',
        'ICU Positive Patients')

    result['icu_patients'] = _get_col_data(
        label='ICU patients',
        total_pres_model_name='ICU Positive Census',
        total_field_caption='SUM(Icu Covid Confirmed Patients)',
        expected_date=date_raw)

    # Now load in information from the ICU Suspected Patients view.
    tableau_loader.set_parameter_value(
        '[Parameters].[Select Measure (copy)_1581607928766861312]',
        'ICU Suspected Patients')

    result['icu_suspected_patients'] = _get_col_data(
        label='ICU suspected patients',
        total_pres_model_name='ICU Suspected Census',
        total_field_caption='SUM(Icu Suspected Covid Patients)',
        expected_date=date_raw)

    import pprint; pprint.pprint(result)

    add_or_update_json_date_row(out_filename, result)


def parse_csv(info, response, out_filename, **kwargs):
    """Parse a CSV file, building a new CSV file based on its information.

    This takes information on the columns in a source CSV file and how they
    should be transformed into a destination CSV File.

    These options live in ``info['csv']``, and contain:

    ``columns`` (list):
        A list of column definitions. Each definition contains:

        ``name`` (str):
            The name of the column.

        ``delta_from`` (str, optional);
            For ints, pcts, and reals, the field in the generated row data that
            this number will be relative to.

        ``delta_type`` (str, optional);
            The type to interpret a delta value for. This accepts ``int``,
            ``pct``, and ``real``, and defaults to the ``delta_type`` option
            (see below).

        ``format`` (str, optional):
            For dates, the :py:func:`datetime.datetime.strftime` format.

        ``type`` (str, optional).
            The type of the column (as supported by
            :py:func:`parse_csv_value`). Defaults to the ``default_type``
            option (see below).

    ``default_type`` (str, optional):
        The optional default type for any values present.

    ``end_if`` (callable, optional):
        An optional function that takes a row's data and returns whether
        parsing should stop for the file.

    ``match_row`` (callable, optional):
        An optional function that determines whether a row should be processed
        from the source CSV file. This takes the parsed row dictionary.

    ``skip_rows`` (int, optional):
        An optional number of rows to skip in the source file.

    ``sort_by`` (str, optional):
        The column in the destination file that entries should be sorted by.

    ``unique_col`` (str, optional):
        The name of a column that is considered unique across all entries
        (generally an ID).

    ``validator`` (callable, optional):
        An optional function that takes in the resulting row data and returns
        a boolean indicating if the results are valid and suitable for writing.

    Args:
        info (dict):
            The parser options information. This must contain a ``csv`` key.

        response (requests.Respone):
            The HTTP response containing the CSV file.

        out_filename (str):
            The filename for the CSV file to write.

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
    csv_info = info.get('csv', {})
    columns = csv_info['columns']
    match = csv_info.get('match_row')
    sort_by = csv_info.get('sort_by')
    validator = csv_info.get('validator')
    unique_col = csv_info.get('unique_col')
    skip_rows = csv_info.get('skip_rows', 0)
    default_type = csv_info.get('default_type')
    end_if = csv_info.get('end_if')

    unique_found = set()
    results = []

    lines = response.iter_lines()

    for i in range(skip_rows):
        next(lines)

    reader = csv.DictReader(codecs.iterdecode(lines, 'utf-8'),
                            delimiter=',')
    prev_row = None

    for row in reader:
        if match is not None and not match(row):
            continue

        if end_if is not None and end_if(row):
            break

        row_result = {}

        for col_info in columns:
            dest_name = col_info['name']
            src_name = col_info.get('source_column', dest_name)
            data_type = col_info.get('type', default_type)

            try:
                value = row[src_name]
            except KeyError:
                raise ParseError('Missing column in CSV file: %s' % src_name)

            if data_type == 'delta':
                delta_from = col_info['delta_from']

                if (row[delta_from] == '' or
                    prev_row is None or
                    prev_row[delta_from] == ''):
                    value = ''
                else:
                    value = parse_csv_value(
                        value=value,
                        data_type=col_info.get('delta_type', default_type),
                        col_info=col_info)
            else:
                value = parse_csv_value(value=value,
                                        data_type=data_type,
                                        col_info=col_info)

            row_result[dest_name] = value

        if unique_col is None:
            results.append(row_result)
        elif isinstance(unique_col, tuple):
            unique_values = tuple(
                row_result[_col]
                for _col in unique_col
            )

            if unique_values not in unique_found:
                # We haven't encountered this row before. Add it to the
                # results.
                results.append(row_result)
                unique_found.add(unique_values)
        else:
            unique_value = row_result[unique_col]

            if unique_value not in unique_found:
                # We haven't encountered this row before. Add it to the
                # results.
                results.append(row_result)
                unique_found.add(unique_value)

        prev_row = row

    # Some datasets are unordered or not in an expected order. If needed, sort.
    if sort_by is not None:
        results = sorted(results, key=lambda row: row[sort_by])

    # Validate that we have the data we expect. We don't want to be offset by
    # a row or have garbage or something.
    if validator is not None and not validator(results):
        raise ParseError('Resulting CSV file did not pass validation!')

    with safe_open_for_write(out_filename) as out_fp:
        writer = csv.DictWriter(
            out_fp,
            fieldnames=[
                col_info['name']
                for col_info in columns
            ])
        writer.writeheader()

        for row_result in results:
            writer.writerow(row_result)

    convert_csv_to_tsv(out_filename)


#: The list of feeds to download and parse.
#:
#: Each of these will generate one or more files, which may be used as
#: final datasets or intermediary datasets for another parser.
FEEDS = [
    {
        'filename': 'cusd.json',
        'format': 'json',
        'url': 'https://docs.google.com/spreadsheets/u/0/d/e/2PACX-1vSPLYKyOXjJQbvrnZtU9Op0uMoH84EKYP7pEp1ANCAw3yWg3LswQs5wfOSKFt5AukxPymzZ9QczlMDh/pub/sheet?headers=false&gid=2096611352&output=csv',
        'parser': parse_cusd,
    },
    {
        'filename': 'cusd.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'cusd.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
        ] + [
            ('District - %s Cases' % _cases_name,
             ('district_wide', 'total_cases', _cases_key))
            for _cases_key, _cases_name in (('staff', 'Staff'),
                                            ('students', 'Student'),
                                            ('remote', 'Remote'))
        ] + [
            ('%s - %s Cases' % (_school_type, _cases_name),
             (_school_type_key, 'totals', 'total_cases', _cases_key))
            for _school_type_key, _school_type in (
                ('elementary', 'Elementary'),
                ('junior_high', 'Junior High'),
                ('high_school', 'High School'),
                ('other', 'Other')
            )
            for _cases_key, _cases_name in (('staff', 'Staff'),
                                            ('students', 'Student'),
                                            ('remote', 'Remote'))
        ] + [
            ('%s - %s Cases' % (_location, _cases_name),
             (_school_type_key, _location, 'total_cases', _cases_key))
            for _school_type_key, _locations in (
                ('elementary', (
                    'Chapman Elementary School',
                    'Citrus Elementary School',
                    'Emma Wilson Elementary School',
                    'Hooker Oak Elementary School',
                    'McManus Elementary School',
                    'Little Chico Creek Elementary School',
                    'Marigold/Loma Vista School',
                    'Neal Dow Elementary School',
                    'Parkview Elementary School',
                    'Rosedale Elementary School',
                    'Shasta Elementary School',
                    'Sierra View Elementary School',
                    'Oak Bridge Academy Elementary School (K-12)',
                )),
                ('junior_high', (
                    'Bidwell Junior High School',
                    'Chico Junior High School',
                    'Marsh Junior High School',
                )),
                ('high_school', (
                    'Chico High School',
                    'Pleasant Valley High School',
                    'Fair View High School',
                    'Oakdale/AFC/CAL',
                )),
                ('other', (
                    'Itinerant Staff',
                    'Non-School Campus',
                    'Online Learning',
                )),
                ('state_preschools', (
                    'State Funded Preschools',
                )),
            )
            for _location in _locations
            for _cases_key, _cases_name in (('staff', 'Staff'),
                                            ('students', 'Student'),
                                            ('remote', 'Remote'))
        ],
    },
    {
        'filename': 'skilled-nursing-facilities-v3.csv',
        'format': 'csv',
        'url': 'https://raw.githubusercontent.com/datadesk/california-coronavirus-data/master/cdph-skilled-nursing-facilities.csv',
        'csv': {
            'match_row': lambda row: (
                row['county'] == 'Butte' and
                row['date'] not in ('2020-04-21', '2020-04-22', '2020-04-23')
            ),
            'validator': lambda results: results[0]['date'] == '2020-04-24',
            'sort_by': 'date',
            'unique_col': ('date', 'name'),
            'columns': [
                {
                    'name': 'date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {'name': 'name'},
                {'name': 'staff_confirmed_cases'},
                {'name': 'patients_confirmed_cases'},
                {'name': 'staff_confirmed_cases_note'},
                {'name': 'patients_confirmed_cases_note'},
                {'name': 'staff_deaths'},
                {'name': 'patients_deaths'},
                {'name': 'staff_deaths_note'},
                {'name': 'patients_deaths_note'},
            ],
        },
    },
    {
        'filename': 'state-hospitals-v3.csv',
        'format': 'csv',
        'url': 'https://data.ca.gov/dataset/529ac907-6ba1-4cb7-9aae-8966fc96aeef/resource/42d33765-20fd-44b8-a978-b083b7542225/download/hospitals_by_county.csv',
        'csv': {
            'match_row': lambda row: row['county'] == 'Butte',
            'validator': lambda results: results[0]['date'] == '2020-03-29',
            'sort_by': 'date',
            'unique_col': 'date',
            'columns': [
                {
                    'name': 'date',
                    'source_column': 'todays_date',
                    'type': 'date',
                    'format': '%Y-%m-%d',
                },
                {'name': 'hospitalized_covid_confirmed_patients'},
                {'name': 'hospitalized_suspected_covid_patients'},
                {'name': 'icu_covid_confirmed_patients'},
                {'name': 'icu_suspected_covid_patients'},
                {'name': 'all_hospital_beds'},
                {'name': 'icu_available_beds'},
            ],
        },
    },
    {
        'filename': 'columbia-projections-nochange.csv',
        'format': 'csv',
        'url': 'https://raw.githubusercontent.com/shaman-lab/COVID-19Projection/master/LatestProjections/Projection_nochange.csv',
        'csv': {
            'match_row': lambda row: row['county'] == 'Butte County CA',
            'sort_by': 'date',
            'unique_col': 'date',
            'columns': [
                {
                    'name': 'date',
                    'source_column': 'Date',
                    'type': 'date',
                    'format': '%m/%d/%y',
                },
                {'name': 'report_2.5'},
                {'name': 'report_25'},
                {'name': 'report_50'},
                {'name': 'report_75'},
                {'name': 'report_97.5'},
                {'name': 'total_2.5'},
                {'name': 'total_25'},
                {'name': 'total_50'},
                {'name': 'total_75'},
                {'name': 'total_97.5'},
            ],
        },
    },
    {
        'filename': 'butte-dashboard.json',
        'format': 'json',
        'url': 'https://infogram.com/1pe66wmyjnmvkrhm66x9362kp3al60r57ex',
        'parser': parse_butte_dashboard,
    },
    {
        'filename': 'butte-dashboard-v4.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'butte-dashboard.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Confirmed Cases', ('confirmed_cases',)),
            ('Deaths', ('deaths',)),
            ('Currently In Isolation', ('in_isolation', 'current')),
            ('Total Released From Isolation', ('in_isolation',
                                               'total_released')),
            ('Total Viral Tests', ('viral_tests', 'total')),
            ('Daily Viral Test Results', ('viral_tests', 'results')),
            ('Currently Hospitalized', ('hospitalized', 'current')),
            ('Age 0-4 Years', ('age_ranges_in_years', '0-4')),
            ('Age 5-12 Years', ('age_ranges_in_years', '5-12')),
            ('Age 13-17 Years', ('age_ranges_in_years', '13-17')),
            ('Age 18-24 Years', ('age_ranges_in_years', '18-24')),
            ('Age 25-34 Years', ('age_ranges_in_years', '25-34')),
            ('Age 35-44 Years', ('age_ranges_in_years', '35-44')),
            ('Age 45-54 Years', ('age_ranges_in_years', '45-54')),
            ('Age 55-64 Years', ('age_ranges_in_years', '55-64')),
            ('Age 65-74 Years', ('age_ranges_in_years', '65-74')),
            ('Age 75+ Years', ('age_ranges_in_years', '75_plus')),
            ('Age 0-17 Years', ('age_ranges_in_years', '0-17')),
            ('Age 18-49 Years', ('age_ranges_in_years', '18-49')),
            ('Age 50-64 Years', ('age_ranges_in_years', '50-64')),
            ('Age 65+ Years', ('age_ranges_in_years', '65_plus')),
            ('Biggs/Gridley Cases', ('regions', 'biggs_gridley')),
            ('Chico Cases', ('regions', 'chico')),
            ('Durham Cases', ('regions', 'durham')),
            ('Oroville Cases', ('regions', 'oroville')),
            ('Ridge Community Cases', ('regions', 'ridge')),
            ('Other Region Cases', ('regions', 'other')),
            ('Gridley Cases (Historical)', ('regions', 'gridley')),
            ('Deaths - Age 0-4 Years',
             ('deaths_by', 'age_ranges_in_years', '0-4')),
            ('Deaths - Age 5-12 Years',
             ('deaths_by', 'age_ranges_in_years', '5-12')),
            ('Deaths - Age 13-17 Years',
             ('deaths_by', 'age_ranges_in_years', '13-17')),
            ('Deaths - Age 18-24 Years',
             ('deaths_by', 'age_ranges_in_years', '18-24')),
            ('Deaths - Age 25-34 Years',
             ('deaths_by', 'age_ranges_in_years', '25-34')),
            ('Deaths - Age 35-44 Years',
             ('deaths_by', 'age_ranges_in_years', '35-44')),
            ('Deaths - Age 45-54 Years',
             ('deaths_by', 'age_ranges_in_years', '45-54')),
            ('Deaths - Age 55-64 Years',
             ('deaths_by', 'age_ranges_in_years', '55-64')),
            ('Deaths - Age 65-74 Years',
             ('deaths_by', 'age_ranges_in_years', '65-74')),
            ('Deaths - Age 75+ Years',
             ('deaths_by', 'age_ranges_in_years', '75_plus')),
            ('Deaths - Age 0-17 Years',
             ('deaths_by', 'age_ranges_in_years', '0-17')),
        ],
    },
    {
        'filename': 'butte-county-jail.json',
        'format': 'json',
        'url': 'https://www.buttecounty.net/sheriffcoroner/Covid-19',
        'parser': parse_butte_county_jail,
    },
    {
        'filename': 'butte-county-jail.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'butte-county-jail.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Inmate Population', ('inmates', 'current_population')),
            ('Current Inmate Cases', ('inmates', 'current_cases')),
            ('Total Recovered Inmates', ('inmates', 'total_recovered')),
            ('Total Inmate Tests', ('inmates', 'total_tests')),
            ('Total Negative Inmate Tests', ('inmates', 'total_negative')),
            ('Total Positive Inmate Tests', ('inmates', 'total_positive')),
            ('Pending Inmate Tests', ('inmates', 'pending_tests')),
            ('Total Staff Tests', ('staff', 'total_tests')),
            ('Total Staff Cases', ('staff', 'total_cases')),
            ('Total Recovered Staff', ('staff', 'total_recovered')),
        ],
    },
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
    {
        'filename': 'state-region-icu-pct.json',
        'format': 'json',
        'url': 'https://covid19.ca.gov/stay-home-except-for-essential-needs/',
        'parser': build_state_region_icu_pct_json,
    },
    {
        'filename': 'state-region-icu-pct.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'state-region-icu-pct.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Bay Area', ('bay_area',)),
            ('Greater Sacramento', ('greater_sacramento',)),
            ('Northern California', ('northern_california',)),
            ('San Joaquin Valley', ('san_joaquin_valley',)),
            ('Southern California', ('southern_california',)),
        ],
    },
    {
        'filename': 'state-resources.json',
        'format': 'json',
        'url': (
            'https://public.tableau.com/views/COVID-19CountyProfile3/'
            'CountyLevelCombined?%3AshowVizHome=no&County=Butte'
        ),
        'parser': build_state_resources_json,
    },
    {
        'filename': 'state-resources.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'state-resources.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Beds', ('beds',)),
            ('Face Shields', ('face_shields',)),
            ('Gloves', ('gloves',)),
            ('Gowns', ('gowns',)),
            ('N95 Respirators', ('n95_respirators',)),
            ('Procedure Masks', ('procedure_masks',)),
            ('ICU Beds Percent', ('icu_beds_pct',)),
            ('Ventilators Percent', ('ventilators_pct',)),
        ],
    },
    {
        'filename': 'state-tiers.json',
        'format': 'json',
        'url': (
            'https://public.tableau.com/views/Planforreducingcovid-19/'
            'planforreducingcovid-19/?%3AshowVizHome=no&County=Butte'
        ),
        'parser': build_state_tiers_json,
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
        ],
    },
    {
        'filename': 'hospital-cases.json',
        'format': 'json',
        'url': (
            'https://public.tableau.com/views/COVID-19HospitalsDashboard/'
            'Hospitals?&:showVizHome=no'
        ),
        'parser': build_hospital_cases_json,
    },
    {
        'filename': 'hospital-cases.csv',
        'format': 'csv',
        'local_source': {
            'filename': 'hospital-cases.json',
            'format': 'json',
        },
        'parser': convert_json_to_csv,
        'key_map': [
            ('Date', ('date',)),
            ('Patients: Enloe Hospital', ('enloe_hospital',)),
            ('Patients: Oroville Hospital', ('oroville_hospital',)),
            ('Patients: Orchard Hospital', ('orchard_hospital',)),
            ('Patients: Total', ('total_patients',)),
        ] + [
            ('%s: %s' % (_prefix, _hospital), (_type_key, _hospital_key))
            for _prefix, _type_key in (('Suspected', 'suspected_patients'),
                                       ('In ICU', 'icu_patients'),
                                       ('Suspected in ICU',
                                        'icu_suspected_patients'),
                                       ('Available ICU Beds',
                                        'icu_beds_available'))
            for _hospital, _hospital_key in (('Enloe Hospital',
                                              'enloe_hospital'),
                                             ('Oroville Hospital',
                                              'oroville_hospital'),
                                             ('Orchard Hospital',
                                              'orchard_hospital'),
                                             ('Total', 'total'))
        ],
    },
    {
        'filename': 'timeline.csv',
        'format': 'csv',
        'url': 'https://docs.google.com/spreadsheets/d/e/2PACX-1vRwJpCeZj4tsxMXqrHFDjIis5Znv-nI0kQk9enEAJAbYzZUBHm7TELQe0wl2huOYEkdaWLyR8N9k_uq/pub?gid=169564738&single=true&output=csv',
        'csv': {
            'end_if': lambda row: (row['confirmed_cases:total'] == ''),
            'validator': lambda results: (
                len(results) > 0 and
                results[0]['date'] == '2020-03-20' and
                (results[-1]['confirmed_cases:total'] != '' or
                 results[-2]['confirmed_cases:total'] != '' or
                 results[-3]['confirmed_cases:total'] != '')
            ),
            'skip_rows': 4,
            'default_type': 'int_or_blank',
            'columns': [
                {
                    'name': 'date',
                    'type': 'date',
                    'format': '%a, %b %d, %Y',
                },
                {'name': 'confirmed_cases:total'},
                {
                    'name': 'confirmed_cases:delta_total',
                    'type': 'delta',
                    'delta_from': 'confirmed_cases:total',
                },
                {'name': 'in_isolation:current'},
                {
                    'name': 'in_isolation:delta_current',
                    'type': 'delta',
                    'delta_from': 'in_isolation:current',
                },
                {'name': 'in_isolation:total_released'},
                {
                    'name': 'in_isolation:delta_total_released',
                    'type': 'delta',
                    'delta_from': 'in_isolation:total_released',
                },
                {'name': 'deaths:total'},
                {
                    'name': 'deaths:delta_total',
                    'type': 'delta',
                    'delta_from': 'deaths:total',
                },
                {'name': 'deaths:age_ranges_in_years:0-4'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_0-4',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:0-4',
                },
                {'name': 'deaths:age_ranges_in_years:5-12'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_5-12',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:5-12',
                },
                {'name': 'deaths:age_ranges_in_years:13-17'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_13-17',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:13-17',
                },
                {'name': 'deaths:age_ranges_in_years:18-24'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_18-24',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:18-24',
                },
                {'name': 'deaths:age_ranges_in_years:25-34'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_25-34',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:25-34',
                },
                {'name': 'deaths:age_ranges_in_years:35-44'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_35-44',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:35-44',
                },
                {'name': 'deaths:age_ranges_in_years:45-54'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_45-54',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:45-54',
                },
                {'name': 'deaths:age_ranges_in_years:55-64'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_55-64',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:55-64',
                },
                {'name': 'deaths:age_ranges_in_years:65-74'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_65-74',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:65-74',
                },
                {'name': 'deaths:age_ranges_in_years:75_plus'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_75_plus',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:75_plus',
                },
                {'name': 'deaths:age_ranges_in_years:0-17'},
                {
                    'name': 'deaths:age_ranges_in_years:delta_0-17',
                    'type': 'delta',
                    'delta_from': 'deaths:age_ranges_in_years:0-17',
                },
                {'name': 'viral_tests:total'},
                {
                    'name': 'viral_tests:delta_total',
                    'type': 'delta',
                    'delta_from': 'viral_tests:total',
                },
                {'name': 'viral_tests:results'},
                {
                    'name': 'viral_tests:delta_results',
                    'type': 'delta',
                    'delta_from': 'viral_tests:results',
                },
                {'name': 'viral_tests:pending'},
                {
                    'name': 'viral_tests:delta_pending',
                    'type': 'delta',
                    'delta_from': 'viral_tests:pending',
                },
                {'name': 'hospitalizations:county_data:hospitalized'},
                {'name': 'hospitalizations:state_data:positive'},
                {
                    'name': 'hospitalizations:state_data:delta_positive',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:positive',
                },
                {'name': 'hospitalizations:state_data:suspected_positive'},
                {
                    'name': 'hospitalizations:state_data:delta_suspected_positive',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:suspected_positive',
                },
                {'name': 'hospitalizations:state_data:icu_positive'},
                {
                    'name': 'hospitalizations:state_data:delta_icu_positive',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:icu_positive',
                },
                {'name': 'hospitalizations:state_data:icu_suspected'},
                {
                    'name': 'hospitalizations:state_data:delta_icu_suspected',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:icu_suspected',
                },
                {'name': 'hospitalizations:state_data:enloe_hospital'},
                {
                    'name': 'hospitalizations:state_data:delta_enloe_hospital',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:enloe_hospital',
                },
                {'name': 'hospitalizations:state_data:oroville_hospital'},
                {
                    'name': 'hospitalizations:state_data:delta_oroville_hospital',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:oroville_hospital',
                },
                {'name': 'hospitalizations:state_data:orchard_hospital'},
                {
                    'name': 'hospitalizations:state_data:delta_orchard_hospital',
                    'type': 'delta',
                    'delta_from': 'hospitalizations:state_data:orchard_hospital',
                },
                {'name': 'regions:biggs_gridley:cases'},
                {
                    'name': 'regions:biggs_gridley:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:biggs_gridley:cases',
                },
                {'name': 'regions:chico:cases'},
                {
                    'name': 'regions:chico:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:chico:cases',
                },
                {'name': 'regions:durham:cases'},
                {
                    'name': 'regions:durham:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:durham:cases',
                },
                {'name': 'regions:gridley:cases'},
                {
                    'name': 'regions:gridley:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:gridley:cases',
                },
                {'name': 'regions:oroville:cases'},
                {
                    'name': 'regions:oroville:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:oroville:cases',
                },
                {'name': 'regions:ridge:cases'},
                {
                    'name': 'regions:ridge:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:ridge:cases',
                },
                {'name': 'regions:other:cases'},
                {
                    'name': 'regions:other:delta_cases',
                    'type': 'delta',
                    'delta_from': 'regions:other:cases',
                },
                {'name': 'age_ranges_in_years:0-4'},
                {
                    'name': 'age_ranges_in_years:delta_0-4',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:0-4',
                },
                {'name': 'age_ranges_in_years:5-12'},
                {
                    'name': 'age_ranges_in_years:delta_5-12',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:5-12',
                },
                {'name': 'age_ranges_in_years:13-17'},
                {
                    'name': 'age_ranges_in_years:delta_13-17',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:13-17',
                },
                {'name': 'age_ranges_in_years:18-24'},
                {
                    'name': 'age_ranges_in_years:delta_18-24',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:18-24',
                },
                {'name': 'age_ranges_in_years:25-34'},
                {
                    'name': 'age_ranges_in_years:delta_25-34',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:25-34',
                },
                {'name': 'age_ranges_in_years:35-44'},
                {
                    'name': 'age_ranges_in_years:delta_35-44',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:35-44',
                },
                {'name': 'age_ranges_in_years:45-54'},
                {
                    'name': 'age_ranges_in_years:delta_45-54',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:45-54',
                },
                {'name': 'age_ranges_in_years:55-64'},
                {
                    'name': 'age_ranges_in_years:delta_55-64',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:55-64',
                },
                {'name': 'age_ranges_in_years:65-74'},
                {
                    'name': 'age_ranges_in_years:delta_65-74',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:65-74',
                },
                {'name': 'age_ranges_in_years:75_plus'},
                {
                    'name': 'age_ranges_in_years:delta_75_plus',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:75_plus',
                },
                {'name': 'age_ranges_in_years:0-17'},
                {
                    'name': 'age_ranges_in_years:delta_0-17',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:0-17',
                },
                {'name': 'age_ranges_in_years:18-49'},
                {
                    'name': 'age_ranges_in_years:delta_18-49',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:18-49',
                },
                {'name': 'age_ranges_in_years:50-64'},
                {
                    'name': 'age_ranges_in_years:delta_50_64',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:50-64',
                },
                {'name': 'age_ranges_in_years:65_plus'},
                {
                    'name': 'age_ranges_in_years:delta_65_plus',
                    'type': 'delta',
                    'delta_from': 'age_ranges_in_years:65_plus',
                },
                {
                    'name': 'resources:state_data:icu_beds_pct',
                    'type': 'pct',
                },
                {
                    'name': 'resources:state_data:ventilators_pct',
                    'type': 'pct',
                },
                {'name': 'resources:state_data:n95_respirators'},
                {'name': 'resources:state_data:procedure_masks'},
                {'name': 'resources:state_data:gowns'},
                {'name': 'resources:state_data:face_shields'},
                {'name': 'resources:state_data:gloves'},
                {
                    'name': 'note',
                    'type': 'string',
                },
                {'name': 'skilled_nursing_facilities:current_patient_cases'},
                {'name': 'skilled_nursing_facilities:current_staff_cases'},
                {'name': 'skilled_nursing_facilities:total_patient_deaths'},
                {'name': 'skilled_nursing_facilities:total_staff_deaths'},
                {'name': 'county_jail:inmates:population'},
                {
                    'name': 'county_jail:inmates:delta_population',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:population',
                },
                {'name': 'county_jail:inmates:total_tests'},
                {
                    'name': 'county_jail:inmates:delta_total_tests',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:total_tests',
                },
                {'name': 'county_jail:inmates:total_positive'},
                {
                    'name': 'county_jail:inmates:delta_total_positive',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:total_positive',
                },
                {'name': 'county_jail:inmates:tests_pending'},
                {
                    'name': 'county_jail:inmates:delta_tests_pending',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:tests_pending',
                },
                {'name': 'county_jail:inmates:current_cases'},
                {
                    'name': 'county_jail:inmates:delta_current_cases',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:current_cases',
                },
                {'name': 'county_jail:inmates:total_recovered'},
                {
                    'name': 'county_jail:inmates:delta_total_recovered',
                    'type': 'delta',
                    'delta_from': 'county_jail:inmates:total_recovered',
                },
                {'name': 'county_jail:staff:total_tests'},
                {
                    'name': 'county_jail:staff:delta_total_tests',
                    'type': 'delta',
                    'delta_from': 'county_jail:staff:total_tests',
                },
                {'name': 'county_jail:staff:total_positive'},
                {
                    'name': 'county_jail:staff:delta_total_positive',
                    'type': 'delta',
                    'delta_from': 'county_jail:staff:total_positive',
                },
                {
                    'name': 'monitoring:tier',
                    'type': 'string',
                },
                {
                    'name': 'monitoring:new_case_rate',
                    'type': 'real',
                },
                {
                    'name': 'monitoring:delta_new_case_rate',
                    'type': 'delta',
                    'delta_from': 'monitoring:new_case_rate',
                    'delta_type': 'real',
                },
                {
                    'name': 'monitoring:test_pos_rate',
                    'type': 'pct',
                },
                {
                    'name': 'monitoring:delta_test_pos_rate',
                    'type': 'delta',
                    'delta_from': 'monitoring:test_pos_rate',
                    'delta_type': 'pct',
                }
            ],
        },
    },
    {
        'filename': 'timeline.json',
        'min_filename': 'timeline.min.json',
        'format': 'json',
        'local_source': {
            'filename': 'timeline.csv',
            'format': 'csv',
        },
        'parser': build_timeline_json,
    },
]


def main():
    """Main function for building datasets.

    This accepts names of feeds on the command line to build, as well as a
    special ``-not-timeline`` argument that excludes the ``timeline.csv``,
    ``timeline.json``, and ``timeline.min.json`` files.

    Once the options are chosen, this will run through :py:data:`FEEDS` and
    handle pulling down files via HTTP(S), running them through a parser,
    possibly building exports, and then listing the states of that feed.

    HTTP responses are cached, to minimize traffic.
    """
    global http_cache

    if '--not-timeline' in sys.argv:
        feeds_to_build = {
            feed['filename']
            for feed in FEEDS
        } - {'timeline.csv', 'timeline.json'}
    elif len(sys.argv) > 1:
        feeds_to_build = set(sys.argv[1:])
    else:
        feeds_to_build = {
            feed['filename']
            for feed in FEEDS
        }

    # Load in the stored HTTP cache, if it exists.
    try:
        with open(CACHE_FILE, 'r') as fp:
            http_cache = json.load(fp)
    except Exception:
        http_cache = {}

    for info in FEEDS:
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

        if 'url' in info:
            url = info['url']

            session, response = \
                http_get(url, allow_cache=os.path.exists(out_filename))

            if response.status_code == 200:
                try:
                    result = parser(info=info,
                                    response=response,
                                    out_filename=out_filename,
                                    session=session)
                except ParseError as e:
                    sys.stderr.write('Data parse error while building %s: %s\n'
                                     % (filename, e))
                    continue
                except Exception as e:
                    sys.stderr.write('Unexpected error while building %s: %s\n'
                                     % (filename, e))
                    continue
            elif response.status_code == 304:
                up_to_date = True
            else:
                sys.stderr.write('HTTP error %s while fetching %s: %s'
                                 % (response.status_code, filename,
                                    response.text))
                continue
        elif 'local_source' in info:
            local_source = info['local_source']
            source_filename = os.path.join(DATA_DIR, local_source['format'],
                                           local_source['filename'])

            if not os.path.exists(source_filename):
                with open(source_filename, 'w') as out_fp:
                    out_fp.write('[]')

            with open(source_filename, 'r') as in_fp:
                try:
                    result = parser(info=info,
                                    in_fp=in_fp,
                                    out_filename=out_filename)
                except ParseError as e:
                    sys.stderr.write('Data parse error while building %s: %s\n'
                                     % (filename, e))
                    continue
                except Exception as e:
                    sys.stderr.write('Unexpected error while building %s: %s\n'
                                     % (filename, e))
                    continue
        else:
            sys.stderr.write('Invalid feed entry: %r\n' % info)
            continue

        skipped = (result is False)

        if up_to_date:
            print('Up-to-date: %s' % out_filename)
        elif skipped:
            print('Skipped %s' % out_filename)
        else:
            print('Wrote %s' % out_filename)


    # Write the new HTTP cache.
    with open(CACHE_FILE, 'w') as fp:
        json.dump(http_cache, fp)


if __name__ == '__main__':
    main()
