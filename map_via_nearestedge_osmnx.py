import pandas as pd
import osmnx as ox
from pyrosm import OSM
from shapely.geometry import LineString
import numpy as np
import os


# Elabora un segmento GPS associato a un edge e restituisce un dizionario con i dati calcolati
def process_segment(G, activity_id, edge, gps_segment, time_segment):
    """
    Elabora un segmento GPS associato a un edge e restituisce un dizionario con i dati calcolati.
    """
    ed = G.get_edge_data(*edge)

    # Se manca la geometria, ricrea linea diretta tra i nodi u,v
    geom = ed.get("geometry")
    if geom is None:
        u, v = edge[0], edge[1]
        u_xy = (G.nodes[u]["x"], G.nodes[u]["y"])
        v_xy = (G.nodes[v]["x"], G.nodes[v]["y"])
        geom = LineString([u_xy, v_xy])
        ed["geometry"] = geom

    sl = segment_distance(gps_segment)
    el = ed.get('length', 0)
    nm = ed.get('name', 'Sconosciuto')
    legal, cw = check_legality(ed, gps_segment, edge[0], edge[1], G)
    perc = min(sl / el, 1) * 100 if el else 0
    t0, t1 = time_segment[0], time_segment[-1]
    exp = ((t1 - t0).total_seconds() / sl * el) if sl > 0 and pd.notnull(t0) and pd.notnull(t1) else np.nan

    return {
        'ActivityId': activity_id, 'IsLegal': legal, 'HasCycleway': cw,
        'NomeVia': nm, 'Nodo_Da': edge[0], 'Nodo_A': edge[1], 'Key': edge[2],
        'PercentualePercorsa': perc, 'DistanzaPercorsa_m': sl,
        'LunghezzaEdge_m': el, 'TempoAtteso_s': exp,
        'TimeFrom': t0, 'TimeTo': t1
    }

# Calcola la distanza totale di una lista di punti (lat, lon)
def segment_distance(gps_segment):
    """Calcola la distanza totale (metri) di una lista di punti (lat, lon)"""
    if len(gps_segment) < 2:
        return 0
    d = 0
    for (lat1, lon1), (lat2, lon2) in zip(gps_segment[:-1], gps_segment[1:]):
        d += ox.distance.great_circle(lat1, lon1, lat2, lon2)
    return d

# Restituisce il vettore normalizzato
def get_direction(vec):
    norm = np.linalg.norm(vec)
    return np.array(vec) / norm if norm > 0 else np.array([0, 0])

# Controlla se il segmento GPS e l'arco OSM hanno la stessa direzione
# Utile per verificare la legalità del senso di marcia
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

# Controlla se l'arco è legale per la bici
def check_legality(edge_data, gps_segment, u, v, G):
    # Controlla se il segmento ha una pista ciclabile (cioè se uno dei tag è presente e valorizzato)
    has_cycleway = any(edge_data.get(tag) not in [None, '', 'no'] for tag in ["cycleway", "cycleway:right", "cycleway:left", "cycleway:both"])
    if edge_data.get("highway") == "cycleway":
        has_cycleway = True

    # Se ha pista ciclabile, è sempre legale
    if has_cycleway:
        return True, True

    # Altrimenti calcola direzione e legalità in base al senso di marcia
    oneway = edge_data.get("oneway", False)
    geometry = edge_data.get("geometry")
    if geometry is None or len(gps_segment) < 2:
        return False, has_cycleway
    same = is_same_direction(geometry, gps_segment, u, v, G)
    if oneway in ["yes", True, "True", 1, "1"]:
        legal = same
    elif oneway == "-1":
        legal = not same
    else:
        legal = True

    return legal, has_cycleway



