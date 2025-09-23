import pandas as pd

# Node_SRC_From, Node_SRC_To, Node_DST_From, Node_DST_To
TOP3 = [
    (1, 250734660, 250734679, 280145073, 4496799435),
    (2, 655135679, 3325048776, 3254498353, 346089939),
    (3, 250713168, 245980471, 4449687200, 1617612971),
]

activities = pd.read_csv(
    "segments_all_activities.csv",
    usecols=["ActivityId", "Nodo_Da", "Nodo_A", 
             "PercentualePercorsa", "DistanzaPercorsa_m", "LunghezzaEdge_m", 
             "TempoAtteso_s", "TimeFrom", "TimeTo"]
)

output_rows = []

# Filtro le attività che:
# --> partono da Node_SRC_From -> Node_SRC_To
# --> arrivano a Node_DST_From -> Node_DST_To

counter = 0

print("Filtering activities for TOP3 paths...")
for activity_id, rows_by_activity_id in activities.groupby("ActivityId", sort=False):
    counter += 1
    if counter % 10000 == 0:
        print(f"Processed {counter} activities...", end="\r")

    first_row = rows_by_activity_id.iloc[0]
    last_row = rows_by_activity_id.iloc[-1]

    # Controllo se la coppia (first_row, last_row) è in TOP3
    for path_index, src_from, src_to, dst_from, dst_to in TOP3:
        if (first_row.Nodo_Da == src_from and first_row.Nodo_A == src_to and
                last_row.Nodo_Da == dst_from and last_row.Nodo_A == dst_to):
            df = rows_by_activity_id.copy()
            df["PathIndex"] = path_index
            output_rows.append(df)

output_filename = "filtered_activities_top3_paths.csv"
pd.concat(output_rows).to_csv(output_filename, index=False)
print(f"\nFiltered activities saved to {output_filename}")
print(f"\nFound {len(pd.concat(output_rows).groupby('ActivityId', sort=False))} activities for TOP3 paths:")