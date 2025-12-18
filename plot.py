# plot data from the fred data call

import matplotlib.pyplot as plt
from fred_data_call import get_fred_series_df

df = get_fred_series_df("DGS10") # series ID for the 10-yr treasury yield
# print(df.head(2))

plt.scatter(df["date"], df["value"], s=1)
plt.title("10-year treasury yield over time")
plt.xlabel("Date")
plt.ylabel("Yield (%)")
plt.show()