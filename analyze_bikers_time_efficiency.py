import pandas as pd
import numpy as np

# 1) Load the file
df = pd.read_csv("dijkstra_results_from_points_cleaned.csv")

# 2) Clean the minimum required data
df = df.dropna(subset=["Time_s", "DijkstraTime_s"]).copy()
df = df[(df["Time_s"] > 0) & (df["DijkstraTime_s"] > 0)]

# 3) Metrics: how much slower/faster than theoretical
df["efficiency_ratio"] = df["Time_s"] / df["DijkstraTime_s"]         # 1 = same as theoretical; >1 = slower
df["over_pct"] = (df["Time_s"] - df["DijkstraTime_s"]) / df["DijkstraTime_s"] * 100

# 4) Actual minutes and bins
df["real_minutes"] = (df["Time_s"] // 60).astype(int)
bins = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
labels = ["0-5", "5-10", "10-15", "15-20", "20-25", "25-30", "30-35", "35-40", "40-45", "45-50", "50-55", "55-60"]
df["duration_bin"] = pd.cut(df["real_minutes"], bins=bins, labels=labels, right=False)

# 5) Summary by bin: count, mean, and median
summary = (df.groupby("duration_bin")
             .agg(
                 n=("ActivityId", "count"),
                 mean_over_pct=("over_pct", "mean"),
                 median_over_pct=("over_pct", "median"),
                 mean_efficiency=("efficiency_ratio", "mean"),
                 median_efficiency=("efficiency_ratio", "median")
             )
             .reset_index())

# 6) Save and display
summary.to_csv("efficiency_by_duration_bins_under60_by5_TOTAL.csv", index=False)
print(summary)
print("\nSaved in efficiency_by_duration_bins_under60_by5_TOTAL.csv")

# # Results:
# #    duration_bin      n  mean_over_pct  median_over_pct  mean_efficiency  median_efficiency
# 0           0-5  17478     104.651536       -26.483322         2.046515           0.735167
# 1          5-10  52720      14.852305       -14.065157         1.148523           0.859348
# 2         10-15  56795     134.115358        -4.662012         2.341154           0.953380
# 3         15-20  42881     140.877899         3.068036         2.408779           1.030680
# 4         20-25  27669     847.244594        10.319946         9.472446           1.103199
# 5         25-30  17849    1333.647591        20.731520        14.336476           1.207315
# 6         30-35  11322     795.184658        36.839548         8.951847           1.368395
# 7         35-40   7221     615.020543        57.489337         7.150205           1.574893
# 8         40-45   4961    1035.028301        81.326388        11.350283           1.813264
# 9         45-50   3491   13560.201050       111.436357       136.602010           2.114364
# 10        50-55   2485    2109.111262       155.213934        22.091113           2.552139
# 11        55-60   1895    4965.163476       233.082339        50.651635           3.330823