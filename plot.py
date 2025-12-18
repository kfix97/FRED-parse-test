# plot data fetched from the FRED API

from fred_data_call import get_fred_series_df

df = get_fred_series_df("DGS10")
print(df.head(2))