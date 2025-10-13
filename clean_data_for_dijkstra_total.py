import time
from typing import Counter
import pandas as pd
import osmnx as ox
from pyrosm import OSM
from shapely.geometry import LineString
import numpy as np
import os


# Processes a GPS segment associated with an edge and returns a dictionary with calculated data
def process_segment(G, activity_id, edge, gps_segment, time_segment):
    """
    Processes a GPS segment associated with an edge and returns a dictionary with calculated data.
    """
    ed = G.get_edge_data(*edge)

    # If geometry is missing, recreate a direct line between nodes u, v
    geom = ed.get("geometry")
    if geom is None:
        u, v = edge[0], edge[1]
        u_xy = (G.nodes[u]["x"], G.nodes[u]["y"])
        v_xy = (G.nodes[v]["x"], G.nodes[v]["y"])
        geom = LineString([u_xy, v_xy])
        ed["geometry"] = geom

    sl = segment_distance(gps_segment)
    el = ed.get('length', 0)
    nm = ed.get('name', 'Unknown')
    legal, cw = check_legality(ed, gps_segment, edge[0], edge[1], G)
    perc = min(sl / el, 1) * 100 if el else 0
    t0, t1 = time_segment[0], time_segment[-1]
    exp = ((t1 - t0).total_seconds() / sl * el) if sl > 0 and pd.notnull(t0) and pd.notnull(t1) else np.nan

    return {
        'ActivityId': activity_id, 'IsLegal': legal, 'HasCycleway': cw,
        'StreetName': nm, 'Node_From': edge[0], 'Node_To': edge[1], 'Key': edge[2],
        'PercentageTraveled': perc, 'DistanceTraveled_m': sl,
        'EdgeLength_m': el, 'ExpectedTime_s': exp,
        'TimeFrom': t0, 'TimeTo': t1
    }

# Calculates the total distance of a list of points (lat, lon)
def segment_distance(gps_segment):
    """Calculates the total distance (meters) of a list of points (lat, lon)"""
    if len(gps_segment) < 2:
        return 0
    d = 0
    for (lat1, lon1), (lat2, lon2) in zip(gps_segment[:-1], gps_segment[1:]):
        d += ox.distance.great_circle(lat1, lon1, lat2, lon2)
    return d

# Calculates the total distance of a point (lat, lon) from the nodes of an edge
def point_distance(point, edge):
    """Calculates the total distance (meters) of a point (lat, lon) from the nodes of an edge"""
    """It returns 'DistanceFrom_NodeFrom_m' and 'DistanceFrom_NodeTo_m'"""
    u, v = edge[0], edge[1]
    u_xy = (G.nodes[u]["y"], G.nodes[u]["x"])
    v_xy = (G.nodes[v]["y"], G.nodes[v]["x"])
    return {
        'DistanceFrom_NodeFrom_m': ox.distance.great_circle(point[0], point[1], *u_xy),
        'DistanceFrom_NodeTo_m': ox.distance.great_circle(point[0], point[1], *v_xy)
    }

# Returns the normalized vector
def get_direction(vec):
    norm = np.linalg.norm(vec)
    return np.array(vec) / norm if norm > 0 else np.array([0, 0])

# Checks if the GPS segment and the OSM edge have the same direction
# Useful for verifying the legality of the direction of travel
def is_same_direction(edge_geom, gps_segment, u, v, G):
    geom_start, geom_end = edge_geom.coords[0], edge_geom.coords[-1]
    u_latlon = (G.nodes[u]["y"], G.nodes[u]["x"])
    v_latlon = (G.nodes[v]["y"], G.nodes[v]["x"])
    start_latlon = (geom_start[1], geom_start[0])
    if ox.distance.great_circle(*v_latlon, *start_latlon) < ox.distance.great_circle(*u_latlon, *start_latlon):
        A, B = geom_end, geom_start
    else:
        A, B = geom_start, geom_end
    edge_vec = [B[0] - A[0], B[1] - A[1]]
    G0, G1 = gps_segment[0], gps_segment[-1]
    gps_vec = [G1[1] - G0[1], G1[0] - G0[0]]
    return np.dot(get_direction(edge_vec), get_direction(gps_vec)) > 0.5

def _val(ed, key):
    """Ritorna il valore normalizzato (stringa minuscola o '' se mancante)."""
    v = ed.get(key)
    if isinstance(v, list):  # dopo simplify può essere una lista di valori
        v = v[0] if v else None
    return str(v).lower() if v is not None else ""

