## Leggi Nodo_Da e Nodo_A da "segments_all_activities.csv" e vedi quanti sono con la distinct le coppie uniche (considerando anche il verso opposto)
# e guarda quante sono e quante non sono nel grafo (nodi_grafo.csv) considerando u, v e v, u
import os
import pandas as pd

df = pd.read_csv("segments_all_activities.csv", usecols=["Nodo_Da","Nodo_A"])
print(f"Coppie uniche (u,v): {len(df.drop_duplicates())}")
df_set = set(zip(df["Nodo_Da"], df["Nodo_A"]))
print(f"Coppie uniche (u,v) con set: {len(df_set)}")

# Leggo il csv dei nodi del grafo
graph_df = pd.read_csv("nodi_grafo.csv")
graph_set = set(zip(graph_df["u"], graph_df["v"]))
print(f"Coppie uniche nel grafo (u,v): {len(graph_set)}")

# Conta quante coppie (u,v) in df_set non sono in graph_set
missing_count = 0
coppie_mancanti = []
for (u, v) in df_set:
    if (u, v) not in graph_set and (v, u) not in graph_set:
        missing_count += 1
        coppie_mancanti.append((u, v))



print(f"Numero coppie (u,v) in segments_all_activities.csv: {len(df_set)}")
print(f"Coppie (u,v) mancanti nel grafo (considerando anche il verso opposto): {missing_count}")


## Senza semplificazione mi trovava 25k archi nel segments.csv e 200k+ nel grafo creato.. di questi 25k -> 15k non li trovava
## Con semplificazione -> 25k archi e 50k+ nel grafo creato.. di questi 25k -> 13 non li trova! Ottimo :-D