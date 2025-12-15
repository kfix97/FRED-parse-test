# parse API responses from the FRED API

# steps:
# 0) environment setup and import libraries
# 1) construct Request URL
# 2) send request to FRED API, get and validate response
# 3) parse raw json response to python dicts
# 4) convert python dicts to pandas df
# 5) plot data points from pandas df

# step 0: import libraries and setup environment

# 0a) import libraries
from dotenv import load_dotenv
import requests
import pandas
import os
from datetime import date

# 0b) get environment variables from config file (API key)
load_dotenv()

# step 1: construct request URL

# 1a) prompt end-user to input the series ID of choice
SeriesID = str(input("Enter the SeriesID for the dataset --> "))

# 1b) read the API key from the .env file
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY not found. Check your .env file.")

# 1c) define URL components
BASE_URL = str("https://api.stlouisfed.org/fred")
endpoint = "/series/observations"
params = {
    "series_id" : SeriesID, # the specified dataset - required
    "api_key" : API_KEY,   # the FRED API key - required
    "file_type" : "json"   # json format vs xml - required
    #,"sort_order" : "desc"  # sorting the data descending by observation_date - optional
    # ,"observation_start" : date.today() # start date of the dataset - optional
    # ,"observation_end" =    # end date of the dataset - optional
}

# step 2: send request to FRED API, get and validate response

# 2a) make the get request and store the response in a variable
response = requests.get(BASE_URL + endpoint, params=params)

# 2b) check the status of the response
response.raise_for_status()

# 2c) store the raw json in a variable
raw_json = response.json()

# 2d) print the get url and response for validation
print(raw_json.keys())
print(raw_json)
