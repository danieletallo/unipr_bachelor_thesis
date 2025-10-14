# Read matched_coords.csv and read how many rows there are and how many have NEW_LATITUDE and NEW_LONGITUDE filled vs None
import pandas as pd
import os
from pathlib import Path

file_path = "matched_coords.csv"

if os.path.exists(file_path):
    df = pd.read_csv(file_path)
    total_rows = len(df)
    filled_rows = df[['NEW_Longitude', 'NEW_Latitude']].dropna().shape[0]
    empty_rows = df[['NEW_Longitude', 'NEW_Latitude']].isnull().all(axis=1).sum()

    print(f"Total rows in {file_path}: {total_rows}")
    print(f"Rows with NEW_Longitude and NEW_Latitude filled: {filled_rows}")
    print(f"Rows with NEW_Longitude and NEW_Latitude as None: {empty_rows}")
    
    # Find how many activities are there in total and how many distinct ActivityId have at least one row with NEW_Longitude and NEW_Latitude filled
    total_activities = df['ActivityId'].nunique()
    filled_activities = df[df[['NEW_Longitude', 'NEW_Latitude']].notnull().all(axis=1)]['ActivityId'].nunique()
    print(f"Total distinct ActivityId in {file_path}: {total_activities}")
    print(f"Distinct ActivityId with at least one row with NEW_Longitude and NEW_Latitude filled: {filled_activities}")
    
else:
    print(f"The file {file_path} does not exist.")