def check_legality(edge_data, gps_segment, u, v, G):
    # --- Raccogli tutti i tag ciclabili ---
    cyc   = _val(edge_data, "cycleway")
    cyc_l = _val(edge_data, "cycleway:left")
    cyc_r = _val(edge_data, "cycleway:right")
    cyc_b = _val(edge_data, "cycleway:both")
    hw    = _val(edge_data, "highway")

    # --- Flag: esiste almeno una forma di infrastruttura ciclabile ---
    has_cycleway = any(v not in ("", "no", "none", "false") for v in (cyc, cyc_l, cyc_r, cyc_b)) or hw == "cycleway"

    # --- 1. Casi veramente bidirezionali ---
    # pista dedicata (non oneway)
    if hw == "cycleway" and _val(edge_data, "oneway") not in {"yes", "1", "true"}:
        return True, True

    # corsie opposte o bidirezionali (qualunque tag con "opposite" o cycleway:both valido)
    if any("opposite" in v for v in (cyc, cyc_l, cyc_r)) or cyc_b not in ("", "no", "none", "false"):
        return True, True

    # --- 2. Altri casi: controlla direzione ---
    geometry = edge_data.get("geometry")
    if geometry is None or len(gps_segment) < 2:
        return False, has_cycleway

    same = is_same_direction(geometry, gps_segment, u, v, G)
    ow_bike = _val(edge_data, "oneway:bicycle")
    ow = _val(edge_data, "oneway")

    if ow_bike in {"yes", "1", "true"}:
        legal = same
    elif ow_bike == "-1":
        legal = not same
    elif ow in {"yes", "1", "true"}:
        legal = same
    elif ow == "-1":
        legal = not same
    else:
        legal = True

    return legal, has_cycleway



