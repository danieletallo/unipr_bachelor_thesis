import pandas as pd

# Read the CSV file "segments_all_activities.csv"
# -> if IsLegal = False ----> skip
# -> if IsLegal = True -----> take ExpectedTime_s and calculate weighted average based on PercentageTraveled

output_file = "edges_with_estimated_times.csv"
segments = pd.read_csv(
    "segments_all_activities_2.csv",
    usecols=["ActivityId", "IsLegal", "Node_From", "Node_To", "Key", "ExpectedTime_s", "PercentageTraveled", "EdgeLength_m"]
)

print(f"Total number of segments: {len(segments)}")

# For time estimation, remove the first and last edge of each activity due to potential "point cloud"
cleaned = []
for activity_id, group in segments.groupby("ActivityId"):
    if len(group) > 2:
        group = group.iloc[1:-1]
    cleaned.append(group)

segments_cleaned = pd.concat(cleaned)

segments_cleaned = segments_cleaned[(segments_cleaned["IsLegal"]) 
                                    & (segments_cleaned["ExpectedTime_s"].notna()) 
                                    & (segments_cleaned["PercentageTraveled"] > 0)]

print(f"Number of legal segments: {len(segments_cleaned)}")

# Calculate weighted average for each edge (Node_From, Node_To, Key), also combining opposite directions
# Due to nearest edge with osmnx and segmentation, some edges were considered in both directions
results = []
segments_cleaned = segments_cleaned.assign(
    u_min=segments_cleaned[["Node_From", "Node_To"]].min(axis=1),
    v_max=segments_cleaned[["Node_From", "Node_To"]].max(axis=1)
)

for (u, v, key), segment in segments_cleaned.groupby(["u_min", "v_max", "Key"]):
    weighted_avg = (segment["ExpectedTime_s"] * segment["PercentageTraveled"]).sum() / segment["PercentageTraveled"].sum()
    results.append({
        "Node_From": u,
        "Node_To": v,
        "Key": key,
        "EstimatedTime_s": weighted_avg,
        "EdgeLength_m": segment["EdgeLength_m"].iloc[0],
        "NumObservations": len(segment),
        "Speed_km_h": segment["EdgeLength_m"].iloc[0] / weighted_avg * 3.6
    })

print(f"Number of unique edges: {len(results)}")

# Save the results to a CSV file, which will be used for Dijkstra
df_results = pd.DataFrame(results)
df_results.to_csv(output_file, index=False)

print(f">>> Saved: {output_file}")