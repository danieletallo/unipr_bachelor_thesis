## Dijkstra's Algorithm Implementation
# Using the .osm.pbf file from 2018
# Create the graph with edges weighted based on the estimated times from the file "edges_with_estimated_times.csv"
# To determine the direction of travel, refer to "map_via_nearestedge_osmnx.py"
import os
import osmnx as ox
import networkx as nx
from pyrosm import OSM
import pandas as pd
import geopandas as gpd
import contextily as ctx
import matplotlib.pyplot as plt
from shapely import LineString
from shapely.ops import substring
from shapely.geometry import Point

def normalize_nodes_and_edges(nodes, edges):
    # ---------- NORMALIZE NODES ----------
    nodes = nodes.rename(columns={'id': 'osmid'})
    nodes = nodes.rename(columns={'lon': 'x', 'lat': 'y'})

    # Clean and set consistent index
    nodes = nodes.dropna(subset=['osmid']).copy()
    nodes['osmid'] = pd.to_numeric(nodes['osmid'], errors='coerce')
    nodes = nodes.dropna(subset=['osmid']).copy()
    nodes['osmid'] = nodes['osmid'].astype('int64')
    nodes = nodes.set_index('osmid')

    # ---------- NORMALIZE EDGES ----------
    # u/v must exist and have the same dtype as nodes.index
    for col in ('u', 'v'):
        if col not in edges.columns:
            raise ValueError(f"Missing column '{col}' in edges.")
    edges = edges.dropna(subset=['u','v']).copy()
    edges['u'] = pd.to_numeric(edges['u'], errors='coerce')
    edges['v'] = pd.to_numeric(edges['v'], errors='coerce')
    edges = edges.dropna(subset=['u','v']).copy()
    edges['u'] = edges['u'].astype('int64')
    edges['v'] = edges['v'].astype('int64')

    # FILTER edges pointing to nodes NOT present (typical after bbox)
    mask_uv_ok = edges['u'].isin(nodes.index) & edges['v'].isin(nodes.index)
    edges = edges.loc[mask_uv_ok].copy()

    # Create 'key' if missing or if it does not guarantee uniqueness
    if 'key' not in edges.columns or edges.duplicated(['u','v','key']).any():
        edges['key'] = edges.groupby(['u','v']).cumcount()

    # Set required MultiIndex (u, v, key)
    edges = edges.set_index(['u','v','key']).sort_index()
    
    return nodes, edges
    
#######################
#######################

# ------------------------------
#  BIKE-DIRECTION (only 4 tags)
# ------------------------------
FORBIDDEN_HW = {"motorway", "motorway_link"}  # remove highways and ramps


def _highway_vals(d):
    """Handle highway as string, list, or 'a;b'."""
    hw = d.get("highway")
    if isinstance(hw, list):
        vals = hw
    elif isinstance(hw, str):
        vals = [s.strip().lower() for s in hw.split(";")]
    else:
        vals = []
    return set(v.lower() for v in vals)

def _invert_geom(g):
    return LineString(list(g.coords)[::-1]) if isinstance(g, LineString) else g

def _val(d, k):
    """Valore normalizzato (gestisce liste post-simplify)."""
    v = d.get(k)
    if isinstance(v, list):
        v = v[0] if v else None
    return (str(v).strip().lower() if v is not None else "")


def _bike_dir_from_basic_tags(ed):
    """
    Usa: oneway, oneway:bicycle, highway, cycleway, cycleway:left/right/both, bicycle.
    Ritorna: 'none' | 'forward' | 'backward' | 'both'
    """
    # bici vietate?
    if _val(ed, "bicycle") in {"no", "dismount"}:
        return "none"
    if _highway_vals(ed) & FORBIDDEN_HW:
        return "none"

    hw      = _val(ed, "highway")
    cyc     = _val(ed, "cycleway")
    cyc_l   = _val(ed, "cycleway:left")
    cyc_r   = _val(ed, "cycleway:right")
    cyc_b   = _val(ed, "cycleway:both")
    ow      = _val(ed, "oneway")
    ow_bike = _val(ed, "oneway:bicycle")

    # 1) pista dedicata → bidirezionale salvo oneway esplicito
    if hw == "cycleway":
        if ow in {"yes", "1", "true"} or ow_bike in {"yes", "1", "true"}:
            return "forward"
        if ow == "-1" or ow_bike == "-1":
            return "backward"
        return "both"

    # 2) opposte o "both" (qualunque tag con 'opposite*' o cycleway:both valido) → bidirezionale
    def has_opposite(s): 
        return any(tok in s for tok in ("opposite", "opposite_lane", "opposite_track", "opposite_share_busway"))
    if any(has_opposite(s) for s in (cyc, cyc_l, cyc_r)):
        return "both"
    if cyc_b not in ("", "no", "none", "false"):
        return "both"

    # 3) altrimenti oneway (precedenza a oneway:bicycle)
    if ow_bike in {"yes", "1", "true"}:
        return "forward"
    if ow_bike == "-1":
        return "backward"

    if ow in {"yes", "1", "true"}:
        return "forward"
    if ow == "-1":
        return "backward"

    # 4) bidirezionale generico
    return "both"


