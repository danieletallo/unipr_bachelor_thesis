# Read the graph from the file .graphml and apply Dijkstra between two example nodes
import os
from time import time
from osmnx import io as oxio
import pandas as pd
import networkx as nx

# Load the graph from the file
script_dir = os.path.dirname(os.path.abspath(__file__))
graphml_path = os.path.join(script_dir, "bologna_graph.graphml")

graph = oxio.load_graphml(graphml_path, edge_dtypes={"weight": float, "oneway": str})

print(">>> Graph loaded from bologna_graph.graphml")



# Read the cleaned paths from cleaned_paths_for_dijkstra.csv

cleaned_paths_path = os.path.join(script_dir, "cleaned_paths_for_dijkstra.csv")
df_paths = pd.read_csv(cleaned_paths_path)

dijkstra_results = []

print(f">>> Starting Dijkstra path calculations for {len(df_paths)} paths...")
paths_not_found = 0

for index, row in df_paths.iterrows():
    activity_id = row['ActivityId']
    start_node = row['StartNode']
    end_node = row['EndNode']

    if (index % 1000 == 0) and index > 0:
        print(f">>> Processed {index} Dijkstra paths...")

    try:
        path_length = None
        path = None
        
        
        path = nx.dijkstra_path(graph, start_node, end_node, weight='weight')
        path_length = nx.dijkstra_path_length(graph, start_node, end_node, weight='weight')
        
        dijkstra_results.append({
            "ActivityId": activity_id,
            "StartNode": start_node,
            "EndNode": end_node,
            "TimeFrom": row['TimeFrom'],
            "TimeTo": row['TimeTo'],
            "Time_s": row['Time_s'],
            "DijkstraTime_s": path_length,
            "DijkstraPath": path
        })

    except nx.NetworkXNoPath:
        dijkstra_results.append({
            "ActivityId": activity_id,
            "StartNode": start_node,
            "EndNode": end_node,
            "TimeFrom": row['TimeFrom'],
            "TimeTo": row['TimeTo'],
            "Time_s": row['Time_s'],
            "DijkstraTime_s": None,
            "DijkstraPath": None
        })
        paths_not_found += 1

# Save the results to a CSV file
df_dijkstra = pd.DataFrame(dijkstra_results)
dijkstra_csv_path = os.path.join(script_dir, "dijkstra_results.csv")
df_dijkstra.to_csv(dijkstra_csv_path, index=False, header=True)

print(f">>> Paths not found: {paths_not_found}")
print(f">>> Dijkstra results saved in {dijkstra_csv_path}")
