import os
from osmnx import io as oxio
import pandas as pd

# Carica grafo
script_dir = os.path.dirname(os.path.abspath(__file__))
graphml_path = os.path.join(script_dir, "grafo.graphml")
graph = oxio.load_graphml(graphml_path, edge_dtypes={"weight": float, "oneway": str})

print(">>> Grafo caricato da grafo.graphml")

# Conta la frequenza di ogni key
keys = [key for (_, _, key) in graph.edges(keys=True)]
key_counts = pd.Series(keys).value_counts().sort_index()

# Stampa risultati
print("\n>>> Distribuzione delle chiavi (key):")
for k, cnt in key_counts.items():
    print(f"key={k} → {cnt} archi")

print(f"\nTotale archi: {len(keys)}")
