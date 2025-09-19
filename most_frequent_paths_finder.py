import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from pyproj import CRS
import numpy as np
import folium
from folium.features import DivIcon

# Parametri
MATCHED_COORDS_CSV = "matched_coords.csv"
CELL_SIZE_M = 750
OUTPUT_OD = "od_by_grid.csv"          # qui salviamo origin/dest come RANK (1..K)
OUTPUT_GRID_GEOJSON = "grid_tiles.geojson"
OUTPUT_HTML = "grid_top_cells.html"
TOP_K_CELLS = 5

# 1) Origini/Destinazioni
print(">>> 1) Caricamento origini/destinazioni...")
df = pd.read_csv(MATCHED_COORDS_CSV, parse_dates=["Time"]).dropna(subset=["NEW_Latitude","NEW_Longitude"])
orig = df.groupby("ActivityId").head(1)
dest = df.groupby("ActivityId").tail(1)

g_orig = gpd.GeoDataFrame(geometry=gpd.points_from_xy(orig.NEW_Longitude, orig.NEW_Latitude), crs=4326)
g_dest = gpd.GeoDataFrame(geometry=gpd.points_from_xy(dest.NEW_Longitude, dest.NEW_Latitude), crs=4326)

# 2) Griglia semplice in UTM 32N
print(">>> 2) Creazione griglia...")
utm = CRS.from_epsg(32632)
g_orig, g_dest = g_orig.to_crs(utm), g_dest.to_crs(utm)
minx = min(g_orig.total_bounds[0], g_dest.total_bounds[0])
miny = min(g_orig.total_bounds[1], g_dest.total_bounds[1])
maxx = max(g_orig.total_bounds[2], g_dest.total_bounds[2])
maxy = max(g_orig.total_bounds[3], g_dest.total_bounds[3])

xs = np.arange(minx, maxx+CELL_SIZE_M, CELL_SIZE_M)
ys = np.arange(miny, maxy+CELL_SIZE_M, CELL_SIZE_M)
cells = [box(xs[i], ys[j], xs[i+1], ys[j+1]) for i in range(len(xs)-1) for j in range(len(ys)-1)]
grid = gpd.GeoDataFrame({"cell_id": range(len(cells))}, geometry=cells, crs=utm)

# 3) OD per cella
print(">>> 3) Calcolo OD per cella...")
orig_join = gpd.sjoin(g_orig, grid, how="left", predicate="within")[["cell_id"]].rename(columns={"cell_id":"origin"})
dest_join = gpd.sjoin(g_dest, grid, how="left", predicate="within")[["cell_id"]].rename(columns={"cell_id":"dest"})
od = pd.concat([orig_join.reset_index(drop=True), dest_join.reset_index(drop=True)], axis=1).dropna().astype(int)

od_counts = od.groupby(["origin","dest"]).size().reset_index(name="count")

# 4) Score cella e TOP-K con colonna coerente
print(">>> 4) Calcolo top-K celle...")
score = od_counts.groupby("origin")["count"].sum().add(od_counts.groupby("dest")["count"].sum(), fill_value=0)
top = (score.sort_values(ascending=False)
            .head(TOP_K_CELLS)
            .rename_axis("cell_id")      # <— nome chiaro per l’indice
            .reset_index())               # ora c’è una colonna 'cell_id'
top["rank"] = range(1, len(top)+1)

# mappa cella_id -> rank
rank_map = dict(zip(top["cell_id"], top["rank"]))

# 5) CSV finale con RANK al posto degli id cella (tieni solo coppie tra top)
print(">>> 5) Salvataggio OD con rank...")
od_rank = od_counts.copy()
od_rank["origin"] = od_rank["origin"].map(rank_map)
od_rank["dest"]   = od_rank["dest"].map(rank_map)
od_rank = od_rank.dropna(subset=["origin","dest"]).astype({"origin":int,"dest":int})
od_rank = od_rank.sort_values("count", ascending=False)
od_rank.to_csv(OUTPUT_OD, index=False)

# 6) Mappa con numeri dei rank
print(">>> 6) Salvataggio mappa top-K celle...")
grid_wgs84 = grid.to_crs(4326)

# calcolo centroidi in UTM, poi trasformo in WGS84
centroids = grid.to_crs(32632).centroid.to_crs(4326)

m = folium.Map(location=[centroids.y.mean(), centroids.x.mean()], zoom_start=12)

folium.GeoJson(
    grid_wgs84,
    style_function=lambda x: {"fillOpacity":0,"color":"black","weight":0.5}
).add_to(m)

for _, r in top.iterrows():
    geom = grid_wgs84.loc[grid_wgs84["cell_id"] == r["cell_id"], "geometry"].iloc[0]
    c = geom.centroid
    folium.GeoJson(geom.__geo_interface__, style_function=lambda x: {"fillOpacity":0.1,"color":"orange","weight":2}).add_to(m)
    folium.Marker([c.y,c.x], icon=DivIcon(html=f"<b>{r['rank'].astype(int)}</b>")).add_to(m)

