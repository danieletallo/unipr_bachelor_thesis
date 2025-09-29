## Dijkstra's Algorithm Implementation
# Prendo in considerazione il file .osm.pbf del 2018
# Creo il grafo con gli archi pesati in base alla stima dei tempi del file "edges_with_estimated_times.csv"
# per capire la direzione di marcia prendo spunto dal "map_via_nearestedge_osmnx.py"
import os
import osmnx as ox
import networkx as nx
from pyrosm import OSM
import pandas as pd
import geopandas as gpd
import contextily as ctx
import matplotlib.pyplot as plt
from shapely import LineString
from shapely.ops import substring
from shapely.geometry import Point

def normalize_nodes_and_edges(nodes, edges):
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
    
    return nodes, edges

def plot_graph_with_basemap(graph, filename):
    # Proietta in Web Mercator (EPSG:3857) per allineare le tile
    graph_3857 = ox.project_graph(graph, to_crs="EPSG:3857")

    # Plot del grafo già in 3857
    fig, ax = ox.plot_graph(
        graph_3857,
        node_size=0.5,
        edge_color="black",
        edge_linewidth=0.7,
        bgcolor="white",
        show=False,
        close=False
    )

    # Fissa uno zoom valido (p.es. 13 per Bologna)
    ctx.add_basemap(
        ax,
        # source=ctx.providers.CartoDB.Voyager,
        source=ctx.providers.OpenStreetMap.Mapnik,
        zoom=13,
        attribution=True,
        reset_extent=False
    )

    
    # Salvo il plot
    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    
#######################
#######################

# ------------------------------
#  BIKE-DIRECTION (solo 4 tag)
# ------------------------------
FORBIDDEN_HW = {"motorway", "motorway_link"}  # elimina autostrade e rampe

def _val(d, k):
    """Legge tag come stringa normalizzata."""
    return str(d.get(k, "")).strip().lower()

def _highway_vals(d):
    """Gestisce highway come stringa, lista o 'a;b'."""
    hw = d.get("highway")
    if isinstance(hw, list):
        vals = hw
    elif isinstance(hw, str):
        vals = [s.strip().lower() for s in hw.split(";")]
    else:
        vals = []
    return set(v.lower() for v in vals)

def _invert_geom(g):
    return LineString(list(g.coords)[::-1]) if isinstance(g, LineString) else g

def _bike_dir_from_basic_tags(ed):
    """
    Usa SOLO: oneway, highway, cycleway, bicycle.
    Ritorna: 'none' | 'forward' | 'backward' | 'both'
    - 'forward' intende verso u->v della riga originale.
    """
    # stop se bici vietate
    if _val(ed, "bicycle") in {"no", "dismount"}:
        return "none"
    if _highway_vals(ed) & FORBIDDEN_HW:
        return "none"

    # cycleway=opposite* → bidirezionale per bici
    cyc = _val(ed, "cycleway")
    if "opposite" in cyc:
        return "both"

    # oneway generico
    ow = _val(ed, "oneway")
    if ow in {"yes", "1", "true"} or ed.get("oneway") is True or ed.get("oneway") == 1:
        return "forward"
    if ow == "-1":
        return "backward"
    # altrimenti bidirezionale
    return "both"

def make_bike_directed_edges(edges):
    """
    Da edges (index: u,v,key) crea edges_bike direzionati:
      - rimuove 'none'
      - 'forward' → u->v
      - 'backward' → v->u (geometry invertita)
      - 'both' → entrambe le direzioni (duplicando e invertendo)
    """
    df = edges.reset_index().copy()

    # considero solo i tag essenziali
    for c in ["oneway", "highway", "cycleway", "bicycle", "geometry"]:
        if c not in df.columns:
            df[c] = None

    # applico la logica di direzionalità
    df["bike_dir"] = df.apply(_bike_dir_from_basic_tags, axis=1)
    df = df[df["bike_dir"] != "none"].copy()

    fwd = df[df["bike_dir"].isin(["forward", "both"])].copy()

    bwd = df[df["bike_dir"].isin(["backward", "both"])].copy()
    # inverti verso e geometry
    bwd[["u", "v"]] = bwd[["v", "u"]].to_numpy()
    if "geometry" in bwd.columns:
        bwd["geometry"] = bwd["geometry"].apply(_invert_geom)

    out = pd.concat([fwd, bwd], ignore_index=True)
    out["key"] = out.groupby(["u", "v"]).cumcount()
    out = out.set_index(["u", "v", "key"]).sort_index()
    return out

