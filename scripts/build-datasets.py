#!/usr/bin/env python3
"""Builds datasets for the bc19.live dashboard from public COVID-19 sources.

This script is responsible for going through a number of public sources,
consisting of CSV files, JSON feeds, Tableau dashboards, and web pages, and
building/validating new datasets that can be pulled in to analyze the COVID-19
situation in Butte County.
"""

from bc19live.main import main


if __name__ == '__main__':
    main()
