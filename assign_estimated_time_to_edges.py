import pandas as pd

# Leggo il csv "segments_all_activities.csv"
# -> se Legal = False ----> skippo
# -> se Legal = True -----> prendo TempoAtteso_s e faccio media ponderata a seconda della PercentualePercorsa

output_file = "edges_with_estimated_times.csv"
segments = pd.read_csv(
    "segments_all_activities.csv",
    usecols=["ActivityId","IsLegal","Nodo_Da","Nodo_A","TempoAtteso_s","PercentualePercorsa", "LunghezzaEdge_m"]
)

print(f"Numero segmenti totali: {len(segments)}")

# Per stima tempi tolgo primo e ultimo arco di ogni attività causa ipotetica "nuvola di punti"
cleaned = []
for activity_id, group in segments.groupby("ActivityId"):
    if len(group) > 2:
        group = group.iloc[1:-1]
    cleaned.append(group)

segments_cleaned = pd.concat(cleaned)

segments_cleaned = segments_cleaned[(segments_cleaned["IsLegal"]) 
                                    & (segments_cleaned["TempoAtteso_s"].notna()) 
                                    & (segments_cleaned["PercentualePercorsa"] > 0)]

print(f"Numero segmenti legali: {len(segments_cleaned)}")

# Faccio media ponderata per ogni arco (Nodo_Da, Nodo_A) unendo anche i pochi versi opposti
# Facendo nearest edge con osmnx e segmentando, mi sono ritrovato che alcuni archi sono stati considerati in entrambi i versi
results = []
for (u, v), segment in segments_cleaned.groupby([
    segments_cleaned[["Nodo_Da", "Nodo_A"]].min(axis=1),
    segments_cleaned[["Nodo_Da", "Nodo_A"]].max(axis=1)
]):
    weighted_avg = (segment["TempoAtteso_s"] * segment["PercentualePercorsa"]).sum() / segment["PercentualePercorsa"].sum()
    results.append({
        "Nodo_Da": u,
        "Nodo_A": v,
        "TempoStimato_s": weighted_avg,
        "LunghezzaArco_m": segment["LunghezzaEdge_m"].iloc[0],
        "NumOsservazioni": len(segment),
        "Velocita_km_h": segment["LunghezzaEdge_m"].iloc[0] / weighted_avg * 3.6
    })

print(f"Numero archi unici: {len(results)}")

# Salvo i risultati in un csv, mi servirà per Dijkstra
df_results = pd.DataFrame(results)
df_results.to_csv(output_file, index=False)

print(f">>> Salvato: {output_file}")