###
###
### MAIN
if __name__ == '__main__':
    # -------- Load and filter GPS data --------
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'matched_coords.csv')
    print("Loading CSV file from:", csv_path)
    df_all = pd.read_csv(csv_path, usecols=["ActivityId","NEW_Latitude","NEW_Longitude","Time"]).dropna(subset=["NEW_Latitude","NEW_Longitude"])
    print(f"Total GPS points read: {len(df_all)}")
    df_all["ParsedTime"] = pd.to_datetime(
        df_all["Time"],
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce"
    )

    # -------- Load the OSM network from the historical PBF (Geofabrik Bologna 2018) -------- 
    print("Loading OSM graph from historical PBF (Bologna 2018)...")
    pbf_path = os.path.join(script_dir, "osrm", "bologna-2018.osm.pbf")  # place the file next to the script

    print("Loading OSM graph from historical PBF (Bologna 2018)... -- 2")
    if not os.path.exists(pbf_path):
        raise FileNotFoundError(f"PBF not found: {pbf_path}")

    print("Loading OSM graph from historical PBF (Bologna 2018)... -- 3")
    # Read 'cycling' network with Pyrosm
    osm = OSM(pbf_path)    

    # Essential tags for cycling: reduce attributes to save memory
    extra_attrs = [
        "oneway", "oneway:bicycle", "bicycle", "highway",
        "cycleway", "cycleway:left", "cycleway:right", "cycleway:both",
        "cycleway:left:oneway", "cycleway:right:oneway"
    ]


    print("Loading OSM graph from historical PBF (Bologna 2018)... -- 4")

    # ----------- LOAD NODES AND EDGES ----------
    nodes, edges = osm.get_network(
        network_type="cycling",
        extra_attributes=extra_attrs,
        nodes=True
    )

    print("Loading OSM graph from historical PBF (Bologna 2018)... -- 5")

    # ---------- NORMALIZE NODES ----------
    nodes = nodes.rename(columns={'id': 'osmid'})
    nodes = nodes.rename(columns={'lon': 'x', 'lat': 'y'})

    # Clean and ensure consistent index
    nodes = nodes.dropna(subset=['osmid']).copy()
    nodes['osmid'] = pd.to_numeric(nodes['osmid'], errors='coerce')
    nodes = nodes.dropna(subset=['osmid']).copy()
    nodes['osmid'] = nodes['osmid'].astype('int64')
    nodes = nodes.set_index('osmid')

    # ---------- NORMALIZE EDGES ----------
    # u/v must exist and have the same dtype as nodes.index
    for col in ('u', 'v'):
        if col not in edges.columns:
            raise ValueError(f"Column '{col}' is missing in edges.")
    edges = edges.dropna(subset=['u','v']).copy()
    edges['u'] = pd.to_numeric(edges['u'], errors='coerce')
    edges['v'] = pd.to_numeric(edges['v'], errors='coerce')
    edges = edges.dropna(subset=['u','v']).copy()
    edges['u'] = edges['u'].astype('int64')
    edges['v'] = edges['v'].astype('int64')

    # FILTER edges pointing to NON-existing nodes (typical after bbox)
    mask_uv_ok = edges['u'].isin(nodes.index) & edges['v'].isin(nodes.index)
    edges = edges.loc[mask_uv_ok].copy()

    # Create 'key' if missing or if it does not guarantee uniqueness
    if 'key' not in edges.columns or edges.duplicated(['u','v','key']).any():
        edges['key'] = edges.groupby(['u','v']).cumcount()

    # Set MultiIndex required (u, v, key)
    edges = edges.set_index(['u','v','key']).sort_index()

    print("Loading OSM graph from historical PBF (Bologna 2018)... -- 5.1")

    # Create MultiDiGraph compatible with OSMnx and simplify
    G = ox.graph_from_gdfs(nodes, edges)
    print("Loading OSM graph from historical PBF (Bologna 2018)... -- 6")
    G = ox.simplify_graph(G)

    # Ensure edge lengths are in meters
    print("Loading OSM graph from historical PBF (Bologna 2018)... -- 7")
    ox.distance.add_edge_lengths(G)

    print(f"Graph loaded from PBF: {len(G.nodes)} nodes, {len(G.edges)} edges")


    # -------- VECTORIAL CALCULATION nearest_edges ONLY ONCE --------
    print("Starting nearest_edges calculation for all points...")
    xs = df_all['NEW_Longitude'].values
    ys = df_all['NEW_Latitude'].values
    print(f"Calculating nearest_edges for {len(xs)} points...")
    # Split xs and ys to avoid memory issues with large datasets
    if len(xs) > 1000000:
        chunk_size = 1000000
        edges, dists = [], []
        for i in range(0, len(xs), chunk_size):
            chunk_edges, chunk_dists = ox.distance.nearest_edges(G, X=xs[i:i+chunk_size], Y=ys[i:i+chunk_size], return_dist=True)
            print(f"Calculated {len(chunk_edges)} nearest_edges for chunk {i//chunk_size + 1}")
            edges.extend(chunk_edges)
            dists.extend(chunk_dists)
    else:
        edges, dists = ox.distance.nearest_edges(G, X=xs, Y=ys, return_dist=True)
    print("nearest_edges calculated.")
    df_all['NearestEdge'] = list(edges)
    df_all['EdgeDist_m']   = dists
    print("Columns NearestEdge and EdgeDist_m added to DataFrame.")

    # -------- Analyze each ActivityId --------
    all_segments = []
    segment_count = 0
    num_activities = df_all['ActivityId'].nunique()
    print(f"Number of ActivityId to process: {num_activities}")

    num_activity_counter = 0

    for idx, (activity_id, df) in enumerate(df_all.groupby('ActivityId'), start=1):
        num_activity_counter += 1
        if num_activity_counter == 1000:
            time_start = time.time()    
        if num_activity_counter == 2000:
            time_end = time.time()
            time_per_1000 = time_end - time_start
            estimated_total_time = (time_per_1000 * (num_activities / 1000)) / 60  # in minutes
            print(f"Estimated total processing time for all activities: {estimated_total_time:.2f} minutes")    
        
        if num_activity_counter % 10000 == 0:    
            print(f"\nProcessing ActivityId {activity_id} ({num_activity_counter}/{num_activities}) with {len(df)} GPS points...")

        gps = list(zip(df['NEW_Latitude'], df['NEW_Longitude']))
        times = list(df['ParsedTime'])
        nes   = df['NearestEdge'].tolist()
        last = None
        seg, seg_t = [], []

        # Process segments
        first_segment_to_check = True
        for i, (pt, t, e) in enumerate(zip(gps, times, nes), start=1):
            if e is None:
                print(f"  Point {i}: no edge found, skipping")
                continue
            if e != last and seg:
                result = process_segment(G, activity_id, last, seg, seg_t)
                if result:
                    # If this is the first point of the activity, add it as:
                    # StartingLatitude, StartingLongitude
                    if first_segment_to_check:
                        result['StartingLatitude'] = gps[0][0]
                        result['StartingLongitude'] = gps[0][1]
                        result['EndingLatitude'] = None
                        result['EndingLongitude'] = None
                        result['DistanceFrom_NodeFrom_m'] = point_distance(gps[0], last)['DistanceFrom_NodeFrom_m']
                        result['DistanceFrom_NodeTo_m'] = point_distance(gps[0], last)['DistanceFrom_NodeTo_m']
                        first_segment_to_check = False
                    all_segments.append(result)
                    segment_count += 1
                seg, seg_t = [], []
            seg.append(pt)
            seg_t.append(t)
            last = e

        # Last segment
        if seg and last:
            result = process_segment(G, activity_id, last, seg, seg_t)
            if result:
                # This has to be the last point of the activity, add it as:
                # EndingLatitude, EndingLongitude
                result['StartingLatitude'] = None
                result['StartingLongitude'] = None
                result['EndingLatitude'] = gps[-1][0]
                result['EndingLongitude'] = gps[-1][1]
                result['DistanceFrom_NodeFrom_m'] = point_distance(gps[-1], last)['DistanceFrom_NodeFrom_m']
                result['DistanceFrom_NodeTo_m'] = point_distance(gps[-1], last)['DistanceFrom_NodeTo_m']
                all_segments.append(result)
                segment_count += 1



    # Now, we want 2 rows for each activity:
    # - the first with ActivityId, NodeFrom, NodeTo, Key, Time_s, Point_Latitude, Point_Longitude, Point_DistanceFrom_NodeFrom_m, Point_DistanceFrom_NodeTo_m
    # - the second equal but with the last point of the activity
    # This is needed to apply Dijkstra between the start and end nodes of the activity
    print(f"++++++++++++ CREATING THE FINAL DATAFRAME WITH {segment_count} SEGMENTS... ++++++++++++")
    print(f"++++++++++++ CREATING THE FINAL DATAFRAME WITH {segment_count} SEGMENTS... ++++++++++++")
    print(f"++++++++++++ CREATING THE FINAL DATAFRAME WITH {segment_count} SEGMENTS... ++++++++++++")
    all_segments = pd.DataFrame(all_segments)
    activity_counts = Counter(all_segments['ActivityId'])
    num_unique_activities = len(activity_counts)
    print(f">>> Number of unique ActivityIds: {num_unique_activities}")
    
    valid_paths_counter = 0
    valid_paths = []

    for activity_id, group in all_segments.groupby('ActivityId'):
        if (len(group) < 2):
            continue  # Ignore paths with fewer than 2 segments
        
        if valid_paths_counter % 10000 == 0:
            print(f"Processed {valid_paths_counter}/{len(all_segments)} valid paths...")
        
        valid_paths_counter += 1
        first_activity_row = group.iloc[0]
        last_activity_row = group.iloc[-1]
        time_from = first_activity_row['TimeFrom']
        time_to = last_activity_row['TimeTo']
        time_s = (pd.to_datetime(time_to) - pd.to_datetime(time_from)).total_seconds()

        valid_paths.append([activity_id, first_activity_row['Node_From'], first_activity_row['Node_To'], first_activity_row['Key'], time_s, first_activity_row['StartingLatitude'], first_activity_row['StartingLongitude'], first_activity_row['DistanceFrom_NodeFrom_m'], first_activity_row['DistanceFrom_NodeTo_m']]) # starting point
        valid_paths.append([activity_id, last_activity_row['Node_From'], last_activity_row['Node_To'], last_activity_row['Key'], time_s, last_activity_row['EndingLatitude'], last_activity_row['EndingLongitude'], last_activity_row['DistanceFrom_NodeFrom_m'], last_activity_row['DistanceFrom_NodeTo_m']]) # ending point

    # ActivityId, Node_From, Node_To, Key, Time_s, Point_Latitude, Point_Longitude, Point_DistanceFrom_NodeFrom_m, Point_DistanceFrom_NodeTo_m
    valid_paths = pd.DataFrame(valid_paths, columns=["ActivityId", "Node_From", "Node_To", "Key", "Time_s", "Point_Latitude", "Point_Longitude", "Point_DistanceFrom_NodeFrom_m", "Point_DistanceFrom_NodeTo_m"])
    valid_paths.to_csv(os.path.join(script_dir, "cleaned_paths_for_dijkstra_TOTAL.csv"), index=False, header=True)

    print(f">>> Number of valid paths in cleaned_paths_for_dijkstra_TOTAL.csv: {valid_paths_counter}")
    
    
    # # -------- Export --------
    # out = pd.DataFrame(all_segments)
    # out.to_csv(os.path.join(script_dir,'segments_for_dijkstra.csv'),index=False)
    # print(f"Exported 'segments_for_dijkstra.csv' with {len(all_segments)} segments.")
