import json
from datetime import datetime

from bc19live.errors import ParseError


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

                require_attrs = col_info.get('require_attrs')

                if require_attrs:
                    valid = all(
                        col_data.get(attr) == attr_value
                        for attr, attr_value in require_attrs.items()
                    )

                    if not valid:
                        continue

                data_type = col_data.get('dataType')

                if data_type != col_info['data_type']:
                    raise ParseError(
                        'Expected data type "%s" for column "%s", but got '
                        '"%s" instead.'
                        % (col_info['data_type'], caption, data_type))

                data_type_dict = data_dicts.get(data_type, [])
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
