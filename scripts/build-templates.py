#!/usr/bin/env python3

import os

from jinja2 import Environment, FileSystemLoader, Template


TEMPLATES = [
    {
        'template': 'index.html.j2',
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
            'county_dashboard_url': 'https://bcph.netlify.app/',
        },
    },
    {
        'template': 'schools.html.j2',
        'out_filename': 'schools.html',
        'context': {
            # Page header information
            'preview_file': './images/preview.png',
            'summary': 'Information on COVID-19 cases in Butte County schools',
            'title': 'Unofficial Butte County COVID-19 Schools Dashboard',

            # URLs
            'county_dashboard_url': 'https://bcph.netlify.app/',
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
    base_path = os.path.abspath(os.path.join(__file__, '..', '..', 'src'))
    dest_path = base_path
    templates_path = os.path.join(base_path, 'templates')

    env = Environment(
        loader=FileSystemLoader(templates_path),
        keep_trailing_newline=True)

    for template_info in TEMPLATES:
        build_template(env, dest_path, **template_info)


if __name__ == '__main__':
    main()
