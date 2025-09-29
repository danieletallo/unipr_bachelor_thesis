# Leggi file segments_all_activities.csv 
# e conta quanti activityid ci sono

import pandas as pd
import os
from collections import Counter

# Carica il file CSV
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "segments_all_activities.csv")
df = pd.read_csv(csv_path)

# Conta quanti activityid ci sono
activity_counts = Counter(df['ActivityId'])
num_unique_activities = len(activity_counts)
print(f">>> Numero di activityid unici in segments_all_activities.csv: {num_unique_activities}")

# Conta quanti percorsi sono giusti, ovvero hanno:
# all'inizio un Nodo_Da o un Nodo_A che esiste anche nella seconda riga
# e alla fine un Nodo_Da o un Nodo_A che esiste anche nella penultima riga
# così da vedere qual è il nodo comune all'inizio e alla fine del percorso
# per poter applicare Dijkstra tra questi due nodi

valid_paths = 0
for activity_id, group in df.groupby('ActivityId'):
    if (len(group) < 4):
        continue  # Ignora i percorsi con meno di 4 segmenti
    
    start_nodes = {group.iloc[0]['Nodo_Da'], group.iloc[0]['Nodo_A']}
    end_nodes = {group.iloc[-1]['Nodo_Da'], group.iloc[-1]['Nodo_A']}
    second_row_nodes = {group.iloc[1]['Nodo_Da'], group.iloc[1]['Nodo_A']}
    penultimate_row_nodes = {group.iloc[-2]['Nodo_Da'], group.iloc[-2]['Nodo_A']}
    
    # Controllo se in start_nodes c'è un nodo che è anche in second_row_nodes
    # e se in end_nodes c'è un nodo che è anche in penultimate_row_nodes
    # controllo sia Nodo_Da che Nodo_A
    if (start_nodes & second_row_nodes) and (end_nodes & penultimate_row_nodes):
        valid_paths += 1
        
print(f">>> Numero di percorsi validi in segments_all_activities.csv: {valid_paths}")