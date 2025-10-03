import pandas as pd
import numpy as np

# 1) Load the file
df = pd.read_csv("dijkstra_results.csv")

# 2) Clean the minimum required data
df = df.dropna(subset=["Time_s", "DijkstraTime_s"]).copy()
df = df[(df["Time_s"] > 0) & (df["DijkstraTime_s"] > 0)]

# 3) Metrics: how much slower/faster than theoretical
df["efficiency_ratio"] = df["Time_s"] / df["DijkstraTime_s"]         # 1 = same as theoretical; >1 = slower
df["over_pct"] = (df["Time_s"] - df["DijkstraTime_s"]) / df["DijkstraTime_s"] * 100

# 4) Actual minutes and bins
df["real_minutes"] = (df["Time_s"] // 60).astype(int)
bins = [0, 5, 10, 15, 20, 30, 45, 60, 90, 120, np.inf]
labels = ["0–<5", "5–<10", "10–<15", "15–<20", "20–<30", "30–<45", "45–<60", "60–<90", "90–<120", ">=120"]
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
summary.to_csv("efficiency_by_duration_bins.csv", index=False)
print(summary)
print("\nSaved in efficiency_by_duration_bins.csv")
