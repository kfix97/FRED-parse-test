#---------------------------------------REFACTORED to use functions---------------------------------------#

# steps:
# 0) environment setup and import libraries
# 1) construct request URL
# 2) send request to FRED API, get and validate response
# 3) parse and clean raw json response
# 4) load clean data to pandas df
# 5) plot data points from pandas df

# step 0: environment setup and import libraries

# 0a) import libraries
from dotenv import load_dotenv
import requests
import sys
import os
from datetime import date
from datetime import datetime
import pandas as pd
import json
import time
import warnings
from pathlib import Path

# constants
BASE_URL = str("https://api.stlouisfed.org/fred")
endpoint = "/series/observations"
# series_id = "DGS10" # str(input("Enter the SeriesID for the dataset --> ")) # 1a) prompt end-user to input the series id of choice

# functions
def get_api_key():
    # 0b) get environment variables from config file (API key)
    load_dotenv()
    # 1b) read the API key from the .env file
    API_KEY = os.getenv("API_KEY")
    if not API_KEY:
        raise RuntimeError("API_KEY not found. Check your .env file.")
    return API_KEY

def fetch_fred_json(series_id, API_KEY):
    # 1c) define URL components
    params = {
        "series_id" : series_id,                # the specified dataset - required
        "api_key" : API_KEY,                   # the FRED API key - required
        "file_type" : "json"                   # json format vs xml - required
        #,"sort_order" : "desc"                # sorting the data descending by observation_date - optional
        # ,"observation_start" : date.today()  # start date of the dataset - optional
        # ,"observation_end" =                 # end date of the dataset - optional
    }

    # step 2: send request to FRED API, get and validate response

    # 2a) make the get request and store the response in a variable
    response = requests.get(BASE_URL + endpoint, params=params)

    # 2b) check the status of the response
    response.raise_for_status()

    # 2c) store the raw json in a variable
    raw_json = response.json()
    return raw_json

def parse_observations(observations):
    # 3c) inspect one observation row and look at the fields:
    # - date and value are the two key fields here for the x and y axes of a potential chart, respectively
    # i. drop observations with missing values in either date or value
    # ii. drop other key/value pairs besides date and value
    # iii. convert values to numeric data type and dates to a data type of date
    # 3d) transform raw observations to a smaller, cleaned dict with the logic above
    cleaned_observations = []
    for obs in observations:
        # step (ii) above mentions dopping all key/value pairs besides date and value, simply focus on these two
        raw_date = obs.get("date"," ")
        raw_value = obs.get("value",".")
        
        # FRED encodes nulls as "." rather than NULL or NaN, etc. - this is step (i) above
        if raw_value == ".": 
            continue
        if raw_date == "":
            continue
        
        # step (iii) above mentions data type transformations, this and the below lines accomplish that
        parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        parsed_value = float(raw_value)
        
        # the cleaned dictionary/row of data to be appended to the list
        clean_row = { 
            "date" : parsed_date,
            "value" : parsed_value
        }
        cleaned_observations.append(clean_row) # append to the list
    return cleaned_observations

# def print_validations(raw_json, cleaned_observation, df, json_limit=1):
#     # 2e) print a preview of the response
#     json_limit = 1
#     observations = raw_json["observations"]
#     preview = observations[:json_limit]
#     print("json preview: " + str(preview))
#     # 3b) confirm presence of the key and that the value is a list
#     number_of_cleaned_observations = len(cleaned_observations)
#     print("Of the original " + str(number_of_observations) + " data points, "
#         + str(number_of_cleaned_observations) + " passed the data validation check meaning that "
#         + str(number_of_observations - number_of_cleaned_observations) + " were invalid")
#     # 4b) print sample df data
#     print(df.head(10))

def load_cache_meta(meta_path: Path):
    if not meta_path.exists():
        return None
    with meta_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def is_cache_fresh(meta: dict, ttl_seconds: int) -> bool:
    pulled_at = meta.get("pulled_at")
    if not pulled_at:
        return False
    pulled_dt = datetime.fromisoformat(pulled_at)
    age_seconds = (datetime.now() - pulled_dt).total_seconds()
    return age_seconds <= ttl_seconds

def load_cache_df(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["date"])
    if df.empty:
        raise ValueError("Cache DF is empty")
    if "date" not in df.columns or "value" not in df.columns:
        raise ValueError("Cache DF missing required columns")
    if df["date"].isna().any() or df["value"].isna().any():
        raise ValueError("Cache DF contains missing date/value")
    df = df.sort_values("date").reset_index(drop=True)
    return df

def save_cache(df: pd.DataFrame, series_id: str, csv_path: Path, meta_path: Path):
    # enforce invariants before writing
    if df.empty:
        raise ValueError("Refusing to cache empty DataFrame")
    if "date" not in df.columns or "value" not in df.columns:
        raise ValueError("Refusing to cache DF missing required columns")
    if df["date"].isna().any() or df["value"].isna().any():
        raise ValueError("Refusing to cache DF with missing date/value")

    max_obs_date = df["date"].max().date().isoformat()
    meta = {
        "series_id": series_id,
        "pulled_at": datetime.now().isoformat(timespec="seconds"),
        "max_observation_date": max_obs_date,
        "row_count": int(len(df)),
    }

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_csv = csv_path.with_suffix(".csv.tmp")
    tmp_meta = meta_path.with_suffix(".json.tmp")

    df.to_csv(tmp_csv, index=False)
    with tmp_meta.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    tmp_csv.replace(csv_path)
    tmp_meta.replace(meta_path)

def get_fred_series_df(series_id, cache_ttl_seconds=86400, cache_dir="cache"):
    cache_dir_path = Path(cache_dir)
    csv_path = cache_dir_path / f"fred_{series_id}.csv"
    meta_path = cache_dir_path / f"fred_{series_id}_meta.json"

    # 1) try fresh cache
    meta = load_cache_meta(meta_path)
    if meta and csv_path.exists() and is_cache_fresh(meta, cache_ttl_seconds):
        return load_cache_df(csv_path)

    # 2) try API
    try:
        api_key = get_api_key()
        raw_json = fetch_fred_json(series_id, api_key)
        observations = raw_json.get("observations", [])
        if not isinstance(observations, list) or len(observations) == 0:
            raise RuntimeError("No observations returned")

        cleaned = parse_observations(observations)
        if len(cleaned) == 0:
            raise RuntimeError("All observations were filtered out during parsing")

        df = pd.DataFrame(cleaned).sort_values("date").reset_index(drop=True)

        save_cache(df, series_id, csv_path, meta_path)
        return df

    except Exception as api_err:
        # 3) API failed, try stale cache
        try:
            if csv_path.exists() and meta:
                df = load_cache_df(csv_path)
                warnings.warn(
                    f"Using stale cached data for {series_id}. "
                    f"Pulled at {meta.get('pulled_at')}, "
                    f"max observation date {meta.get('max_observation_date')}. "
                    f"API error: {api_err}"
                )
                return df
        except Exception as cache_err:
            raise RuntimeError(
                f"Cache is corrupted/unusable AND API request failed. "
                f"API error: {api_err}. Cache error: {cache_err}."
            ) from api_err

        raise

# enable the main guard to call the functions and validate that the file runs successfully here
if __name__ == "__main__":
    df = get_fred_series_df("DGS10")
    print(df.head())