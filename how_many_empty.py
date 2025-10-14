# Read "dijkstra_results_from_points.csv" and check these columns:
        # "ActivityId": activity_id,
        # "StartNode": start_point,
        # "EndNode": end_point,
        # "Time_s": real_time_s,
        # "DijkstraTime_s": length
        
# counting how many have DijkstraTime_s as None

import pandas as pd
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
in_path = os.path.join(script_dir, "dijkstra_results_from_points.csv")
df = pd.read_csv(in_path)
print(f"Total activities in the file: {len(df)}")
num_empty = df['DijkstraTime_s'].isna().sum()
print(f"Number of activities with empty DijkstraTime_s: {num_empty}")
print(f"Percentage of empty DijkstraTime_s: {num_empty / len(df) * 100:.2f}%")

# Remove rows with empty DijkstraTime_s if needed
df_cleaned = df.dropna(subset=['DijkstraTime_s'])
cleaned_path = os.path.join(script_dir, "dijkstra_results_from_points_cleaned.csv")
df_cleaned.to_csv(cleaned_path, index=False)
print(f"Cleaned data saved to: {cleaned_path}")