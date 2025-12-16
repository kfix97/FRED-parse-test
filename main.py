# parse API responses from the FRED API

# steps:
# 0) environment setup and import libraries
# 1) construct Request URL
# 2) send request to FRED API, get and validate response
# 3) parse and clean raw json response
# 4) load clean data to pandas df
# 5) plot data points from pandas df

# step 0: import libraries and setup environment

# 0a) import libraries
from dotenv import load_dotenv
import requests
import sys
import pandas
import os
from datetime import date
from datetime import datetime
import pandas as pd

# 0b) get environment variables from config file (API key)
load_dotenv()

# step 1: construct request URL

# 1a) prompt end-user to input the series ID of choice
SeriesID = "DGS10" # str(input("Enter the SeriesID for the dataset --> "))

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

# 2d) print the column headers
# print(raw_json.keys())

# 2e) print a preview of the response
json_limit = 1
observations = raw_json["observations"]
preview = observations[:json_limit]
print("json preview: " + str(preview))

# step 3: parse and clean raw json response

# 3a) define the key that contains the repeating records
observations = observations # the observations list contains the rows of data

# 3b) confirm presence of the key and that the value is a list
number_of_observations = len(observations)

if number_of_observations < 1:
    print("No rows returned in the specified dataset")
    sys.exit()
else:
    print("Found some freakin' data!!")

# 3c) inspect one observation row and look at the fields:
# - date and value are the two key fields here for the x and y axes of a potential chart, respectively
# i. drop observations with missing values in either date or value
# ii. drop other key/value pairs besides date and value
# iii. convert values to numeric data type and dates to a data type of date

# 3d) transform raw observations to a smaller, cleaned dict with the logic above

cleaned_observations = []

for obs in observations:
    # step (ii) above mentions dopping all key/value pairs besides date and value, simply focus on these two
    raw_date = obs["date"]
    raw_value = obs["value"]
    
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

number_of_cleaned_observations = len(cleaned_observations)
print("Of the original " + str(number_of_observations) + " data points, "
       + str(number_of_cleaned_observations) + " passed the data validation check meaning that "
       + str(number_of_observations - number_of_cleaned_observations) + " were invalid")


# step 4: load clean data to pandas df

# 4a) load data to df
df = pd.DataFrame(cleaned_observations)

# 4b) df validation checks
# df.head()
# df.dtypes()
# len(df)

# 4c) print sample df data
print(df.head(10))

# step 5: plot data points from pandas df