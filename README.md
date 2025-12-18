# parse-test

Hands-on exercise in parsing a real-world API response (FRED - Federal Reserve Bank of St. Louis) and transforming raw JSON into a clean, reusable analytical dataset using Python

This project intentionally avoids AI-generated starter code (I saved my GPT calls for this README) and focuses on building correct mental models for data pipelines, module structure, validation boundaries, and data invariants

---

## What this project does

- Fetches time-series data from the FRED API
- Extracts the observation records from the raw response
- Validates assumptions about structure and content
- Transforms raw JSON into a clean, typed Python data structure
- Loads the cleaned data into a pandas DataFrame
- Prepares the dataset for downstream use such as plotting or caching

---

## Key lessons learned

- The difference between running a Python file and importing it
- Why `if __name__ == "__main__"` guards exist and what they protect you from
- How importing a module executes top-level code exactly once
- Why imports should never trigger side effects like API calls
- How raw API JSON should be treated as an immutable source of truth
- How to explicitly select, validate, and transform data rather than relying on pandas inference
- Why validation belongs in orchestration logic, not in print or reporting helpers
- How to design functions with clear contracts and no hidden global dependencies
- Why data shape, type consistency, and ordering are invariants that must be enforced before usage
- How to think of plotting and caching as downstream consumers of data, not core responsibilities

---

## Design principles used

- No side effects on import
- Explicit data flow from fetch → validate → parse → tabularize
- Functions do one thing and return values instead of mutating globals
- Fail fast on invalid configuration or unusable data
- Avoid unnecessary dependencies until they are justified
- Treat pandas as a container, not a cleaning tool

---

## Data flow overview

The pipeline is intentionally linear and explicit:

FRED API
↓
raw_json (dict)
↓  select “observations”
observations (list[dict])
↓  validate structure and length
parse_observations
↓
cleaned_rows (list[{“date”: date, “value”: float}])
↓
pandas.DataFrame
↓
analysis / plotting / caching

Each step has a clear responsibility and enforces its own assumptions before passing data downstream

---

## Project structure

- `fred_data_call.py`
  - Contains all data fetching, validation, and parsing logic
  - Safe to import without triggering API calls
  - Uses a main guard for executable orchestration only

- `plot.py`
  - Consumes the DataFrame returned by the data module
  - Responsible only for visualization, not data correctness

- `.env`
  - Stores the FRED API key locally
  - Excluded from version control via `.gitignore`

---

## How to run

### Prerequisites

- Python 3.10+
- A FRED API key stored in a `.env` file

Example `.env`

API_KEY=your_fred_api_key_here

---

### Install dependencies

pip3 install requests pandas python-dotenv matplotlib

---

### Run the data pipeline directly

python3 fred_data_call.py

This will:
- Fetch the specified FRED series
- Validate and parse the response
- Build a pandas DataFrame
- Print basic sanity checks when run as a script

---

### Import safely from another file

from fred_data_call import get_fred_series_df

df = get_fred_series_df(“DGS10”)

Importing the module will not trigger any API calls or prints

---

## Why this matters

Most bugs in data work come from implicit assumptions about:
- execution context
- data structure
- ordering
- missing values
- responsibility boundaries

This project focuses on making those assumptions explicit so that:
- plots are honest
- caches are correct
- downstream users can trust the data
- changes are localized and predictable

---

## Next steps

- Add a local caching layer to reduce API calls and improve speed
- Plot the time series using matplotlib with correct ordering and labeling
- Support multiple FRED series with configurable parameters
- Add lightweight tests for parsing and validation logic