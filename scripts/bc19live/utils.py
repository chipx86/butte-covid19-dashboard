import codecs
import csv
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta

from bc19live.errors import ParseError


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


def get_nested_key(d, full_key, must_resolve=True):
    """Return the value from a dictionary using a nested key path.

    This takes a ``.``-separated key path and uses it to retrieve a value
    at the provided dictionary.

    Args:
        d (dict):
            The dictionary to retrieve the key from.

        full_key (str):
            The ``.``-separated key path.

        must_resolve (bool, optional):
            Raise an exception if the key could not be fully resolved.

    Returns:
        object:
        The value stored at the key.

    Raises:
        KeyError:
            The key could not be found, and ``must_resolve`` is ``True``.
    """
    for path in full_key:
        try:
            d = d[path]
        except KeyError:
            if must_resolve:
                raise

            d = None
            break

    return d


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


def build_missing_date_rows(cur_date, latest_date, date_field='date',
                            empty_row_data={}):
    """Build empty rows for a span of dates.

    Args:
        cur_date (datetime.datetime):
            The current date.

        latest_date (datetime.datetime):
            The latest date in the dataset.

        date_field (str, optional):
            The name of the field to add to generated rows for the row date.

        empty_row_data (dict, optional):
            Data to add to each empty row.

    Returns:
        list of dict:
        The generated list of rows.
    """
    assert cur_date >= latest_date, (
        'Current date (%s) should be >= latest date (%s)' % (
            cur_date, latest_date,
        ))

    return [
        dict(empty_row_data, **{
            date_field: (latest_date +
                         timedelta(days=day)).strftime('%Y-%m-%d'),
        })
        for day in range(1, (cur_date - latest_date).days)
    ]


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
            dates_data += build_missing_date_rows(
                cur_date=datetime.strptime(date_key, '%Y-%m-%d'),
                latest_date=datetime.strptime(latest_date_key, '%Y-%m-%d'),
                date_field=date_field)

        dates_data.append(row_data)

    with safe_open_for_write(filename) as fp:
        json.dump(dataset,
                  fp,
                  indent=2,
                  sort_keys=True)


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

        if isinstance(dataset, list):
            rows = dataset
        else:
            rows = dataset.get('dates', [])

        for row in rows:
            csv_writer.writerow({
                key: get_nested_key(row, paths, must_resolve=False)
                for key, paths in key_map
            })

    convert_csv_to_tsv(out_filename)


def parse_csv(info, response, out_filename, **kwargs):
    """Parse a CSV file, building a new CSV file based on its information.

    This takes information on the columns in a source CSV file and how they
    should be transformed into a destination CSV File.

    These options live in ``info['csv']``, and contain:

    ``add_missing_dates`` (bool, optional):
        Whether to ensure that missing date rows are present. They will be
        filled in with blanks.

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
    validators = csv_info.get('validators', csv_info.get('validator'))
    unique_col = csv_info.get('unique_col')
    skip_rows = csv_info.get('skip_rows', 0)
    default_type = csv_info.get('default_type')
    end_if = csv_info.get('end_if')
    add_missing_dates = csv_info.get('add_missing_dates', False)

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
            func = col_info.get('transform_func')

            if callable(func):
                value = func(row=row,
                             src_name=src_name,
                             data_type=data_type,
                             col_info=col_info)
            else:
                try:
                    value = row[src_name]
                except KeyError:
                    raise ParseError('Missing column in CSV file: %s'
                                     % src_name)

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
        if isinstance(sort_by, tuple):
            results = sorted(
                results,
                key=lambda row: tuple(
                    row[_key]
                    for _key in sort_by
                ))
        else:
            results = sorted(results, key=lambda row: row[sort_by])

    if add_missing_dates:
        # Make sure that the source feed doesn't skip any days. If they
        # do, we need to pad them out.
        #
        # This has been an on-going problem with state vaccine data.
        date_source_col = None
        date_dest_col = None
        empty_row_data = None
        date_fmt = None

        if add_missing_dates:
            empty_row_data = {}

            for col_info in columns:
                col_name = col_info['name']

                if col_info.get('type') == 'date':
                    assert not date_source_col
                    assert not date_dest_col
                    date_dest_col = col_name
                    date_source_col = col_info.get('source_column',
                                                   date_dest_col)
                    date_fmt = col_info.get('format', '%Y-%m-%d')
                else:
                    empty_row_data[col_name] = None

            assert date_source_col, 'Could not determine date column'
            assert date_fmt, (
                'Could not determine format for date column "%s"'
                % date_source_col)

        prev_date = None
        new_results = []

        for row in results:
            date = datetime.strptime(row[date_dest_col], date_fmt)

            if prev_date is not None:
                missing_rows = build_missing_date_rows(
                    cur_date=date,
                    latest_date=prev_date,
                    date_field=date_dest_col,
                    empty_row_data=empty_row_data)

                if missing_rows:
                    new_results += missing_rows

            new_results.append(row)
            prev_date = date

        results = new_results

    # Validate that we have the data we expect. We don't want to be offset by
    # a row or have garbage or something.
    if validators is not None:
        if not isinstance(validators, list):
            validators = [validators]

        for validate_func in validators:
            result = validate_func(results)

            if isinstance(result, tuple):
                result, reason = result
            else:
                reason = None

            if not result:
                raise ParseError('Resulting CSV file did not pass '
                                 'validation: %s'
                                 % (reason or 'Checks failed'))

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