###
###
### MAIN
if __name__ == '__main__':
    # -------- Carica e filtra dati GPS --------
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'matched_coords.csv')
    print("Caricamento file CSV da:", csv_path)
    df_all = pd.read_csv(csv_path, usecols=["ActivityId","NEW_Latitude","NEW_Longitude","Time"]).dropna(subset=["NEW_Latitude","NEW_Longitude"])
    print(f"Totale punti GPS letti: {len(df_all)}")
    df_all["ParsedTime"] = pd.to_datetime(
        df_all["Time"],
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce"
    )

    # -------- Carica la rete OSM dal PBF storico (Geofabrik Bologna 2018) -------- 
    print("Carico grafo OSM dal PBF storico (Bologna 2018)...")
    pbf_path = os.path.join(script_dir, "osrm", "bologna-2018.osm.pbf")  # metti il file qui accanto allo script

    print("Carico grafo OSM dal PBF storico (Bologna 2018)... -- 2")
    if not os.path.exists(pbf_path):
        raise FileNotFoundError(f"PBF non trovato: {pbf_path}")

    print("Carico grafo OSM dal PBF storico (Bologna 2018)... -- 3")
    # Leggi rete 'cycling' con Pyrosm
    osm = OSM(pbf_path)    

    # Tag essenziali per ciclabilità: riduci gli attributi per risparmiare memoria
    extra_attrs = ["oneway", "highway",  "cycleway", "bicycle"]

    print("Carico grafo OSM dal PBF storico (Bologna 2018)... -- 4")

    # ----------- CARICA NODES ED EDGES ----------
    nodes, edges = osm.get_network(
        network_type="cycling",
        extra_attributes=extra_attrs,
        nodes=True
    )

    print("Carico grafo OSM dal PBF storico (Bologna 2018)... -- 5")

    # ---------- NORMALIZZA NODES ----------
    nodes = nodes.rename(columns={'id': 'osmid'})
    nodes = nodes.rename(columns={'lon': 'x', 'lat': 'y'})

    # pulizia e indice coerente
    nodes = nodes.dropna(subset=['osmid']).copy()
    nodes['osmid'] = pd.to_numeric(nodes['osmid'], errors='coerce')
    nodes = nodes.dropna(subset=['osmid']).copy()
    nodes['osmid'] = nodes['osmid'].astype('int64')
    nodes = nodes.set_index('osmid')

    # ---------- NORMALIZZA EDGES ----------
    # u/v devono esistere e avere stesso dtype dei nodes.index
    for col in ('u', 'v'):
        if col not in edges.columns:
            raise ValueError(f"Manca la colonna '{col}' in edges.")
    edges = edges.dropna(subset=['u','v']).copy()
    edges['u'] = pd.to_numeric(edges['u'], errors='coerce')
    edges['v'] = pd.to_numeric(edges['v'], errors='coerce')
    edges = edges.dropna(subset=['u','v']).copy()
    edges['u'] = edges['u'].astype('int64')
    edges['v'] = edges['v'].astype('int64')

    # FILTRA archi che puntano a nodi NON presenti (tipico dopo bbox)
    mask_uv_ok = edges['u'].isin(nodes.index) & edges['v'].isin(nodes.index)
    edges = edges.loc[mask_uv_ok].copy()

    # crea 'key' se manca o se non garantisce unicità
    if 'key' not in edges.columns or edges.duplicated(['u','v','key']).any():
        edges['key'] = edges.groupby(['u','v']).cumcount()

    # imposta MultiIndex richiesto (u, v, key)
    edges = edges.set_index(['u','v','key']).sort_index()

    print("Carico grafo OSM dal PBF storico (Bologna 2018)... -- 5.1")

    # Crea MultiDiGraph compatibile con OSMnx e semplifica
    G = ox.graph_from_gdfs(nodes, edges)
    print("Carico grafo OSM dal PBF storico (Bologna 2018)... -- 6")
    G = ox.simplify_graph(G)

    # assicurati di avere la lunghezza degli archi in metri
    print("Carico grafo OSM dal PBF storico (Bologna 2018)... -- 7")
    ox.distance.add_edge_lengths(G)

    print(f"Grafo caricato dal PBF: {len(G.nodes)} nodi, {len(G.edges)} archi")


    # -------- CALCOLO VETTORIALE nearest_edges UNA SOLA VOLTA --------
    print("Inizio calcolo nearest_edges per tutti i punti...")
    xs = df_all['NEW_Longitude'].values
    ys = df_all['NEW_Latitude'].values
    print(f"Calcolo nearest_edges per {len(xs)} punti...")
    # Split xs and ys to avoid memory issues with large datasets
    if len(xs) > 1000000:
        chunk_size = 1000000
        edges, dists = [], []
        for i in range(0, len(xs), chunk_size):
            chunk_edges, chunk_dists = ox.distance.nearest_edges(G, X=xs[i:i+chunk_size], Y=ys[i:i+chunk_size], return_dist=True)
            print(f"Calcolati {len(chunk_edges)} nearest_edges per chunk {i//chunk_size + 1}")
            edges.extend(chunk_edges)
            dists.extend(chunk_dists)
    else:
        edges, dists = ox.distance.nearest_edges(G, X=xs, Y=ys, return_dist=True)
    print("nearest_edges calcolati.")
    df_all['NearestEdge'] = list(edges)
    df_all['EdgeDist_m']   = dists
    print("Colonne NearestEdge e EdgeDist_m aggiunte al DataFrame.")

    # -------- Analizza ogni ActivityId --------
    all_segments = []
    segment_count = 0
    num_activities = df_all['ActivityId'].nunique()
    print(f"Numero di ActivityId da processare: {num_activities}")

    num_activity_counter = 0

    for idx, (activity_id, df) in enumerate(df_all.groupby('ActivityId'), start=1):
        num_activity_counter += 1
        print(f"\nElaborazione ActivityId {activity_id} ({num_activity_counter}/{num_activities}) con {len(df)} punti GPS...")
        # df = df.sort_values('ParsedTime')
        gps = list(zip(df['NEW_Latitude'], df['NEW_Longitude']))
        times = list(df['ParsedTime'])
        nes   = df['NearestEdge'].tolist()
        last = None
        seg, seg_t = [], []

        # Processa i segmenti
        for i, (pt, t, e) in enumerate(zip(gps, times, nes), start=1):
            if e is None:
                print(f"  Punto {i}: nessun edge trovato, skip")
                continue
            if e != last and seg:
                result = process_segment(G, activity_id, last, seg, seg_t)
                if result:
                    all_segments.append(result)
                    segment_count += 1
                seg, seg_t = [], []
            seg.append(pt)
            seg_t.append(t)
            last = e

        # Ultimo segmento
        if seg and last:
            result = process_segment(G, activity_id, last, seg, seg_t)
            if result:
                all_segments.append(result)
                segment_count += 1

    # -------- Esporta --------
    out = pd.DataFrame(all_segments)
    out.to_csv(os.path.join(script_dir,'segments_all_activities_REMAKE.csv'),index=False)
    print(f"Esportato 'segments_all_activities_REMAKE.csv' con {len(all_segments)} segmenti.")
