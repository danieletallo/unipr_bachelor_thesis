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
    usecols = ["ActivityId", "Node_From", "Node_To", "Key", "IsLegal", "DistanceTraveled_m"]
    df = pd.read_csv(csv_path, usecols=usecols)
    print(f"Total segments (raw): {len(df)}")

    # Remove first and last edge per activity (to avoid GPS noise)
    cleaned_segments = []
    for _, group in df.groupby("ActivityId", sort=False):
        if len(group) > 2:
            cleaned_segments.append(group.iloc[1:-1])
    cleaned_df = pd.concat(cleaned_segments, ignore_index=True)

    # Keep only valid distances
    cleaned_df = cleaned_df[
        cleaned_df["DistanceTraveled_m"].fillna(0) > 0
    ].copy()

    # Convert columns to appropriate data types for joining
    for col in ["Node_From", "Node_To"]:
        cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors="coerce").astype("Int64")
    if "Key" not in cleaned_df.columns:
        raise ValueError("The column 'Key' is missing in the segments.")
    cleaned_df["Key"] = cleaned_df["Key"].astype(str)

    # Ensure boolean type for IsLegal
    cleaned_df["IsLegal"] = cleaned_df["IsLegal"].astype(bool)

    print(f"Cleaned segments: {len(cleaned_df)} (legal: {(cleaned_df['IsLegal']).sum()})")
    return cleaned_df

def build_edges_from_pbf(pbf_path):
    """
    Extract edges from the PBF file replicating the pipeline:
    Pyrosm -> (nodes, edges) -> OSMnx graph -> simplify_graph -> simplified edges.
    Returns u, v, key, highway consistent with the simplification.
    """
    from pyrosm import OSM
    import pandas as pd
    import osmnx as ox

    extra_attrs = ["oneway", "highway", "cycleway", "bicycle"]
    osm = OSM(pbf_path)

    # 1) Extract nodes and edges with necessary tags
    nodes_gdf, edges_gdf = osm.get_network(
        network_type="cycling",
        extra_attributes=extra_attrs,
        nodes=True
    )

    # 2) NODES: index = osmid, columns x, y from geometry
    nodes = nodes_gdf.copy()
    if "id" not in nodes.columns:
        raise KeyError("The column 'id' is missing in nodes.")
    nodes = nodes.dropna(subset=["id"]).copy()
    nodes["osmid"] = pd.to_numeric(nodes["id"], errors="coerce")
    nodes = nodes.dropna(subset=["osmid"]).copy()
    nodes["osmid"] = nodes["osmid"].astype("int64")

    # Extract x, y from geometry (pyrosm provides geometry=Point)
    nodes["x"] = nodes.geometry.x
    nodes["y"] = nodes.geometry.y
    nodes = nodes.set_index("osmid")

    # 3) EDGES: ensure u, v are int64 and key is unique for (u, v)
    edges = edges_gdf.copy()
    for col in ("u", "v"):
        if col not in edges.columns:
            raise KeyError(f"The column '{col}' is missing in edges.")
        edges[col] = pd.to_numeric(edges[col], errors="coerce")
    edges = edges.dropna(subset=["u", "v"]).copy()
    edges["u"] = edges["u"].astype("int64")
    edges["v"] = edges["v"].astype("int64")

    # Create 'key' if missing or not unique
    if "key" not in edges.columns or edges.duplicated(["u", "v", "key"]).any():
        edges = edges.sort_values(["u", "v"]).copy()
        edges["key"] = edges.groupby(["u", "v"]).cumcount()

    # MultiIndex (u, v, key) before graph_from_gdfs
    edges = edges.set_index(["u", "v", "key"]).sort_index()

    # 4) Build and simplify graph
    G = ox.graph_from_gdfs(nodes, edges)   # edges now have the correct MultiIndex
    G = ox.simplify_graph(G)

    # 5) Export simplified edges
    _, e = ox.graph_to_gdfs(G, nodes=True, edges=True)
    e = e.reset_index()

    # Ensure 'key' consistency and normalize 'highway'
    if "key" not in e.columns or e.duplicated(["u", "v", "key"]).any():
        e = e.sort_values(["u", "v"]).copy()
        e["key"] = e.groupby(["u", "v"]).cumcount()

    def normalize_highway(h):
        if isinstance(h, (list, tuple)) and len(h) > 0:
            return h[0]
        return h
    e["highway"] = e["highway"].apply(normalize_highway) if "highway" in e.columns else "unknown"

    e["key"] = e["key"].astype(str)  # for joining with segments (Key)
    return e[["u", "v", "key", "highway"]]

def merge_segments_with_edges(segments_df, edges_df):
    """Merge segments with edge data, trying both directions (coalescing results)."""
    # Direct merge on (Node_From, Node_To, Key)
    direct = segments_df.merge(
        edges_df.rename(columns={"u": "Node_From", "v": "Node_To", "key": "Key"}),
        on=["Node_From", "Node_To", "Key"],
        how="left"
    )

    # Reverse merge on (Node_To, Node_From, Key)
    rev_edges = edges_df.rename(columns={"u": "Node_To", "v": "Node_From", "key": "Key"})[
        ["Node_From", "Node_To", "Key", "highway"]
    ]
    reverse = segments_df.merge(
        rev_edges,
        on=["Node_From", "Node_To", "Key"],
        how="left",
        suffixes=("", "_rev")
    )

    # Coalesce: use highway from direct, if NaN use from reverse
    merged = direct.copy()
    merged["highway"] = merged["highway"].fillna(reverse["highway"])

    return merged

def analyze_road_types(merged_df):
    """Analyze road types by total vs legal distance."""
    merged_df["highway"] = merged_df["highway"].fillna("unknown")

    # Add column showing the total of all DistanceTraveled_m after cleaning
    merged_df["Overall_Total_Distance_m"] = merged_df["DistanceTraveled_m"].sum()

    # Consider only relevant road types
    valid_highways = {"primary", "secondary", "tertiary", "residential", "pedestrian", "footway", "living_street", "cycleway"}
    merged_df = merged_df[merged_df["highway"].isin(valid_highways)].copy()

    # Calculate total and legal distances by road type
    total_distance = merged_df.groupby("highway", observed=True)["DistanceTraveled_m"].sum()
    legal_distance = merged_df[merged_df["IsLegal"]].groupby("highway", observed=True)["DistanceTraveled_m"].sum()

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
