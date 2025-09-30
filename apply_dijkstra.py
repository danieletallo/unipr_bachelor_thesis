# Leggi il grafo dal file grafo.graphml e applica Dijkstra tra due nodi di esempio
import os
from time import time
from osmnx import io as oxio
import pandas as pd
import networkx as nx

# Carica il grafo da file
script_dir = os.path.dirname(os.path.abspath(__file__))
graphml_path = os.path.join(script_dir, "grafo.graphml")

graph = oxio.load_graphml(graphml_path, edge_dtypes={"weight": float, "oneway": str})

print(">>> Grafo caricato da grafo.graphml")


# # # # # # Applico Dijkstra tra due nodi di esempio
# # # # # # Da 250735019,390032680 a 251897634,341927978
# # # # # # Applicando i 4 percorsi possibili, ovvero da u_orig a u_dest, da u_orig a v_dest, da v_orig a u_dest, da v_orig a v_dest

# # # # # # start_node = 567074443   # 250735019,390032680
# # # # # # end_node = 297798839     #251897634,341927978


# Leggo i percorsi puliti da cleaned_paths_for_dijkstra.csv

cleaned_paths_path = os.path.join(script_dir, "cleaned_paths_for_dijkstra.csv")
df_paths = pd.read_csv(cleaned_paths_path)

dijkstra_results = []

print(f">>> Inizio calcolo percorsi Dijkstra per {len(df_paths)} percorsi...")
paths_not_found = 0

for index, row in df_paths.iterrows():
    activity_id = row['ActivityId']
    start_node = row['StartNode']
    end_node = row['EndNode']

    if (index % 1000 == 0) and index > 0:
        print(f">>> Elaborati {index} percorsi Dijkstra...")

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

# Salvo i risultati in un file CSV
df_dijkstra = pd.DataFrame(dijkstra_results)
dijkstra_csv_path = os.path.join(script_dir, "dijkstra_results.csv")
df_dijkstra.to_csv(dijkstra_csv_path, index=False, header=True)

print(f">>> Percorsi non trovati: {paths_not_found}")
print(f">>> Risultati Dijkstra salvati in {dijkstra_csv_path}")
