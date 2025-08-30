import pandas as pd
import osmnx as ox
from shapely.geometry import LineString
import numpy as np
import os

def segment_distance(gps_segment):
    """Calcola la distanza totale (metri) di una lista di punti (lat, lon)"""
    if len(gps_segment) < 2:
        return 0
    d = 0
    for (lat1, lon1), (lat2, lon2) in zip(gps_segment[:-1], gps_segment[1:]):
        d += ox.distance.great_circle(lat1, lon1, lat2, lon2)
    return d

# NEW METHOD
def get_direction(vec):
    norm = np.linalg.norm(vec)
    return np.array(vec) / norm if norm > 0 else np.array([0, 0])

def is_same_direction(edge_geom, gps_segment, node_u, node_v, G):
    """
    Controlla se la direzione del segmento GPS coincide con il verso dell'arco (u→v)
    """
    # Coordinate dei nodi u e v
    u_coords = (G.nodes[node_u]["x"], G.nodes[node_u]["y"])
    v_coords = (G.nodes[node_v]["x"], G.nodes[node_v]["y"])

    # Coordinate inizio/fine della geometria
    geom_start = edge_geom.coords[0]
    geom_end = edge_geom.coords[-1]

    # Inverti (x, y) → (lat, lon) per great_circle
    u_latlon = (G.nodes[node_u]["y"], G.nodes[node_u]["x"])
    v_latlon = (G.nodes[node_v]["y"], G.nodes[node_v]["x"])
    start_latlon = (geom_start[1], geom_start[0])
    end_latlon = (geom_end[1], geom_end[0])

    # Distanze per capire se geom va da u→v o da v→u
    d_start_to_u = ox.distance.great_circle(*u_latlon, *start_latlon)
    d_start_to_v = ox.distance.great_circle(*v_latlon, *start_latlon)

    # Se geom parte da u → ok, altrimenti inverti verso
    if d_start_to_v < d_start_to_u:
        # La geometria va da v → u, quindi inverti
        A = geom_end
        B = geom_start
    else:
        A = geom_start
        B = geom_end

    edge_vec = [B[0] - A[0], B[1] - A[1]]

    # Direzione del segmento GPS (usiamo lat/lon, quindi [lon, lat])
    G0 = gps_segment[0]
    G1 = gps_segment[-1]
    gps_vec = [G1[1] - G0[1], G1[0] - G0[0]]  # [lon, lat]

    # Direzioni normalizzate
    edge_dir = get_direction(edge_vec)
    gps_dir = get_direction(gps_vec)

    # Confronta con coseno
    cos_sim = np.dot(edge_dir, gps_dir)

    return cos_sim > 0.5  # soglia tollerante (> 0 = stesso verso, > 0.5 = abbastanza simile)


def check_legality(edge_data, gps_segment, node_u, node_v, G):
    oneway = edge_data.get("oneway", False)
    has_cycleway = any(
        k in edge_data
        for k in ["cycleway", "cycleway:right", "cycleway:left", "cycleway:both"]
    )
    geometry = edge_data.get("geometry", None)
    if not geometry or len(gps_segment) < 2:
        # Not enough info
        return False, has_cycleway

    same_dir = is_same_direction(geometry, gps_segment, node_u, node_v, G)

    # Legalità in base alla direzione e ai tag
    if oneway in ["yes", True, "True", 1, "1"]:
        is_legal = same_dir
    elif oneway == "-1":
        is_legal = not same_dir
    else:
        is_legal = True  # No vincoli di direzione

    return is_legal, has_cycleway


def edge_n_nodes(edge_data):
    # Conta i punti della geometria (esclusi start/end se non c'è geometry)
    geometry = edge_data.get("geometry", None)
    if geometry and isinstance(geometry, LineString):
        return len(geometry.coords)
    else:
        return 2  # Se non c'è geometry, è un segmento diritto tra 2 nodi

def parse_time(t):
    # Parser orario: gestisce formati tipo 01/04/2017 00:19:42
    try:
        return pd.to_datetime(t, format="%d/%m/%Y %H:%M:%S")
    except Exception:
        return pd.to_datetime(t, errors='coerce')

# -------- Parametri principali --------
# activity_id = 1145787

# -------- Carica e filtra dati GPS --------
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, 'cycle.csv')
df_all = pd.read_csv(
    csv_path,
    usecols=["ActivityId", "Latitude", "Longitude", "Time"]
)

