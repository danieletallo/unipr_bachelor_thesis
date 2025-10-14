# Given a path, search in all directories (and subdirectories) for CSV files and count the total of rows
# skipping the header rows.
# Finally read value of column value ActivityType and group by value, counting the number of occurrences for each value.
# e conta quanti distinct ActivityId ci sono in totale e quanti in Cycle
import argparse
from pathlib import Path
import pandas as pd



pathtoread = Path("C:/Users/39338/Desktop/Universita/3 ANNO/tirocinio_&_tesi/tesi/bella_mossa_dataset/zips")

def count_rows_in_csv(file_path: Path) -> int:
    try:
        with file_path.open('r', encoding='utf-8') as f:
            # Count lines, subtract 1 for header
            return sum(1 for line in f) - 1
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0
    
def main(directory: Path):
    total_rows = 0
    activity_type_counts = {}
    cycle_activity_id_count = 0
    total_activity_id_count = 0
    for csv_file in directory.rglob('*.csv'):
        #print(f"Processing file: {csv_file}")
        rows = count_rows_in_csv(csv_file)
        total_rows += rows
        
        try:
            df = pd.read_csv(csv_file, usecols=["ActivityType", "ActivityId"])
            activity_counts = df["ActivityType"].value_counts().to_dict()
            for activity_type, count in activity_counts.items():
                if activity_type in activity_type_counts:
                    activity_type_counts[activity_type] += count
                else:
                    activity_type_counts[activity_type] = count

            # Count distinct ActivityId values
            distinct_activity_ids = df["ActivityId"].nunique()
            print(f"Distinct ActivityId in {csv_file}: {distinct_activity_ids}")

            # Count distinct ActivityId values for "Cycle"
            cycle_activity_ids = df[df["ActivityType"] == "Cycle"]["ActivityId"].nunique()

            # Update total counts
            if "Cycle" in activity_type_counts:
                cycle_activity_id_count += cycle_activity_ids
            total_activity_id_count += distinct_activity_ids
        except Exception as e:
            print(f"Error processing {csv_file}: {e}")

    print(f"Total rows across all CSV files: {total_rows}")
    print("ActivityType counts:")
    for activity_type, count in activity_type_counts.items():
        print(f"  {activity_type}: {count}")
        
    print(f"Total distinct ActivityId count: {total_activity_id_count}")
    print(f"Total distinct ActivityId count for 'Cycle': {cycle_activity_id_count}")
        

if __name__ == "__main__":
    main(pathtoread)
    
    