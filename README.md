BC19.live - Unofficial Butte County COVID-19 Dashboard
======================================================

Butte County being my home county, I've been craving insight into the COVID-19
situation affecting my friends and family. Since the [official
dashboard](https://infogram.com/1pe66wmyjnmvkrhm66x9362kp3al60r57ex) is fairly
light on information, I've decided to take matters into my own hands and build
a new one.

The new [BC19.live](https://bc19.live) dashboard contains trends and insights
into the situation, including notable events, breakdowns of cases based on
hospitals, detailed hospital information, testing relative to the population,
and more.

The data is compiled from the Butte County dashboard, State hospital statistics
for the county, and other state data feeds, all pulled into a Google Sheets
document, compiled, exported to CSV, and translated to JSON. All sources are
made available.

This dashboard lives at [https://bc19.live/](https://bc19.live/), and will be
updated daily.

See the [Frequently Asked Questions](https://www.notion.so/Frequently-Asked-Questions-98c9989c090c41a88f767830af845462)
for more information.


Sources
-------

BC19.live's data is compiled from the following sources:

* [Butte County (Dashboard)](https://infogram.com/1pe66wmyjnmvkrhm66x9362kp3al60r57ex)
* [covid19.ca.gov County Data - Butte County (Dashboard)](https://public.tableau.com/profile/ca.open.data#!/vizhome/COVID-19CountyProfile3/CountyLevelCombined?County=Butte)
* [Chico Unified School District Cases (Spreadsheet)](https://docs.google.com/spreadsheets/u/0/d/e/2PACX-1vSPLYKyOXjJQbvrnZtU9Op0uMoH84EKYP7pEp1ANCAw3yWg3LswQs5wfOSKFt5AukxPymzZ9QczlMDh/pubhtml?headers=true&gid=2096611352#)
* [LA Times - Adult and Senior Care Facilities - All Counties (CSV)](https://raw.githubusercontent.com/datadesk/california-coronavirus-data/master/cdph-adult-and-senior-care-facilities.csv)
* [LA Times - State Skilled Nursing Facilities - All Counties (CSV)](https://raw.githubusercontent.com/datadesk/california-coronavirus-data/master/cdph-skilled-nursing-facilities.csv)
* [Oroville Union High School District (Spreadsheet)](https://docs.google.com/spreadsheets/d/1uOghJGc0QCroA8e2xCaHIEYT-STgJtCgGpetVm6Tny0/edit#gid=0)
* [Oroville City Elementary School District (Spreadsheet)](https://www.ocesd.net/o/ocesd/page/covid-community-information)
* [State Skilled Nursing Facilities - All Counties (Dashboard)](https://www.cdph.ca.gov/Programs/CID/DCDC/Pages/COVID-19/SNFsCOVID_19.aspx)
* [State Hospital Case Statistics - Butte County (Dashboard)](https://public.tableau.com/views/COVID-19HospitalsDashboard/Hospitals?:embed=y&:showVizHome=no&COUNTY=Butte)
* [State Hospital Case Statistics - All Counties (CSV)](https://data.chhs.ca.gov/dataset/6882c390-b2d7-4b9a-aefa-2068cee63e47/resource/6cd8d424-dfaa-4bdd-9410-a3d656e1176e/download/covid19data.csv)
* [Stay-at-Home Regions Information (Dashboard)](https://public.tableau.com/profile/ca.open.data#!/vizhome/COVID-19Planforreducingcovid-19wregionsmap/regionalmap)
* [Butte County Jail - COVID-19](https://www.buttecounty.net/sheriffcoroner/Covid-19)
* [State Cases - All Countes (CSV)](https://data.ca.gov/dataset/590188d5-8545-4c93-a9a0-e230f0db7290/resource/926fd08f-cc91-4828-af38-bd45de97f8c3/download/statewide_cases.csv)
* [State Cases - All Countes (Data Viewer)](https://data.ca.gov/dataset/covid-19-cases/resource/926fd08f-cc91-4828-af38-bd45de97f8c3)
* [State COVID-19 Cases, Deaths, and Tests - All Countes (Data Viewer)](https://data.ca.gov/dataset/covid-19-time-series-metrics-by-county-and-state1/resource/6a1aaf21-2a2c-466b-8738-222aaceaa168)
* [State Monitoring Tier Status (Dashboard)](https://covid19.ca.gov/safer-economy/#reopening-data)
* [State Vaccines Administered Statistics (CSV)](https://data.chhs.ca.gov/dataset/e283ee5a-cf18-4f20-a92c-ee94a2866ccd/resource/130d7ba2-b6eb-438d-a412-741bde207e1c/download/covid19vaccinesbycounty.csv)
* [State Vaccine Statistics - Butte County (Dashboard)](https://covid19.ca.gov/vaccines/)

Additional datasets can be found on the [COVID-19
Section](https://data.ca.gov/group/covid-19) of the [California Open Data
Portal](https://data.ca.gov).


Data Exports
------------

The following data is made available for others to use:

* [Adult and Senior Care Facilities - Butte County Only (CSV)](https://bc19.live/data/csv/adult-and-senior-care.csv)
* [Butte County Dashboard (CSV)](https://bc19.live/data/csv/butte-dashboard-v4.csv)
* [Butte County Dashboard (JSON)](https://bc19.live/data/json/butte-dashboard.json)
* [Butte County Dashboard - Case, Probable Case, Death Timelines (CSV)](https://bc19.live/data/csv/butte-dashboard-history.csv)
* [Butte County Dashboard - Sequenced Variants (CSV)](https://bc19.live/data/csv/butte-dashboard-sequenced-variants.csv)
* [Butte County Jail (CSV)](https://bc19.live/data/csv/butte-county-jail.csv)
* [Butte County Jail (JSON)](https://bc19.live/data/csv/butte-county-jail.json)
* [Chico Unified School District Cases (CSV)](https://bc19.live/data/csv/cusd.csv)
* [Chico Unified School District Cases (JSON)](https://bc19.live/data/json/cusd.json)
* [Oroville Union High School District (CSV)](https://bc19.live/data/csv/oroville-union-high-school-district.csv)
* [Oroville Union High School District (JSON)](https://bc19.live/data/json/oroville-union-high-school-district.json)
* [Per-Hospital Case Counts (CSV)](https://bc19.live/data/csv/hospital-cases.csv)
* [Per-Hospital Case Counts (JSON)](https://bc19.live/data/json/hospital-cases.json)
* [State Skilled Nursing Facilities - Butte County Only (CSV)](https://bc19.live/data/csv/skilled-nursing-facilities-v3.csv)
* [State Hospital Case Statistics - Butte County Only (CSV)](https://bc19.live/data/csv/state-hospitals-v3.csv)
* [State Tests - Butte County Only (CSV)](https://bc19.live/data/csv/state-tests.csv)
* [State Vaccines Administered Statistics (CSV)](https://bc19.live/data/csv/chhs-vaccinations-administered.csv)
* [State Vaccine Demographics - Butte County Only (JSON)](https://bc19.live/data/json/vaccination-demographics.json)
* [State Vaccine Demographics - Butte County Only (CSV)](https://bc19.live/data/json/vaccination-demographics-v2.csv)


### Dashboard-Specific Data

This data is used to build the [bc19.live](https://bc19.live) dashboard.
The structures of the data is subject to change.

* [BC19.live Timeline Data (CSV)](https://bc19.live/data/csv/timeline.csv)
* [BC19.live Timeline Data (JSON)](https://bc19.live/data/json/timeline.json)
* [BC19.live Timeline Data (Google Sheets)](https://docs.google.com/spreadsheets/d/1cDD-vcOT6mZIgv4S3yflAyqUx9w-BbQ_vv9_bkk00lg/edit?usp=sharing)


### Legacy Data

This data is no longer updated, and is provided for historical reasons.

* [State Cases - Butte County Only (CSV)](https://bc19.live/data/csv/state-cases.csv)
* [State Monitoring Tier Status - Butte County Only (CSV)](https://bc19.live/data/csv/state-tiers-v2.csv)
* [State Monitoring Tier Status - Butte County Only (JSON)](https://bc19.live/data/json/state-tiers.json)
* [State Per-Region ICU Availability (CSV)](https://bc19.live/data/csv/state-region-icu-pct.csv)
* [State Resources - Butte County Only (CSV)](https://bc19.live/data/csv/state-resources.csv)
* [State Resources - Butte County Only (JSON)](https://bc19.live/data/json/state-resources.json)
* [Stay-at-Home Regions Information (JSON)](https://bc19.live/data/json/stay-at-home.json)