m.save(OUTPUT_HTML)
grid_wgs84.to_file(OUTPUT_GRID_GEOJSON, driver="GeoJSON")

# 7) Archi più frequenti tra coppie di celle TOP (direzionali A->B) ===
SEGMENTS_CSV = "segments_all_activities.csv"   # deve avere: ActivityId, Nodo_Da, Nodo_A (TimeFrom/TimeTo se ci sono)
OUTPUT_TOP_ARCS = "top_cell_pairs_arc_favorites_directed.csv"
TOP_PER_PAIR = 3  # quanti corridoi arco-src -> arco-dst tenere per coppia A->B

# a) ricostruisco assegnazione cella (con ActivityId) per origini e destinazioni
g_orig_id = gpd.GeoDataFrame(
    orig[["ActivityId"]].copy(),
    geometry=gpd.points_from_xy(orig.NEW_Longitude, orig.NEW_Latitude),
    crs=4326
).to_crs(utm)
g_dest_id = gpd.GeoDataFrame(
    dest[["ActivityId"]].copy(),
    geometry=gpd.points_from_xy(dest.NEW_Longitude, dest.NEW_Latitude),
    crs=4326
).to_crs(utm)

orig_cells = gpd.sjoin(g_orig_id, grid, how="left", predicate="within")[["ActivityId","cell_id"]].rename(columns={"cell_id":"origin_cell"})
dest_cells = gpd.sjoin(g_dest_id, grid, how="left", predicate="within")[["ActivityId","cell_id"]].rename(columns={"cell_id":"dest_cell"})
od_cells = orig_cells.merge(dest_cells, on="ActivityId", how="inner").dropna().astype({"origin_cell":int,"dest_cell":int})

top_cells = set(top["cell_id"].tolist())

# b) carico segmenti e ordino (se ci sono colonne temporali)
seg = pd.read_csv(SEGMENTS_CSV)
sort_cols = [c for c in ["ActivityId","TimeFrom","TimeTo"] if c in seg.columns]
if sort_cols:
    seg = seg.sort_values(sort_cols)
else:
    seg = seg.sort_values(["ActivityId"])

rows = []

# c) per ogni coppia ordinata A->B tra celle TOP, prendo attività con (origin_cell=A, dest_cell=B)
for a in sorted(top_cells):
    for b in sorted(top_cells):
        if a == b:
            continue
        acts = od_cells[(od_cells.origin_cell==a) & (od_cells.dest_cell==b)]["ActivityId"].unique()
        if len(acts) == 0:
            continue

        sub = seg[seg["ActivityId"].isin(acts)][["ActivityId","Nodo_Da","Nodo_A"]].copy()

        # per ogni activity: primo arco = uscita da A, ultimo arco = arrivo in B
        for act in acts:
            s = sub[sub.ActivityId==act]
            if s.empty:
                continue
            first = s.iloc[0]
            last  = s.iloc[-1]
            rows.append({
                "src_cell": a, "dst_cell": b,
                "node_src_from": int(first["Nodo_Da"]), "node_src_to": int(first["Nodo_A"]),
                "node_dst_from": int(last["Nodo_Da"]),  "node_dst_to": int(last["Nodo_A"]),
                "ActivityId": act
            })

# d) aggrego e tengo i TOP_PER_PAIR corridoi per coppia A->B
if rows:
    dfp = pd.DataFrame(rows)
    agg = (dfp.groupby(["src_cell","dst_cell","node_src_from","node_src_to","node_dst_from","node_dst_to"], as_index=False)
               .size().rename(columns={"size":"count"}))
    agg = agg.sort_values(["src_cell","dst_cell","count"], ascending=[True, True, False])
    top_corridors = agg.groupby(["src_cell","dst_cell"], group_keys=False).head(TOP_PER_PAIR).reset_index(drop=True)

    # opzionale: aggiungo i rank delle celle (1..K) per leggibilità
    cell2rank = dict(zip(top["cell_id"], top["rank"]))
    top_corridors["src_rank"] = top_corridors["src_cell"].map(cell2rank)
    top_corridors["dst_rank"] = top_corridors["dst_cell"].map(cell2rank)

    # salvo
    cols = ["src_cell","dst_cell","src_rank","dst_rank","node_src_from","node_src_to","node_dst_from","node_dst_to","count"]
    top_corridors[cols].to_csv(OUTPUT_TOP_ARCS, index=False)
    print(f">>> 7) Salvato: {OUTPUT_TOP_ARCS} ({len(top_corridors)} righe)")
else:
    print(">>> 7) Nessuna attività trovata tra coppie TOP (controlla i dati).")
