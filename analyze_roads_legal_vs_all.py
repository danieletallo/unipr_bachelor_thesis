import os
import pandas as pd
import numpy as np
from pyrosm import OSM
import osmnx as ox

# Configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
segments_csv = os.path.join(script_dir, "segments_all_activities.csv")
pbf_path = os.path.join(script_dir, "osrm", "bologna-2018.osm.pbf")

def clean_segments(csv_path):
    """Clean and filter segments data."""
    usecols = ["ActivityId","Nodo_Da","Nodo_A","Key","IsLegal","DistanzaPercorsa_m"]
    df = pd.read_csv(csv_path, usecols=usecols)
    print(f"Total segments (raw): {len(df)}")
    
    # Remove first and last edge per activity (to avoid GPS cloud)
    cleaned_segments = []
    for _, group in df.groupby("ActivityId", sort=False):
        if len(group) > 2:
            cleaned_segments.append(group.iloc[1:-1])
    cleaned_df = pd.concat(cleaned_segments, ignore_index=True)

    # Keep only valid distances
    cleaned_df = cleaned_df[
        cleaned_df["DistanzaPercorsa_m"].fillna(0) > 0
    ].copy()

    # Dtypes for join
    for col in ["Nodo_Da", "Nodo_A"]:
        cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors="coerce").astype("Int64")
    if "Key" not in cleaned_df.columns:
        raise ValueError("Manca la colonna 'Key' nei segmenti.")
    cleaned_df["Key"] = cleaned_df["Key"].astype(str)

    # Ensure boolean
    cleaned_df["IsLegal"] = cleaned_df["IsLegal"].astype(bool)

    print(f"Cleaned segments: {len(cleaned_df)} (legal: {(cleaned_df['IsLegal']).sum()})")
    return cleaned_df

def build_edges_from_pbf(pbf_path):
    """
    Estrae edges dal PBF e garantisce: u, v, key, highway.
    Usa nodes=True per avere la topologia (u/v).
    """
    from pyrosm import OSM
    import pandas as pd
    import numpy as np

    osm = OSM(pbf_path)

    # IMPORTANTISSIMO: nodes=True -> crea topologia con u/v
    # network_type="all" per includere footway, path, steps, ecc.
    nodes_gdf, edges_gdf = osm.get_network(
        network_type="all",
        nodes=True
    )

    e = edges_gdf.copy()

    # Verifica che u/v esistano davvero
    if "u" not in e.columns or "v" not in e.columns:
        raise KeyError(
            "Mancano le colonne 'u'/'v'. Assicurati di aver passato nodes=True a get_network()."
        )

    # Dtypes coerenti
    e["u"] = pd.to_numeric(e["u"], errors="coerce").astype("Int64")
    e["v"] = pd.to_numeric(e["v"], errors="coerce").astype("Int64")

    # Crea 'key' se manca o non è univoca
    if "key" not in e.columns or e.duplicated(["u","v","key"]).any():
        e = e.sort_values(["u","v"]).copy()
        e["key"] = e.groupby(["u","v"]).cumcount()

    # Normalizza highway (può essere lista)
    def norm_hw(h):
        if isinstance(h, (list, tuple)) and len(h) > 0:
            return h[0]
        return h

    e["highway"] = e["highway"].apply(norm_hw)
    e["key"] = e["key"].astype(str)  # per il join con i segmenti (Key)

    return e[["u","v","key","highway"]]


def merge_segments_with_edges(segments_df, edges_df):
    """Merge segments with edge data, trying both directions (coalescing results)."""
    # Merge diretto su (Nodo_Da, Nodo_A, Key)
    direct = segments_df.merge(
        edges_df.rename(columns={"u": "Nodo_Da", "v": "Nodo_A", "key": "Key"}),
        on=["Nodo_Da", "Nodo_A", "Key"],
        how="left"
    )

    # Merge invertito su (Nodo_A, Nodo_Da, Key)
    rev_edges = edges_df.rename(columns={"u": "Nodo_A", "v": "Nodo_Da", "key": "Key"})[
        ["Nodo_Da", "Nodo_A", "Key", "highway"]
    ]
    # ATTENZIONE: qui mergiamo di nuovo partendo da segments_df (stesso ordine/indice)
    reverse = segments_df.merge(
        rev_edges,
        on=["Nodo_Da", "Nodo_A", "Key"],
        how="left",
        suffixes=("", "_rev")
    )

    # Coalesce: usa highway del diretto, se NaN usa quella del reverse
    merged = direct.copy()
    merged["highway"] = merged["highway"].fillna(reverse["highway"])
    
    return merged


def analyze_road_types(merged_df):
    """Analyze road types by total vs legal distance."""
    merged_df["highway"] = merged_df["highway"].fillna("unknown")

    # Aggiungi colonna che mostra il totale di tutte le DistanzaPercorsa_m dopo la pulizia
    merged_df["Overall_Total_Distance_m"] = merged_df["DistanzaPercorsa_m"].sum()

    # Considera solo tipi di strada rilevanti
    valid_highways = {"primary", "secondary", "tertiary", "residential", "pedestrian","footway", "living_street", "cycleway"}
    merged_df = merged_df[merged_df["highway"].isin(valid_highways)].copy()

    # Calcola distanze totali e legali per tipo di strada
    total_distance = merged_df.groupby("highway", observed=True)["DistanzaPercorsa_m"].sum()
    legal_distance = merged_df[merged_df["IsLegal"]].groupby("highway", observed=True)["DistanzaPercorsa_m"].sum()

    summary = pd.concat(
        [total_distance.rename("Total_Distance_m"),
         legal_distance.rename("Legal_Distance_m")],
        axis=1
    ).fillna(0.0)

    summary["Illegal_Distance_m"] = summary["Total_Distance_m"] - summary["Legal_Distance_m"]
    summary["Legal_Percentage"] = (summary["Legal_Distance_m"] / summary["Total_Distance_m"]) * 100
    summary["Overall_Total_Distance_m"] = merged_df["Overall_Total_Distance_m"].iloc[0]

    return summary.sort_values("Legal_Percentage", ascending=False)

if __name__ == "__main__":
    cleaned_df = clean_segments(segments_csv)
    edges = build_edges_from_pbf(pbf_path)
    print(f"Edges from PBF: {len(edges)}")

    merged_data = merge_segments_with_edges(cleaned_df, edges)

    summary = analyze_road_types(merged_data)
    
    output_file = os.path.join(script_dir, "roads_analysis.csv")
    summary.to_csv(output_file, index=True)
    print(f"Report saved: {output_file}")

    print("\nRoad Type Analysis (Top 20):")
    print(summary.head(20))