print("Qui...")

df_all = df_all.dropna(subset=["Latitude", "Longitude"])

print("Qui 2 ...")

# df_all["ParsedTime"] = df_all["Time"].apply(parse_time)
df_all["ParsedTime"] = pd.to_datetime(df_all["Time"], errors='coerce', dayfirst=True)

# -------- Scarica la rete OSM --------
print("Scarico grafo OSM...")
ox.settings.use_cache = True
G = ox.graph_from_place("Bologna, Italy", network_type="bike", simplify=True)

# -------- Analizza ogni ActivityId --------
all_segments = []

segment_count = 0

for activity_id, df in df_all.groupby("ActivityId"):
    print(f"\n>>> Inizio analisi ActivityId: {activity_id} ({len(df)} punti GPS)")

    df = df.sort_values("ParsedTime")
    gps_points = list(zip(df["Latitude"], df["Longitude"]))
    gps_times = list(df["ParsedTime"])
    
    nearest_edges = []
    for point in gps_points:
        try:
            u, v, key = ox.nearest_edges(G, X=point[1], Y=point[0])
            nearest_edges.append((u, v, key))
        except:
            nearest_edges.append(None)

    last_edge = None
    segment = []
    segment_times = []

    for (latlon, t, edge) in zip(gps_points, gps_times, nearest_edges):
        if edge is None:
            continue

        if edge != last_edge and segment:
            edge_data = G.get_edge_data(*last_edge)
            n_nodi = edge_n_nodes(edge_data)
            if n_nodi < 3:
                segment = []
                segment_times = []
                last_edge = edge
                continue

            seg_len = segment_distance(segment)
            edge_len = edge_data.get("length", 0)
            nome_via = edge_data.get("name", "Sconosciuto")
            is_legal, has_cycleway = check_legality(edge_data, segment, last_edge[0], last_edge[1], G)
            perc = min(seg_len / edge_len, 1.0) * 100 if edge_len else 0
            t0, t1 = segment_times[0], segment_times[-1]
            if pd.isnull(t0) or pd.isnull(t1):
                expected_time = np.nan
            else:
                duration = (t1 - t0).total_seconds()
                expected_time = duration / seg_len * edge_len if seg_len > 0 else np.nan

            all_segments.append({
                "ActivityId": activity_id,
                "IsLegal": is_legal,
                "HasCycleway": has_cycleway,
                "NomeVia": nome_via,
                "Nodo_Da": last_edge[0],
                "Nodo_A": last_edge[1],
                "PercentualePercorsa": perc,
                "DistanzaPercorsa_m": seg_len,
                "LunghezzaEdge_m": edge_len,
                "TempoAtteso_s": expected_time
            })
            segment_count += 1
            print("Segmenti completati:", segment_count)
            segment = []
            segment_times = []

        segment.append(latlon)
        segment_times.append(t)
        last_edge = edge

    # Ultimo segmento
    if segment and last_edge:
        edge_data = G.get_edge_data(*last_edge)
        n_nodi = edge_n_nodes(edge_data)
        if n_nodi >= 3:
            seg_len = segment_distance(segment)
            edge_len = edge_data.get("length", 0)
            nome_via = edge_data.get("name", "Sconosciuto")
            is_legal, has_cycleway = check_legality(edge_data, segment, last_edge[0], last_edge[1], G)
            perc = min(seg_len / edge_len, 1.0) * 100 if edge_len else 0
            t0, t1 = segment_times[0], segment_times[-1]
            if pd.isnull(t0) or pd.isnull(t1):
                expected_time = np.nan
            else:
                duration = (t1 - t0).total_seconds()
                expected_time = duration / seg_len * edge_len if seg_len > 0 else np.nan

            all_segments.append({
                "ActivityId": activity_id,
                "IsLegal": is_legal,
                "HasCycleway": has_cycleway,
                "NomeVia": nome_via,
                "Nodo_Da": last_edge[0],
                "Nodo_A": last_edge[1],
                "PercentualePercorsa": perc,
                "DistanzaPercorsa_m": seg_len,
                "LunghezzaEdge_m": edge_len,
                "TempoAtteso_s": expected_time
            })

# -------- Esporta risultati --------
df_segments = pd.DataFrame(all_segments)
df_segments.to_csv("segments_all_activities.csv", index=False)
print("Esportato 'segments_all_activities.csv'")
