import os
import glob
import pandas as pd

# Set the current folder
directory = os.getcwd()

# Find all CSV files in the folder
csv_files = glob.glob(os.path.join(directory, "*.csv"))

# List to save all cycle rows
cycle_data = []

# Counter for the total number of rows found
total_rows = 0

# Read and filter each CSV file
for file in csv_files:
    try:
        print(f"Processing file: {file}")
        df = pd.read_csv(file)

        if "ActivityType" in df.columns:
            df = df[df["ActivityType"] == "Cycle"]

            if not df.empty:
                df["source_file"] = os.path.basename(file)
                cycle_data.append(df)
                total_rows += len(df)
                print(f"Found {len(df)} 'Cycle' rows in this file")

    except Exception as e:
        print(f"Error in file {file}: {e}")

# Check if there are any cycle rows
if not cycle_data:
    print("No 'Cycle' activities found.")
    exit()

# Combine all filtered data into a single DataFrame
df_cycle = pd.concat(cycle_data, ignore_index=True)

# Remove rows without valid coordinates
df_cycle = df_cycle.dropna(subset=["Latitude", "Longitude"])

# Save to file
df_cycle.to_csv("cycle.csv", index=False)
print("Data saved to 'cycle.csv'.")

# Display final summary
print(f"Total cycle rows found: {len(df_cycle)}")
print(f"Total distinct activities found: {df_cycle['ActivityId'].nunique()}")
