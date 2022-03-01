class ParseError(Exception):
    """Error parsing or extracting data from a dataset."""

    def __init__(self, message, row=None):
        super(ParseError, self).__init__(message)

        self.row = row
