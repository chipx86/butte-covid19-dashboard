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
* [State Skilled Nursing Facilities - All Counties (Dashboard)](https://www.cdph.ca.gov/Programs/CID/DCDC/Pages/COVID-19/SNFsCOVID_19.aspx)
* [State Skilled Nursing Facilities - All Counties (CSV)](https://raw.githubusercontent.com/datadesk/california-coronavirus-data/master/cdph-skilled-nursing-facilities.csv)
* [State Hospital Case Statistics - Butte County (Dashboard)](https://public.tableau.com/views/COVID-19HospitalsDashboard/Hospitals?:embed=y&:showVizHome=no&COUNTY=Butte)
* [State Hospital Case Statistics - All Counties (CSV)](https://data.chhs.ca.gov/dataset/6882c390-b2d7-4b9a-aefa-2068cee63e47/resource/6cd8d424-dfaa-4bdd-9410-a3d656e1176e/download/covid19data.csv)
* [Butte County Jail - COVID-19](https://www.buttecounty.net/sheriffcoroner/Covid-19)
* [State Cases - All Countes (CSV)](https://data.ca.gov/dataset/590188d5-8545-4c93-a9a0-e230f0db7290/resource/926fd08f-cc91-4828-af38-bd45de97f8c3/download/statewide_cases.csv)
* [State Cases - All Countes (Data Viewer)](https://data.ca.gov/dataset/covid-19-cases/resource/926fd08f-cc91-4828-af38-bd45de97f8c3)
* [State Monitoring Tier Status (Dashboard)](https://covid19.ca.gov/safer-economy/#reopening-data)

Additional datasets can be found on the [COVID-19
Section](https://data.ca.gov/group/covid-19) of the [California Open Data
Portal](https://data.ca.gov).


Data Exports
------------

The following data is made available for others to use:

* [BC19.live Timeline Data (CSV)](https://bc19.live/data/csv/timeline.csv)
* [BC19.live Timeline Data (JSON)](https://bc19.live/data/json/timeline.json)
* [BC19.live Timeline Data (Google Sheets)](https://docs.google.com/spreadsheets/d/1cDD-vcOT6mZIgv4S3yflAyqUx9w-BbQ_vv9_bkk00lg/edit?usp=sharing)
* [Per-Hospital Case Counts (CSV)](https://bc19.live/data/csv/hospital-cases.csv)
* [Per-Hospital Case Counts (JSON)](https://bc19.live/data/json/hospital-cases.json)
* [Butte County Dashboard (CSV)](https://bc19.live/data/csv/butte-dashboard-v3.csv)
* [Butte County Dashboard (JSON)](https://bc19.live/data/json/butte-dashboard.json)
* [Butte County Jail (CSV)](https://bc19.live/data/csv/butte-county-jail.csv)
* [Butte County Jail (JSON)](https://bc19.live/data/csv/butte-county-jail.json)
* [State Cases - Butte County Only (CSV)](https://bc19.live/data/csv/state-cases.csv)
* [State Skilled Nursing Facilities - Butte County Only (CSV)](https://bc19.live/data/csv/skilled-nursing-facilities-v3.csv)
* [State Hospital Case Statistics - Butte County Only (CSV)](https://bc19.live/data/csv/state-hospitals-v3.csv)
* [State Resources - Butte County Only (CSV)](https://bc19.live/data/csv/state-resources.csv)
* [State Resources - Butte County Only (JSON)](https://bc19.live/data/json/state-resources.json)
* [State Monitoring Tier Status - Butte County Only (CSV)](https://bc19.live/data/csv/state-tiers-v2.csv)
* [State Monitoring Tier Status - Butte County Only (JSON)](https://bc19.live/data/json/state-tiers.json)
