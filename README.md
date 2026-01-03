# parse-test

Small practice project for pulling a FRED series, validating the response, shaping it into a tidy DataFrame, and handing it off to plotting or cache consumers.

## What it does
- Fetches a FRED series (e.g., DGS10) with explicit request params and status checks.
- Parses `observations` into `{date: datetime.date, value: float}` rows while dropping null or invalid points.
- Builds a sorted pandas DataFrame as the contract for downstream use.
- Caches the cleaned DataFrame plus metadata to `cache/` with TTL checks and safe writes.
- Provides a simple matplotlib scatter plot of the cached/fetched data and saves it to `images/dgs10_yield.png`.
- Pulls Treasury Fiscal Data API `debt_subject_to_limit` records, normalizes them to `{date, debt_subject_to_limit, ...}`, and caches them for future joins with the FRED series.

## Data flow
FRED API → raw JSON → validated observations → cleaned rows → pandas DataFrame → (cache | plot)

## Project layout
- `fred_data_call.py`: fetch/validate/parse plus cache read/write helpers and a main-guard demo.
- `fiscal_data_call.py`: Treasury Fiscal Data API fetch/parse/cache helpers for `debt_subject_to_limit` with a main-guard demo.
- `plot.py`: imports `get_fred_series_df` and plots the series without refetching when cache is fresh.
- `.env`: holds `API_KEY` (git-ignored).

## Setup and run
1) `pip3 install requests pandas python-dotenv matplotlib`
2) Create `.env` with `API_KEY=your_fred_api_key_here` (and optionally `FISCAL_API_KEY` if Treasury starts requiring one)
3) Build or refresh FRED data: `python3 fred_data_call.py` (writes `cache/fred_<series>.csv` and metadata)
4) Build or refresh Treasury debt data: `python3 fiscal_data_call.py` (writes `cache/treasury_debt_subject_to_limit.csv` and metadata)
5) Plot the default series: `python3 plot.py` (uses cache when valid, otherwise fetches; saves chart to `images/dgs10_yield.png`)

## Unit testing
- Install test deps (alongside project deps): `pip3 install -r requirements-dev.txt`
- Run the suite: `pytest -q`
- Tests mock the FRED API and use temp dirs, so they do not hit the network or touch the real cache/images directories.
- Deterministic time: freezegun freezes `datetime.now()` in TTL/cache tests for stable expectations.
- Cache invariants: tests assert invalid/missing cache data raises, stale cache fallback warns, combined API+cache failure surfaces a clear RuntimeError, and failed cache writes do not leave partial temp files.
- CI: GitHub Actions workflow `.github/workflows/tests.yml` runs pytest on every push/PR; enable branch protection to require it to pass before merging.

## Caching notes
- Cache TTL defaults to 24h; stale cache is used if the API fails but files validate.
- Cache writes are atomic and refuse empty/invalid DataFrames.
- Metadata tracks series id, pull time, row count, and max observation date.

## Plot preview
![10-year treasury yield scatter](images/dgs10_yield.png)

## Next steps
- Explore other FRED series IDs and compare plots.
- Add CLI flags for TTL, series id, and cache dir.
- Layer in lightweight tests for parsing and cache invariants.
- Try different plot types (lines, rolling averages) to deepen matplotlib skills.
- Integrate a notebook or dashboard to keep learning pandas and visualization.
