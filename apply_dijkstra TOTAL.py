# Read the graph from the file .graphml and apply Dijkstra 
# creating, for each activity, new edges from coordinates.
# The .csv format will be as follows:
# ActivityId, Node_From, Node_To, Key, Time_s, Point_Latitude, Point_Longitude, Point_DistanceFrom_NodeFrom_m, Point_DistanceFrom_NodeTo_m
# and I'll have 2 rows for each activity (one for the start point and one for the end point).
# Example:
# ActivityId	Node_From	Node_To	Key	Time_s	Point_Latitude	Point_Longitude	Point_DistanceFrom_NodeFrom_m	Point_DistanceFrom_NodeTo_m
# 1145783	250735019	390032680	0	166	44.489197	11.340536	38.59913542	51.41242241
# 1145783	251897634	341927978	0	166	44.486875	11.340436	60.75579419	6.536940847
# 1145787	3105871892	3287381534	0	904	44.500601	11.344895	62.30693521	53.90693201
# 1145787	419638731	419638736	0	904	44.491667	11.313781	33.56873446	41.09623513

# I should pick the start/end edges and create 2 new edges from the coordinates to the start/end nodes
# with weight equal to weight of the original edge / (Point_DistanceFrom_NodeFrom_m	+ Point_DistanceFrom_NodeTo_m) * :
# Point_DistanceFrom_NodeFrom_m for the edge going from the point with given coordinates to NodeFrom 
# and an edge going to Point_DistanceFrom_NodeTo_m for the edge going from NodeTo to the point with given coordinates,
# and they should use the same attributes of the original edge (oneway, etc).
# For example if the real geometry goes to NodeFrom -> ... -> NodeTo, with no opposite direction
# I should create 2 edges:
# NodeFrom -> Point (with weight proportional to Point_DistanceFrom_NodeFrom_m)
# Point -> NodeTo (with weight proportional to Point_DistanceFrom_NodeTo_m)
# and using that new graph for that activity only!

# Actual example of attributes of a node:
# (31528093, {'version': '7', 'changeset': '0', 'y': 44.454811096191406, 'x': 11.281106948852539, 'visible': 'False', 'timestamp': '1490294041', 'tags': {'highway': 'motorway_junction', 'name': 'Cantagallo Est', 'ref': 'A1'}})

# Actual example of attributes of an edge:
# (31528093, 274359331, {'highway': 'service', 'oneway': 'yes', 'timestamp': '1386537508', 'version': '5', 'tags': '{"visible":false}', 'osm_type': 'way', 'geometry': <LINESTRING (11.281 44.455, 11.281 44.456, 11.281 44.456, 11.281 44.456, 11....>, 'length': 148.069, 'bike_dir': 'both', 'weight': 225.0848235048394})
import time
import os
import pandas as pd
import networkx as nx
from osmnx import io as oxio

# === Load base graph ===
script_dir = os.path.dirname(os.path.abspath(__file__))
graphml_path = os.path.join(script_dir, "bologna_graph.graphml")

graph = oxio.load_graphml(graphml_path, edge_dtypes={"weight": float, "oneway": str})
print(">>> Graph loaded")

# === Load activities ===
csv_path = os.path.join(script_dir, "cleaned_paths_for_dijkstra_TOTAL.csv")
df = pd.read_csv(csv_path)
print(f">>> Loaded {len(df)} rows")

results = []

# === Helper: add edges for a GPS point ===
def add_point_edges(G, row, point_name, activity_id):
    node_from = int(row["Node_From"])
    node_to = int(row["Node_To"])
    key = int(row["Key"])
    dist_from = row["Point_DistanceFrom_NodeFrom_m"]
    dist_to = row["Point_DistanceFrom_NodeTo_m"]

    point_node = f"{point_name}_{activity_id}"
    G.add_node(point_node, x=row["Point_Longitude"], y=row["Point_Latitude"])

    def create_edges(u, v, key, df, dt):
        if (u, v, key) not in G.edges(keys=True):
            return
        edge_data = G.get_edge_data(u, v, key)
        total = df + dt
        if total == 0:
            return
        w_from = edge_data["weight"] * (df / total)
        w_to = edge_data["weight"] * (dt / total)

        # c
        edge_attrs = {k: v for k, v in edge_data.items() if k != "weight"}

        # aggiungi archi con i nuovi pesi
        G.add_edge(u, point_node, weight=w_from, **edge_attrs)
        G.add_edge(point_node, v, weight=w_to, **edge_attrs)

    # principale
    create_edges(node_from, node_to, key, dist_from, dist_to)
    # opposta (se bidirezionale)
    create_edges(node_to, node_from, key, dist_to, dist_from)

    return point_node


# === Main loop ===
print(f">>> Starting Dijkstra path calculations for {len(df['ActivityId'].unique())} activities...")
for i, (activity_id, group) in enumerate(df.groupby("ActivityId"), start=1):
    if len(group) != 2:
        continue

    start_row = group.iloc[0]
    end_row = group.iloc[1]
    real_time_s = group["Time_s"].iloc[0]

    # G = graph.copy() # too slow
    G = graph

    start_point = add_point_edges(G, start_row, "startpoint", activity_id)
    end_point = add_point_edges(G, end_row, "endpoint", activity_id)

    try:
        length = nx.dijkstra_path_length(G, start_point, end_point, weight="weight")
    except nx.NetworkXNoPath:
        length = None

    if length is not None:
        results.append({
            "ActivityId": activity_id,
            "StartNode": start_point,
            "EndNode": end_point,
            "Time_s": real_time_s,
            "DijkstraTime_s": length
        })

    # removing the temporary nodes to avoid interference with next iteration
    G.remove_nodes_from([start_point, end_point])
    
    if i % 100 == 0:
        print(f">>> Processed {i} activities on {len(df['ActivityId'].unique())}")
        
    # if i == 100:
    #     start_time = time.time()
    # if i == 1100:
    #     elapsed = time.time() - start_time
    #     print(f">>> Estimated total time: {elapsed * len(df['ActivityId'].unique()) / 1000 / 60:.1f} minutes")

# === Save results ===


out_path = os.path.join(script_dir, "dijkstra_results_from_points.csv")
pd.DataFrame(results).to_csv(out_path, index=False)
print(f">>> Done. Saved {len(results)} results in {out_path}")
print(f">>> Total activities processed: {len(results)} on {len(df['ActivityId'].unique())}. Percentage: {len(results) / len(df['ActivityId'].unique()) * 100:.1f}%")




# Total activities in the file: 274047
# Number of activities with empty DijkstraTime_s: 11780
# Percentage of empty DijkstraTime_s: 4.30%