def make_bike_directed_edges(edges):
    """
    From edges (index: u,v,key) create directed bike edges:
      - remove 'none'
      - 'forward' → u->v
      - 'backward' → v->u (geometry inverted)
      - 'both' → both directions (duplicating and inverting)
    """
    df = edges.reset_index().copy()

    # Consider only essential tags
    for c in ["oneway", "highway", "cycleway", "bicycle", "geometry"]:
        if c not in df.columns:
            df[c] = None

    # Apply directionality logic
    df["bike_dir"] = df.apply(_bike_dir_from_basic_tags, axis=1)
    df = df[df["bike_dir"] != "none"].copy()

    fwd = df[df["bike_dir"].isin(["forward", "both"])].copy()

    bwd = df[df["bike_dir"].isin(["backward", "both"])].copy()
    # Invert direction and geometry
    bwd[["u", "v"]] = bwd[["v", "u"]].to_numpy()
    if "geometry" in bwd.columns:
        bwd["geometry"] = bwd["geometry"].apply(_invert_geom)

    out = pd.concat([fwd, bwd], ignore_index=True)
    out["key"] = out.groupby(["u", "v"]).cumcount()
    out = out.set_index(["u", "v", "key"]).sort_index()
    return out

def assign_edge_weights(edges, weights_csv="edges_with_estimated_times.csv"):
    """
    Assign weights to edges based on the provided CSV file.
    Modify the DataFrame edges by adding the 'weight' column.
    """
    print(">>> Assigning weights to edges based on edges_with_estimated_times.csv...")
    weights_df = pd.read_csv(weights_csv, usecols=["Node_From","Node_To","Key", "EstimatedTime_s"])
    weights_df = weights_df.rename(columns={"Node_From": "u", "Node_To": "v", "Key": "key", "EstimatedTime_s": "weight"})
    weights_df = weights_df.dropna(subset=["u","v","weight"]).copy()
    
    # Iterate through edges and assign weight if it exists in u, v or v, u
    edge_weights = {}
    weight_set = set(zip(weights_df["u"], weights_df["v"], weights_df["key"], weights_df["weight"]))
    for (u, v, key) in edges.index:
        # Search for weight in (u,v) or (v,u)
        weight = None
        for (wu, wv, wk, w) in weight_set:
            if (u == wu and v == wv and key == wk) or (u == wv and v == wu and key == wk):
                weight = w
                break
        if weight is not None:
            edge_weights[(u, v, key)] = weight
        else:
            edge_weights[(u, v, key)] = -1  # weight -1 if not found
    
    # Add weights to edges
    edges['weight'] = edges.index.map(edge_weights)
    edges['weight'] = edges['weight'].astype(float)
    print(f"Edges with assigned weight: {edges['weight'].notna().sum()} out of {len(edges)}")
    return edges

#######################

#######################


def main():
    # Load the graph from .osm.pbf file
    print(">>> Loading graph from .osm.pbf file...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pbf_path = os.path.join(script_dir, "osrm", "bologna-2018.osm.pbf")

    # Read the road graph
    osm = OSM(pbf_path)

    # Essential tags for cycling: reduce attributes to save memory
    extra_attrs = [
        "oneway", "oneway:bicycle", "bicycle", "highway",
        "cycleway", "cycleway:left", "cycleway:right", "cycleway:both"
    ]


    # Load edges and nodes
    print(">>> Loading edges and nodes...")
    nodes, edges = osm.get_network(
        network_type="cycling",
        extra_attributes=extra_attrs,
        nodes=True
    )
    
    # Normalize nodes and edges
    print(">>> Normalizing nodes and edges...")
    nodes, edges = normalize_nodes_and_edges(nodes, edges)
    
    # Load the graph with osmnx, simplify the graph to remove intermediate nodes, as in the initial segmentation
    print(">>> Creating graph with osmnx...")
    graph = ox.graph_from_gdfs(nodes, edges)
    graph = ox.simplify_graph(graph)
    
    # Retrieve edges and nodes from the simplified graph, so there are no intermediate nodes
    # If not done, intermediate nodes are considered and do not match the segments
    print(">>> Extracting nodes and edges from the simplified graph...")
    nodes, edges = ox.graph_to_gdfs(graph)
    
    # Consider true bike directionality
    print(">>> Bike directionality from 4 tags (oneway/highway/cycleway/bicycle)...")
    edges = make_bike_directed_edges(edges)
 
    # Assign weights to edges based on the CSV file   
    edges = assign_edge_weights(edges)
    # Remove edges without weight (-1)
    edges = edges[edges['weight'] >= 0].copy()
    
    # Example of an edge with weight
    example_edge = edges[edges['weight'] < float('inf')].iloc[0]
    print(f"Example of an edge with weight: u={example_edge.name[0]}, v={example_edge.name[1]}, weight={example_edge['weight']:.2f} s")
    
    # Save nodes u, v in osmid order with bidirectionality information
    print(">>> Saving nodes in nodes_graph.csv...")
    edges_df = edges.reset_index()[['u','v','key']].drop_duplicates().sort_values(['u','v','key']).copy()
    
    # Create a set of all pairs (u,v) to quickly verify existence
    edge_set = set(zip(edges_df['u'], edges_df['v'], edges_df['key']))
    
    # Add the bidirectional column indicating if (v,u) also exists
    edges_df['bidirectional'] = edges_df.apply(
        lambda row: (row['v'], row['u'], row['key']) in edge_set, axis=1
    )
    
    # Recreate the graph with attributes inside
    graph = ox.graph_from_gdfs(nodes, edges)
    
    # Save the graph in GraphML format
    ox.save_graphml(graph, "bologna_graph.graphml")
    print(">>> Saved: bologna_graph.graphml")
    
    # Print graph info
    print(f"Graph has {len(nodes)} nodes and {len(edges)} edges after processing.")

    # Save the CSV
    edges_df.to_csv("nodes_graph.csv", index=False)
    print(">>> Saved: nodes_graph.csv")



if __name__ == "__main__":
    main()