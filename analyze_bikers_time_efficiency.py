import pandas as pd
import numpy as np

# 1) Carica il file prodotto dal tuo script
df = pd.read_csv("dijkstra_results.csv")

# 2) Pulisci i dati minimi necessari
df = df.dropna(subset=["Time_s", "DijkstraTime_s"]).copy()
df = df[(df["Time_s"] > 0) & (df["DijkstraTime_s"] > 0)]

# 3) Metriche: quanto sono più lenti/veloci del teorico
df["efficiency_ratio"] = df["Time_s"] / df["DijkstraTime_s"]         # 1 = uguale al teorico; >1 = più lento
df["over_pct"] = (df["Time_s"] - df["DijkstraTime_s"]) / df["DijkstraTime_s"] * 100

# 4) Minuti reali e fasce (modifica i bin se vuoi più/meno dettagli)
df["real_minutes"] = (df["Time_s"] // 60).astype(int)
bins = [0, 5, 10, 15, 20, 30, 45, 60, 90, 120, np.inf]
labels = ["0–<5", "5–<10", "10–<15", "15–<20", "20–<30", "30–<45", "45–<60", "60–<90", "90–<120", ">=120"]
df["duration_bin"] = pd.cut(df["real_minutes"], bins=bins, labels=labels, right=False)

# 5) Riepilogo per fascia: conteggio, media e mediana
summary = (df.groupby("duration_bin")
             .agg(
                 n=("ActivityId", "count"),
                 mean_over_pct=("over_pct", "mean"),
                 median_over_pct=("over_pct", "median"),
                 mean_efficiency=("efficiency_ratio", "mean"),
                 median_efficiency=("efficiency_ratio", "median")
             )
             .reset_index())

# 6) Salva e mostra
summary.to_csv("efficiency_by_duration_bins.csv", index=False)
print(summary)
print("\nSalvato in efficiency_by_duration_bins.csv")
