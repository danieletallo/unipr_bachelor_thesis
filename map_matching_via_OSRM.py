import pandas as pd
import osmnx as ox
from pyrosm import OSM
from shapely.geometry import LineString
import numpy as np
import os
import requests
import time

BASE_URL = "http://localhost:5000"
CHUNK_SIZE = 100  # number of GPS points per OSRM query
MAXIMUM_RADIUS = 15

### MAIN
if __name__ == '__main__':
    
    # -------- Load and filter GPS data --------
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'cycle.csv')
    pkl_path = os.path.join(script_dir, 'cycle.pkl')

    if os.path.exists(pkl_path):
        print("Loading dataframe from pickle...")
        df_all = pd.read_pickle(pkl_path)
    else:
        print("Loading dataframe from CSV...")

        df_all = (
            pd.read_csv(csv_path, usecols=["ActivityId","Latitude","Longitude","Time"])
            .dropna(subset=["Latitude","Longitude"])
        )

        df_all["UnixSec"] = pd.to_datetime(df_all["Time"], errors="coerce")
        df_all = df_all.dropna(subset=["UnixSec"])
        df_all["UnixSec"] = df_all["UnixSec"].astype("int64") // 10**9  # ns → s

        df_all.to_pickle(pkl_path)   # save ready-to-use dataframe

    activity_ids = df_all['ActivityId'].unique()
    print(f"Total unique ActivityIds: {len(activity_ids)}")

    # Check if matched_coords.csv already exists to resume from the last processed ActivityId
    matched_coords_file = os.path.join(script_dir, 'matched_coords.csv')
    last_processed_activity_id = None
    
    if os.path.exists(matched_coords_file):
        print("matched_coords.csv file found. Searching for the last processed ActivityId...")
        try:
            existing_df = pd.read_csv(matched_coords_file)
            if not existing_df.empty:
                last_processed_activity_id = existing_df['ActivityId'].max()
                print(f"Last processed ActivityId: {last_processed_activity_id}")
        except Exception as e:
            print(f"Error reading the existing file: {e}")
            print("Will start from the beginning...")
    
    # Filter ActivityIds to process only those after the last processed one
    if last_processed_activity_id is not None:
        activity_ids = activity_ids[activity_ids > last_processed_activity_id]
        print(f"Remaining ActivityIds to process: {len(activity_ids)}")
    
    counter = 0
    gps_counter = 0
    gps_error_counter = 0
    iteration_counter = 0

    # Create a list with Longitude, Latitude, NewLongitude, NewLatitude
    matched_coords = []
    
    # Counter for saving in append mode every 10000 ActivityIds
    save_interval = 10000
    last_save_count = 0

    timewatch = time.time()
    with requests.Session() as sess:
        # Filter the dataframe to process only the remaining ActivityIds
        if last_processed_activity_id is not None:
            df_filtered = df_all[df_all['ActivityId'] > last_processed_activity_id]
        else:
            df_filtered = df_all
            
        for activity_id, rows_by_activity_id in df_filtered.groupby("ActivityId", sort=False):
            xy = rows_by_activity_id[["Longitude", "Latitude"]].to_numpy()

            counter += 1
            print("Processing activity no.", counter)
            print(f"ActivityId {activity_id}: {len(xy)} GPS points")

            # xy count > 100 -> split into multiple queries
            for i in range(0, len(xy), CHUNK_SIZE):
                chunk = xy[i:i+CHUNK_SIZE]
                coords = ";".join([f"{lon},{lat}" for lon, lat in chunk])
                chunk_times = rows_by_activity_id["UnixSec"].iloc[i:i+CHUNK_SIZE]
                chunk_times_raw = rows_by_activity_id["Time"].iloc[i:i+CHUNK_SIZE]  # <- NEW

                data = {"tracepoints": []} 
                try:
                    iteration_counter += 1

                    # Attempts with increasing radius ONLY if it fails
                    for radius in [None] + list(range(10, MAXIMUM_RADIUS + 1, 5)):
                        params = {
                            "steps": "false",
                            "geometries": "geojson",
                            "overview": "full",
                            "annotations": "true",
                            "timestamps": ";".join(chunk_times.astype(str).tolist())
                        }
                        if radius is not None:
                            params["radiuses"] = ";".join([str(radius)] * len(chunk))

                        r = sess.get(f"{BASE_URL}/match/v1/bicycle/{coords}", params=params)

                        if r.ok:
                            data = r.json()
                            
                            # If there are matching errors or tracepoints are None, retry with a larger radius
                            if (
                                data.get("code") == "NoSegment" or data.get("code") == "NoMatch" 
                                or (data.get("code") == "Ok" and any(tp is None for tp in data.get("tracepoints", [])))
                            ):
                                if radius != MAXIMUM_RADIUS:
                                    continue  # try with a larger radius

                            if data.get("code") == "Ok":
                                break  # success: exit the loop

                            # Other codes -> do not insist with radius
                            break
                        else:
                            # HTTP error: if 400 NoSegment or NoMatch, retry; otherwise exit
                            try:
                                j = r.json()
                                if j.get("code") == "NoSegment" or j.get("code") == "NoMatch":
                                    continue
                            except Exception:
                                pass
                            break
                    else:
                        # If exiting the for loop without a break: all attempts failed
                        if (data.get("code") == "Ok" and any(tp is None for tp in data.get("tracepoints", []))):
                            print("  -> Some tracepoints are None")
                        else:
                            print("\033[91m" + r.text + "\033[0m")

                except Exception:
                    print("EXCEPTION!")

                finally:
                    tps = data.get("tracepoints", [])

                    for idx, (old_lon, old_lat) in enumerate(chunk):
                        if idx >= len(tps) or tps[idx] is None:
                            gps_error_counter += 1
                            new_loc = None
                        else:
                            new_loc = tps[idx].get("location")

                        matched_coords.append({
                            "ActivityId": int(activity_id),
                            "Time": str(chunk_times_raw.iloc[idx]),
                            "OLD_Latitude": float(old_lat),
                            "OLD_Longitude": float(old_lon),
                            "NEW_Latitude": None if new_loc is None else float(new_loc[1]),
                            "NEW_Longitude": None if new_loc is None else float(new_loc[0])
                        })

            gps_counter += len(xy)
            
            # Periodic saving every 10000 ActivityIds
            if counter - last_save_count >= save_interval:
                print(f"\n--- Intermediate save after {counter} ActivityIds ---")
                if matched_coords:
                    df_temp = pd.DataFrame(matched_coords, columns=["ActivityId","Time","OLD_Latitude","OLD_Longitude","NEW_Latitude","NEW_Longitude"])
                    
                    # If the file exists, append; otherwise, create a new one
                    if os.path.exists(matched_coords_file):
                        df_temp.to_csv(matched_coords_file, mode='a', header=False, index=False)
                        print(f"Data appended to the existing file: {len(matched_coords)} rows")
                    else:
                        df_temp.to_csv(matched_coords_file, index=False)
                        print(f"File created with {len(matched_coords)} rows")
                    
                    # Clear the list to save memory
                    matched_coords = []
                    last_save_count = counter
                    print(f"Memory cleared. Next save in {save_interval} ActivityIds")
                print("--- End of intermediate save ---\n")

    print("Counter:", counter)
    print("GPS points error counter:", gps_error_counter, " / ", gps_counter)
    print("Elapsed time:", time.time() - timewatch)
    if counter > 0:
        print("Average time per ActivityId:", (time.time() - timewatch) / counter)
    if gps_counter > 0:
        print("Average time per GPS point:", (time.time() - timewatch) / gps_counter)
        print("Estimated time for 78 million GPS points:", (time.time() - timewatch) / gps_counter * 78000000 / 3600, "hours")

    # Final save of remaining data
    if matched_coords:
        print(f"\n--- Final save of {len(matched_coords)} remaining rows ---")
        df_final = pd.DataFrame(matched_coords, columns=["ActivityId","Time","OLD_Latitude","OLD_Longitude","NEW_Latitude","NEW_Longitude"])
        
        # If the file exists, append; otherwise, create a new one
        if os.path.exists(matched_coords_file):
            df_final.to_csv(matched_coords_file, mode='a', header=False, index=False)
            print("Final data appended to the existing file")
        else:
            df_final.to_csv(matched_coords_file, index=False)
            print("Final file created")
        print("--- Save completed ---")
    
    print(f"\nAll data saved in: {matched_coords_file}")