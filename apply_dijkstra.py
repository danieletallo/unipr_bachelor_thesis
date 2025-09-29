# Leggi il grafo dal file grafo.graphml e applica Dijkstra tra due nodi di esempio
import os
from osmnx import io as oxio

import networkx as nx

# Carica il grafo da file
script_dir = os.path.dirname(os.path.abspath(__file__))
graphml_path = os.path.join(script_dir, "grafo.graphml")

graph = oxio.load_graphml(graphml_path, edge_dtypes={"weight": float, "oneway": str})

print(">>> Grafo caricato da grafo.graphml")


# Applico Dijkstra tra due nodi di esempio
# Da 250735019,390032680 a 251897634,341927978
start_node = 390032680
end_node = 251897634
print(f">>> Calcolo percorso Dijkstra da {start_node} a {end_node}...")
try:
    path = nx.dijkstra_path(graph, start_node, end_node, weight='weight')
    path_length = nx.dijkstra_path_length(graph, start_node, end_node, weight='weight')
    print(f"Percorso trovato con lunghezza totale stimata: {path_length:.2f} secondi")
    print(f"Percorso (nodi): {path}")
except nx.NetworkXNoPath:
    print("Nessun percorso trovato tra i nodi specificati.")
    
    
    
# Nodo da controllare
u, v = 3942996530, 251845761
attrs_to_check = ["oneway", "highway", "cycleway", "bicycle"]

if graph.has_edge(u, v):
    for k, data in graph[u][v].items():
        print(f"\nArco {u} -> {v}, key={k}")
        for attr in attrs_to_check:
            print(f"  {attr} = {data.get(attr)}")
else:
    print(f"Nessun arco {u} -> {v} trovato")

# Verifico anche se esiste l'arco nell'altra direzione
if graph.has_edge(v, u):
    for k, data in graph[v][u].items():
        print(f"\nArco {v} -> {u}, key={k}")
        for attr in attrs_to_check:
            print(f"  {attr} = {data.get(attr)}")
else:
    print(f"Nessun arco {v} -> {u} trovato")