def assign_edge_weights(edges, weights_csv="edges_with_estimated_times.csv"):
    """
    Assegna i pesi agli archi in base al file CSV fornito.
    Modifica il DataFrame edges aggiungendo la colonna 'weight'.
    """
    print(">>> Assegnazione pesi agli archi in base a edges_with_estimated_times.csv...")
    weights_df = pd.read_csv(weights_csv, usecols=["Nodo_Da","Nodo_A","TempoStimato_s"])
    weights_df = weights_df.rename(columns={"Nodo_Da": "u", "Nodo_A": "v", "TempoStimato_s": "weight"})
    weights_df = weights_df.dropna(subset=["u","v","weight"]).copy()
    
    # Scorro gli edges e assegno il peso se esiste in u, v o v, u
    edge_weights = {}
    weight_set = set(zip(weights_df["u"], weights_df["v"], weights_df["weight"]))
    for (u, v, key) in edges.index:
        # cerca peso in (u,v) o (v,u)
        weight = None
        for (wu, wv, w) in weight_set:
            if (u == wu and v == wv) or (u == wv and v == wu):
                weight = w
                break
        if weight is not None:
            edge_weights[(u, v, key)] = weight
        else:
            edge_weights[(u, v, key)] = -1  # peso -1 se non trovato
    
    # Aggiungo i pesi agli archi
    edges['weight'] = edges.index.map(edge_weights)
    edges['weight'] = edges['weight'].astype(float)
    print(f"Archi con peso assegnato: {edges['weight'].notna().sum()} su {len(edges)}")
    return edges

#######################

#######################


def main():
    # Carico il grafo da file .osm.pbf
    print(">>> Caricamento grafo da file .osm.pbf...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pbf_path = os.path.join(script_dir, "osrm", "bologna-2018.osm.pbf")

    # Leggo il grafo stradale
    osm = OSM(pbf_path)

    # Tag essenziali per ciclabilità: riduci gli attributi per risparmiare memoria
    extra_attrs = ["oneway", "highway", "cycleway", "bicycle"]

    # Carico archi e nodi
    print(">>> Caricamento archi e nodi...")
    nodes, edges = osm.get_network(
        network_type="cycling",
        extra_attributes=extra_attrs,
        nodes=True
    )
    
    # Normalizzo nodi e archi
    print(">>> Normalizzazione nodi e archi...")
    nodes, edges = normalize_nodes_and_edges(nodes, edges)
    
    # Carico il grafo con osmnx, semplifico il grafo per non avere nodi intermedi, come nella segmentazione all'inizio
    print(">>> Creazione grafo con osmnx...")
    graph = ox.graph_from_gdfs(nodes, edges)
    graph = ox.simplify_graph(graph)
    
    # Riprendo gli archi e nodi dal grafo semplificato, così non ho nodi intermedi
    # Se non viene fatto vengono considerati anche i nodi intermedi e quindi non corrispondono con i segmenti
    print(">>> Estrazione nodi e archi dal grafo semplificato...")
    nodes, edges = ox.graph_to_gdfs(graph)
    
    # Considero vera direzionalità bici
    print(">>> Direzionalità bici da 4 tag (oneway/highway/cycleway/bicycle)...")
    edges = make_bike_directed_edges(edges)
 
    # Assegno i pesi agli archi in base al file CSV   
    edges = assign_edge_weights(edges)
    # Rimuovo archi senza peso (-1)
    edges = edges[edges['weight'] >= 0].copy()
    
    # Esempio di arco con peso
    example_edge = edges[edges['weight'] < float('inf')].iloc[0]
    print(f"Esempio di arco con peso: u={example_edge.name[0]}, v={example_edge.name[1]}, weight={example_edge['weight']:.2f} s")
    
    # Salvo in un csv i nodi u, v in ordine di osmid con informazione bidirezionalità
    print(">>> Salvo i nodi in nodi_grafo.csv...")
    edges_df = edges.reset_index()[['u','v']].drop_duplicates().sort_values(['u','v'])
    
    # Creo un set di tutte le coppie (u,v) per verificare rapidamente l'esistenza
    edge_set = set(zip(edges_df['u'], edges_df['v']))
    
    # Aggiungo la colonna bidirectional che indica se esiste anche (v,u)
    edges_df['bidirectional'] = edges_df.apply(
        lambda row: (row['v'], row['u']) in edge_set, axis=1
    )
    
    # Ricreo il grafo con gli attributi dentro
    graph = ox.graph_from_gdfs(nodes, edges)
    
    # Salvo il grafo in formato GraphML
    ox.save_graphml(graph, "grafo.graphml")
    print(">>> Salvato: grafo.graphml")

    # Salvo il csv
    edges_df.to_csv("nodi_grafo.csv", index=False)
    print(">>> Salvato: nodi_grafo.csv")

    # Visualizzo grafo
    # plot_graph_with_basemap(graph, filename="dijkstra_graph.png")
    # print(">>> Salvato: dijkstra_graph.png")

    # Mini plot del grafo attorno a un nodo di esempio
    # edges è il tuo GeoDataFrame con index (u,v,key) e colonne 'geometry', 'weight'
    # print(">>> Plot del grafo completo con frecce e pesi...")
    # TODO



if __name__ == "__main__":
    main()