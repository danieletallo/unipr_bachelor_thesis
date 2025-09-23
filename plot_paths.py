import pandas as pd
import folium

path_index_max_to_filter = 3

def to_coords(df: pd.DataFrame, lat_col: str, lon_col: str):
    sub = df[[lat_col, lon_col]].dropna()
    return list(map(tuple, sub.to_numpy()))

def main():

    for path_index_to_filter in range(1, path_index_max_to_filter + 1):
        OUT_HTML = f"plot_path_{path_index_to_filter}_ALL.html"
    
        # 1) ActivityId con PathIndex scelto
        top = pd.read_csv(
            "filtered_activities_top3_paths.csv",
            usecols=["ActivityId", "PathIndex"]
        )
        act_ids = top.loc[top["PathIndex"] == path_index_to_filter, "ActivityId"].unique()

        # 2) Coordinate NEW solo per quegli ActivityId
        gps = pd.read_csv(
            "matched_coords.csv",
            usecols=["ActivityId", "NEW_Latitude", "NEW_Longitude"]
        )
        gps = gps[gps["ActivityId"].isin(act_ids)]

        if gps.empty:
            print("Nessuna riga corrispondente: niente da plottare.")
            return

        # 3) Calcolo bounds globali
        all_new = gps[["NEW_Latitude", "NEW_Longitude"]].dropna()
        minlat, minlon = all_new.min().values
        maxlat, maxlon = all_new.max().values
        center = [(minlat + maxlat) / 2.0, (minlon + maxlon) / 2.0]

        # 4) Mappa unica
        m = folium.Map(location=center, zoom_start=13, tiles="OpenStreetMap", control_scale=True)

        # 5) Una polyline blu per ogni ActivityId
        for act_id, rows in gps.groupby("ActivityId", sort=False):
            coords = to_coords(rows, "NEW_Latitude", "NEW_Longitude")
            if not coords:
                continue
            if len(coords) >= 2:
                folium.PolyLine(
                    coords, color="blue", weight=4, opacity=0.9,
                    tooltip=f"Activity {act_id}"
                ).add_to(m)
            else:
                # caso con un solo punto: metto un marker semplice
                folium.Marker(
                    coords[0], tooltip=f"Activity {act_id}"
                ).add_to(m)

        # 6) Fit su tutti i punti NEW
        m.fit_bounds([[minlat, minlon], [maxlat, maxlon]])

        # 7) Salva unico HTML
        m.save(OUT_HTML)
        print(f"Salvato: {OUT_HTML}")

if __name__ == "__main__":
    main()
