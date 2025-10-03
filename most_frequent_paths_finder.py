import pandas as pd
import geopandas as gpd
from shapely.geometry import box
from pyproj import CRS
import numpy as np
import folium
from folium.features import DivIcon

# Parameters
MATCHED_COORDS_CSV = "matched_coords.csv"
CELL_SIZE_M = 750
OUTPUT_OD = "od_by_grid.csv"          # Save origin/destination as RANK (1..K)
OUTPUT_GRID_GEOJSON = "grid_tiles.geojson"
OUTPUT_HTML = "grid_top_cells.html"
TOP_K_CELLS = 5

# 1) Load origins/destinations
print(">>> 1) Loading origins/destinations...")
df = pd.read_csv(MATCHED_COORDS_CSV, parse_dates=["Time"]).dropna(subset=["NEW_Latitude","NEW_Longitude"])
orig = df.groupby("ActivityId").head(1)
dest = df.groupby("ActivityId").tail(1)

g_orig = gpd.GeoDataFrame(geometry=gpd.points_from_xy(orig.NEW_Longitude, orig.NEW_Latitude), crs=4326)
g_dest = gpd.GeoDataFrame(geometry=gpd.points_from_xy(dest.NEW_Longitude, dest.NEW_Latitude), crs=4326)

# 2) Create grid in UTM 32N
print(">>> 2) Creating grid...")
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

# 3) Compute OD per cell
print(">>> 3) Computing OD per cell...")
orig_join = gpd.sjoin(g_orig, grid, how="left", predicate="within")[["cell_id"]].rename(columns={"cell_id":"origin"})
dest_join = gpd.sjoin(g_dest, grid, how="left", predicate="within")[["cell_id"]].rename(columns={"cell_id":"dest"})
od = pd.concat([orig_join.reset_index(drop=True), dest_join.reset_index(drop=True)], axis=1).dropna().astype(int)

od_counts = od.groupby(["origin","dest"]).size().reset_index(name="count")

# 4) Compute top-K cells
print(">>> 4) Computing top-K cells...")
score = od_counts.groupby("origin")["count"].sum().add(od_counts.groupby("dest")["count"].sum(), fill_value=0)
top = (score.sort_values(ascending=False)
            .head(TOP_K_CELLS)
            .rename_axis("cell_id")      # Clear name for the index
            .reset_index())               # Now there is a 'cell_id' column
top["rank"] = range(1, len(top)+1)

# Map cell_id -> rank
rank_map = dict(zip(top["cell_id"], top["rank"]))

# 5) Final CSV with RANK instead of cell ids (keep only pairs among top cells)
print(">>> 5) Saving OD with rank...")
od_rank = od_counts.copy()
od_rank["origin"] = od_rank["origin"].map(rank_map)
od_rank["dest"]   = od_rank["dest"].map(rank_map)
od_rank = od_rank.dropna(subset=["origin","dest"]).astype({"origin":int,"dest":int})
od_rank = od_rank.sort_values("count", ascending=False)
od_rank.to_csv(OUTPUT_OD, index=False)

# 6) Map with rank numbers
print(">>> 6) Saving map of top-K cells...")
grid_wgs84 = grid.to_crs(4326)

# Compute centroids in UTM, then transform to WGS84
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

# 7) Most frequent arcs between top cell pairs (directional A->B) ===
SEGMENTS_CSV = "segments_all_activities.csv"   # ActivityId, Node_From, Node_To
OUTPUT_TOP_ARCS = "top_cell_pairs_arc_favorites_directed.csv"
TOP_PER_PAIR = 3  # Number of paths per pair of top cells

# a) Reconstruct cell assignment (with ActivityId) for origins and destinations
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

# b) Load segments and sort (if there are temporal columns)
seg = pd.read_csv(SEGMENTS_CSV)
sort_cols = [c for c in ["ActivityId","TimeFrom","TimeTo"] if c in seg.columns]
if sort_cols:
    seg = seg.sort_values(sort_cols)
else:
    seg = seg.sort_values(["ActivityId"])

rows = []

# c) For each ordered pair A->B among top cells, get activities with (origin_cell=A, dest_cell=B)
for a in sorted(top_cells):
    for b in sorted(top_cells):
        if a == b:
            continue
        acts = od_cells[(od_cells.origin_cell==a) & (od_cells.dest_cell==b)]["ActivityId"].unique()
        if len(acts) == 0:
            continue

        sub = seg[seg["ActivityId"].isin(acts)][["ActivityId","Nodo_Da","Nodo_A"]].copy()

        # For each activity: first arc = exit from A, last arc = arrival in B
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

# d) Aggregate and keep TOP_PER_PAIR paths per pair A->B
if rows:
    dfp = pd.DataFrame(rows)
    agg = (dfp.groupby(["src_cell","dst_cell","node_src_from","node_src_to","node_dst_from","node_dst_to"], as_index=False)
               .size().rename(columns={"size":"count"}))
    agg = agg.sort_values(["src_cell","dst_cell","count"], ascending=[True, True, False])
    top_paths = agg.groupby(["src_cell","dst_cell"], group_keys=False).head(TOP_PER_PAIR).reset_index(drop=True)

    # Add cell ranks (1..K) for readability
    cell2rank = dict(zip(top["cell_id"], top["rank"]))
    top_paths["src_rank"] = top_paths["src_cell"].map(cell2rank)
    top_paths["dst_rank"] = top_paths["dst_cell"].map(cell2rank)

    # Save
    cols = ["src_cell","dst_cell","src_rank","dst_rank","node_src_from","node_src_to","node_dst_from","node_dst_to","count"]
    top_paths[cols].to_csv(OUTPUT_TOP_ARCS, index=False)
    print(f">>> 7) Saved: {OUTPUT_TOP_ARCS} ({len(top_paths)} rows)")
else:
    print(">>> 7) No activities found between top pairs (check the data).")
