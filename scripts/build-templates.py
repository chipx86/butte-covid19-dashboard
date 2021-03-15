#!/usr/bin/env python3

import os

from jinja2 import Environment, FileSystemLoader, Template


def main():
    dest_path = os.path.abspath(os.path.join(__file__, '..', '..', 'src'))

    env = Environment(
        loader=FileSystemLoader(
            os.path.abspath(os.path.join(__file__, '..', 'templates'))),
        keep_trailing_newline=True)

    # Read in the template file.
    template = env.get_template('index.html.tmpl')

    # Build the data for the template
    context = {
        # Page header information
        'preview_file': './images/preview.png',
        'summary': (
            'Detailed trends and information on the COVID-19 situation '
            'in Butte County.'
        ),
        'title': 'Unofficial Butte County COVID-19 Dashboard',

        # URLs
        'county_dashboard_url':
            'https://infogram.com/1pe66wmyjnmvkrhm66x9362kp3al60r57ex',
    }

    html = template.render(context)

    # Write out the new HTML.
    dest_file = os.path.join(dest_path, 'index.html')

    with open(dest_file, 'w') as fp:
        fp.write(html)

    print('Wrote %s' % dest_file)


if __name__ == '__main__':
    main()
