# Canadian Housing Affordability Explorer

An interactive data analytics application for exploring Canadian
apartment rental estimates and comparing housing costs with a
user-defined household budget.

Built by Omar Faruqe.

## Business questions

- How do apartment rents differ across selected metropolitan regions?
- How have asking and paid rent estimates changed over time?
- What are the quarter-over-quarter and year-over-year changes?
- How does estimated housing cost compare with a household's
  income and chosen budget target?
- Which observations or comparisons require caution?

## Features

- Filters for region, apartment type, rent measure, and quarter range.
- Interactive rent trend and regional comparison charts.
- Exact-calendar quarter-over-quarter and year-over-year comparisons.
- Data quality warnings and an option to exclude caution estimates.
- Income-based housing budget calculator.
- Downloadable source observations and budget scenarios.
- Reproducible download, cleaning, and database scripts.

## Technology

Python, pandas, requests, SQLite, Plotly, and Streamlit.

## Data source

Statistics Canada, Table 46-10-0092-01:

[Asking rent and paid rent prices, by rental unit type and number
of bedrooms, experimental estimates](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=4610009201)

The download source and timestamp are recorded in
`data/raw/download_metadata.json`.

Source data are subject to the
[Statistics Canada Open Licence Agreement](https://www.statcan.gc.ca/en/reference/licence).

This project is independently developed and is not affiliated with
Statistics Canada.

## Geographic scope

- Montréal
- Toronto
- Vancouver
- Calgary
- Ottawa–Gatineau, Ontario part
- Ottawa–Gatineau, Quebec part

These represent metropolitan areas or metropolitan-area parts,
rather than municipal boundaries.

The two Ottawa–Gatineau parts are kept separate. Their published
averages are not combined without appropriate weights.

## Apartment categories

Studio, one bedroom, two bedrooms, and three or more bedrooms.

Asking rent and paid rent are analyzed separately. Their category
coverage and underlying populations can differ.

## Initial data snapshot

The snapshot downloaded on October 6, 2026 contains:

- 9,646 source observations.
- 1,020 observations within the project's selected scope.
- 1,014 available rent observations.
- 6 unavailable observations.
- 83 available observations flagged "use with caution".
- Reference periods from 2019 Q1 through 2026 Q2.

These counts describe the initial snapshot and may change on refresh.

## Example findings: 2026 Q2

Monthly asking rent for two-bedroom apartments:

| Region | Rent (CAD) | Year-over-year change |
|---|---:|---:|
| Vancouver | 3,030 | -4.11%* |
| Toronto | 2,650 | -0.75%* |
| Ottawa–Gatineau, Ontario part | 2,360 | -2.88%* |
| Calgary | 1,890 | -6.44%* |
| Montréal | 1,820 | -5.21%* |
| Ottawa–Gatineau, Quebec part | 1,700 | Unavailable |

*Each reported year-over-year comparison involves at least one
caution-flagged estimate.

Among these selected regions:

- Vancouver has the highest published two-bedroom asking rent.
- Ottawa–Gatineau's Quebec part has the lowest.
- The difference between those estimates is $1,330 per month.
- Montréal's estimate declined 4.21% from the previous quarter.
- Five regions have computable year-over-year declines; the Quebec
  part of Ottawa–Gatineau lacks an available comparison value.

These are descriptive findings and do not establish the causes
of rent changes.

## Methodology

1. Download the original Statistics Canada ZIP archive.
2. Record source metadata and a SHA-256 fingerprint of the CSV.
3. Select exact geographic and apartment categories.
4. Validate quarterly dates, units, values, and observation uniqueness.
5. Preserve missing values and source quality flags.
6. Load observations into SQLite with integrity constraints.
7. Join exact previous-quarter and previous-year observations.
8. Display comparisons and calculator scenarios in Streamlit.

The dashboard queries SQLite directly. Missing values are not
converted to zero or filled from earlier periods.

## Quality flags

- Blank: acceptable or better quality under source conventions.
- E: use with caution.
- F: too unreliable to publish.
- ..: unavailable for the reference period.

Change calculations carry a caution indicator when either underlying
estimate has an E flag.

## Budget calculator

The calculator uses:

- Annual household income before tax.
- A configurable housing-budget percentage.
- Additional monthly costs not already included in rent.

Monthly housing budget = annual income / 12 × target fraction.

Estimated housing cost = monthly rent + additional monthly costs.

Annual income needed at target = estimated housing cost /
target fraction × 12.

The default 30% is an adjustable scenario setting. Results do not
constitute an official core housing need assessment.

The same additional-cost assumption applies to all selected regions.
A positive budget balance describes remaining housing-budget capacity,
not total disposable household income.

## Run locally

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Launch the app using the included database:

```bash
python -m streamlit run app.py
```

## Refresh the data

Run these commands in order:

```bash
python src/download_data.py
python src/inspect_data.py
python src/clean_data.py
python src/build_database.py
python src/query_data.py
python src/analyze_data.py
```

Review validation reports and update snapshot findings before
publishing refreshed data.

## Main files

| File | Purpose |
|---|---|
| app.py | Dashboard and budget calculator |
| src/download_data.py | Download and source tracking |
| src/inspect_data.py | Initial data inspection |
| src/clean_data.py | Cleaning and validation |
| src/build_database.py | SQLite schema and loading |
| src/query_data.py | Example SQL queries |
| src/analyze_data.py | Analysis SQL and standalone charts |
| data/processed/housing.db | Database used by the dashboard |
| requirements.txt | Pinned direct dependencies |

## Limitations

- Published estimates are experimental.
- Category averages do not represent individual rental listings.
- Rent measures have different coverage and populations.
- Included services may differ between properties and regions.
- Values are nominal Canadian dollars without inflation adjustment.
- Comparisons can involve caution-flagged estimates.
- The app uses a bundled snapshot; updates require a data refresh.
- Budget results depend on user-entered assumptions.

## Future improvements

- Add inflation-adjusted rent comparisons.
- Expand geographic coverage.
- Add automated checks for date matching and quality propagation.
- Add household income datasets with explicit geographic and
  reference-period alignment.


## Live demo

[Launch Canadian Housing Affordability Explorer](https://canadian-housing-affordability.streamlit.app/)  