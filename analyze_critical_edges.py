# analyze_critical_edges.py
import pandas as pd
import numpy as np

# Read dataset
df = pd.read_csv("segments_all_activities.csv")

# --- Skip first and last row of each trip ---
to_drop = []
for activity_id, group in df.groupby("ActivityId"):
    if len(group) > 2:
        to_drop.extend([group.index[0], group.index[-1]])
df = df.drop(to_drop)

# --- Normalizza archi: (u,v,key) e (v,u,key) diventano uguali ---
# Ordino i due nodi così: (min, max)
df["Node_From"] = df[["Nodo_Da", "Nodo_A"]].min(axis=1)
df["Node_To"]   = df[["Nodo_Da", "Nodo_A"]].max(axis=1)
df["Key"] = df["Key"]

# --- Calcolo distanza legale/illegale ---
agg = df.groupby(["Node_From", "Node_To", "Key", "NomeVia", "IsLegal"])["DistanzaPercorsa_m"].sum().unstack(fill_value=0)
agg = agg.rename(columns={False: "IllegalDistance_m", True: "LegalDistance_m"}).reset_index()

# --- Totale ---
agg["TotalDistance_m"] = agg["IllegalDistance_m"] + agg["LegalDistance_m"]
agg["LegalPct"] = np.where(
    agg["TotalDistance_m"] > 0,
    (agg["LegalDistance_m"] / agg["TotalDistance_m"]) * 100.0,
    np.nan
)

# --- Prendi i top 10 archi per IllegalDistance_m ---
critical = agg.sort_values("IllegalDistance_m", ascending=False).head(10)

# --- Salva su CSV ---
critical.to_csv("critical_edges.csv", index=False)

print("Saved top 10 critical edges to critical_edges.csv")
