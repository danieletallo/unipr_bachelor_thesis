# # ## 1
# # ## 1
# # ## 1
# import pandas as pd
# import matplotlib.pyplot as plt
# from matplotlib.ticker import MultipleLocator


# ### Plotter efficiency_by_duration_bins.csv
# # dataframe come il tuo
# df = pd.read_csv("efficiency_by_duration_bins_under60_by5_TOTAL.csv")

# fig, ax = plt.subplots(figsize=(8,5))
# ax.plot(df["duration_bin"], df["median_over_pct"], marker="o", color="steelblue", linewidth=2)

# ax.yaxis.set_major_locator(MultipleLocator(10))   # major ticks ogni 10
# # ax.yaxis.set_minor_locator(MultipleLocator(5))    # minor ticks ogni 5 (opzionale)
# ax.grid(True, which="both", linestyle="--", alpha=0.3)

# # Reference line at 0%
# ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)

# # Fill areas to show faster/slower trips
# ax.fill_between(df["duration_bin"], df["median_over_pct"], 0,
#                 where=(df["median_over_pct"] < 0),
#                 color="lightgreen", alpha=0.3, label="Faster than Dijkstra")
# ax.fill_between(df["duration_bin"], df["median_over_pct"], 0,
#                 where=(df["median_over_pct"] > 0),
#                 color="salmon", alpha=0.3, label="Slower than Dijkstra")

# ax.set_xlabel("Trip duration (minutes range)")
# ax.set_ylabel("Median deviation vs legal shortest path (%)")
# # ax.set_title("Difference between real trip duration and legal shortest path")
# ax.grid(True, linestyle="--", alpha=0.3)
# ax.legend()
# plt.tight_layout()
# plt.show()

## 2
## 2
## 2

# !/usr/bin/env python3
# !/usr/bin/env python3
# !/usr/bin/env python3
# """
# Plot stacked horizontal bars showing legal vs illegal cycling distance
# by road type (highway). English labels, legend below (bottom right).
# Thesis-ready style.
# """

# import pandas as pd
# import matplotlib.pyplot as plt

# # === 1. Load dataset ===
# df = pd.read_csv("roads_analysis.csv")

# # Convert meters to kilometers
# df[["Legal_Distance_m", "Illegal_Distance_m", "Total_Distance_m"]] /= 1000

# # Sort by total distance for better visual order
# df = df.sort_values("Total_Distance_m", ascending=True)

# # === 2. Prepare data ===
# legal = df["Legal_Distance_m"]
# illegal = df["Illegal_Distance_m"]
# labels = df["highway"]
# total_all = df["Overall_Total_Distance_m"].iloc[0] / 1000   # 625017.36 km

# # === 3. Create the plot ===
# fig, ax = plt.subplots(figsize=(8, 5))

# # Stacked horizontal bars (scaled to the global total)
# ax.barh(labels, legal, color="green", label="Legal distance", alpha=0.85)
# ax.barh(labels, illegal, left=legal, color="red", label="Illegal distance", alpha=0.8)

# # === 4. Add total + % labels ===
# for i, (leg, ill, total, pct) in enumerate(zip(
#     legal, illegal, df["Total_Distance_m"], df["Legal_Percentage"]
# )):
#     ax.text(
#         total_all * 0.01 + leg + ill,      # a little offset to the right
#         i,
#         f"{total:,.0f} km  ({pct:.1f}%)",
#         va="center", ha="left", fontsize=8, color="#333333"
#     )

# # === 5. Style ===
# ax.set_xlabel("Distance (km)", fontsize=10)
# ax.set_ylabel("Street type", fontsize=10)
# # ax.set_title("Legal vs illegal cycling distance by road type", fontsize=11, pad=10)

# ax.set_xlim(0, total_all)   # <<< fixed global total on x-axis
# ax.grid(axis="x", linestyle="--", alpha=0.3)
# ax.invert_yaxis()

# # === 6. Legend below (bottom right) ===
# plt.tight_layout(rect=[0, 0.05, 1, 1])

# # fig.legend(
# #     loc="lower right",
# #     bbox_to_anchor=(0.98, 0.0),
# #     ncol=2,
# #     frameon=False,
# #     fontsize=9
# # )

# ax.legend(
#     loc="lower right",
#     bbox_to_anchor=(1, 0.02),
#     frameon=True,
#     fontsize=9
# )

# plt.subplots_adjust(bottom=0.15)
# plt.show()


## 3
## 3
## 3

import pandas as pd
import matplotlib.pyplot as plt

# === Parametri ===
csv_path = "critical_edges.csv"
top_n = 10

# === Caricamento ===
cols = ["StreetName","IllegalDistance_m","LegalDistance_m","TotalDistance_m","LegalPct"]
df = pd.read_csv(csv_path, usecols=cols)

# ✅ Raggruppa per nome della via (somma distanze)
df = (
    df.groupby("StreetName", as_index=False)
      .agg({
          "IllegalDistance_m":"sum",
          "LegalDistance_m":"sum",
          "TotalDistance_m":"sum"
      })
)
df["LegalPct"] = (df["LegalDistance_m"] / df["TotalDistance_m"]) * 100

# Conversione in km
df["Illegal_km"] = df["IllegalDistance_m"] / 1000
df["Legal_km"]   = df["LegalDistance_m"]   / 1000
df["Total_km"]   = df["TotalDistance_m"]   / 1000

# Ordina e prendi le top vie
df = df.sort_values("Total_km", ascending=False).head(top_n)

# === Plot ===
fig, ax = plt.subplots(figsize=(9, 5))

ax.barh(df["StreetName"], df["Legal_km"], color="green", alpha=0.85, label="Legal distance")
ax.barh(df["StreetName"], df["Illegal_km"], left=df["Legal_km"], color="red", alpha=0.8, label="Illegal distance")

# Etichette a destra
for y, (tot, pct, leg, ill) in enumerate(zip(df["Total_km"], df["LegalPct"], df["Legal_km"], df["Illegal_km"])):
    ax.text(
        leg + ill + df["Total_km"].max() * 0.01,
        y,
        f"{tot:,.0f} km  ({pct:.1f}%)",
        va="center", ha="left", fontsize=8, color="#333333"
    )

ax.set_xlim(0, df["Total_km"].max() * 1.22)


ax.set_xlabel("Distance (km)")
# ax.set_ylabel("Street")
# ax.set_title("Top streets by illegal cycling distance (m)", fontsize=11, pad=10)
ax.grid(axis="x", linestyle="--", alpha=0.3)
ax.invert_yaxis()

plt.tight_layout(rect=[0, 0.05, 1, 1])
# fig.legend(loc="lower right", bbox_to_anchor=(0.98, 0.0), ncol=2, frameon=False, fontsize=9)
ax.legend(
    loc="lower right",
    bbox_to_anchor=(1, 0.02),
    frameon=True,
    fontsize=9
)
plt.subplots_adjust(bottom=0.15)
plt.show()
