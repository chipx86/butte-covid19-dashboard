#!/usr/bin/env python3

import os

from jinja2 import Environment, FileSystemLoader, Template


TEMPLATES = [
    {
        'template': 'index.html.tmpl',
        'out_filename': 'index.html',
        'context': {
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
        },
    },
]


def build_template(env, dest_path, template, out_filename, context):
    template = env.get_template(template)
    html = template.render(context)

    dest_file = os.path.join(dest_path, out_filename)

    with open(dest_file, 'w') as fp:
        fp.write(html)

    print('Wrote %s' % dest_file)


def main():
    dest_path = os.path.abspath(os.path.join(__file__, '..', '..', 'src'))

    env = Environment(
        loader=FileSystemLoader(
            os.path.abspath(os.path.join(__file__, '..', 'templates'))),
        keep_trailing_newline=True)

    for template_info in TEMPLATES:
        build_template(env, dest_path, **template_info)


if __name__ == '__main__':
    main()
