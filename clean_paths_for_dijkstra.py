# Read the file segments_all_activities.csv 
# and count how many unique ActivityIds there are

import pandas as pd
import os
from collections import Counter

# Load the CSV file
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, "segments_all_activities_2.csv")
df = pd.read_csv(csv_path)

# Count how many unique ActivityIds there are
activity_counts = Counter(df['ActivityId'])
num_unique_activities = len(activity_counts)
print(f">>> Number of unique ActivityIds in segments_all_activities.csv: {num_unique_activities}")

# Count how many valid paths exist, which have:
# at the start, a Node_From or Node_To that also exists in the second row
# and at the end, a Node_From or Node_To that also exists in the second-to-last row
# to determine the common node at the start and end of the path
# so Dijkstra can be applied between these two nodes

valid_paths_counter = 0
valid_paths = []

for activity_id, group in df.groupby('ActivityId'):
    if (len(group) < 4):
        continue  # Ignore paths with fewer than 4 segments
    
    start_nodes = {group.iloc[0]['Node_From'], group.iloc[0]['Node_To']}
    end_nodes = {group.iloc[-1]['Node_From'], group.iloc[-1]['Node_To']}
    second_row_nodes = {group.iloc[1]['Node_From'], group.iloc[1]['Node_To']}
    penultimate_row_nodes = {group.iloc[-2]['Node_From'], group.iloc[-2]['Node_To']}
    
    # Check if start_nodes has a node that is also in second_row_nodes
    # and if end_nodes has a node that is also in penultimate_row_nodes
    # ensure there is no overlap between start_nodes and end_nodes
    if len(start_nodes & second_row_nodes) == 1 and len(end_nodes & penultimate_row_nodes) == 1 and len(start_nodes & end_nodes) == 0:
        valid_paths_counter += 1
        ## Add to the dataframe the ActivityId, the common node at the start (start_node) and end (end_node), and TimeFrom of the second row and TimeTo of the second-to-last row
        start_node = (start_nodes & second_row_nodes).pop()
        end_node = (end_nodes & penultimate_row_nodes).pop()
        time_from = group.iloc[1]['TimeFrom']
        time_to = group.iloc[-2]['TimeTo']
        time_s = (pd.to_datetime(time_to) - pd.to_datetime(time_from)).total_seconds()
        valid_paths.append([activity_id, start_node, end_node, time_from, time_to, time_s])

valid_paths = pd.DataFrame(valid_paths, columns=["ActivityId", "StartNode", "EndNode", "TimeFrom", "TimeTo", "Time_s"])
valid_paths.to_csv(os.path.join(script_dir, "cleaned_paths_for_dijkstra.csv"), index=False, header=True)

print(f">>> Number of valid paths in segments_all_activities.csv: {valid_paths_counter}")