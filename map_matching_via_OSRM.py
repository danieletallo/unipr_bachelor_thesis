import pandas as pd
import osmnx as ox
from pyrosm import OSM
from shapely.geometry import LineString
import numpy as np
import os
import requests
import time

BASE_URL = "http://localhost:5000"
CHUNK_SIZE = 100  # numero di punti GPS per query OSRM
MAXIMUM_RADIUS = 15

### MAIN
if __name__ == '__main__':
    
    # -------- Carica e filtra dati GPS --------
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'cycle.csv')
    pkl_path = os.path.join(script_dir, 'cycle.pkl')

    if os.path.exists(pkl_path):
        print("Carico dataframe da pickle...")
        df_all = pd.read_pickle(pkl_path)
    else:
        print("Carico dataframe da CSV...")

        df_all = (
            pd.read_csv(csv_path, usecols=["ActivityId","Latitude","Longitude","Time"])
            .dropna(subset=["Latitude","Longitude"])
        )

        df_all["UnixSec"] = pd.to_datetime(df_all["Time"], errors="coerce")
        df_all = df_all.dropna(subset=["UnixSec"])
        df_all["UnixSec"] = df_all["UnixSec"].astype("int64") // 10**9  # ns → s

        df_all.to_pickle(pkl_path)   # salva pronto all’uso

    activity_ids = df_all['ActivityId'].unique()
    print(f"Totale ActivityId unici: {len(activity_ids)}")

    contatore = 0
    contatore_gps = 0
    contatore_gps_errati = 0
    counter_iterations = 0

    # crea lista con Longitude, Latitude, NewLongitude, NewLatitude
    matched_coords = []

    timewatch = time.time()
    with requests.Session() as sess:
        for activity_id, rows_by_activity_id in df_all.groupby("ActivityId", sort=False):
            xy = rows_by_activity_id[["Longitude", "Latitude"]].to_numpy()

            contatore += 1
            print("Attivita' n.", contatore)
            print(f"ActivityId {activity_id}: {len(xy)} punti GPS")

            # xy count > 100 -> split in piu' query
            # tramite for
            for i in range(0, len(xy), CHUNK_SIZE):
                chunk = xy[i:i+CHUNK_SIZE]
                coords = ";".join([f"{lon},{lat}" for lon, lat in chunk])
                chunk_times = rows_by_activity_id["UnixSec"].iloc[i:i+CHUNK_SIZE]
                chunk_times_raw = rows_by_activity_id["Time"].iloc[i:i+CHUNK_SIZE]  # <- NEW

                print(f"  Query OSRM con {len(chunk)} punti GPS")

                data = {"tracepoints": []} 
                try:
                    counter_iterations += 1

                    # tentativi con radius crescente SOLO se fallisce
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
                            
                            # se ho errori sul match oppure tracepoints None, riprova con radius più grande
                            if (
                                data.get("code") == "NoSegment" or data.get("code") == "NoMatch" 
                                or (data.get("code") == "Ok" and any(tp is None for tp in data.get("tracepoints", [])))
                            ):
                                if radius != MAXIMUM_RADIUS:
                                    continue  # prova con radius più grande

                            if data.get("code") == "Ok":
                                break  # successo: esci dal loop

                            # altri codici -> non insistere col radius
                            break
                        else:
                            # HTTP error: se 400 NoSegment o NoMatch, riprova; altrimenti esci
                            try:
                                j = r.json()
                                if j.get("code") == "NoSegment" or j.get("code") == "NoMatch":
                                    continue
                            except Exception:
                                pass
                            break
                    else:
                        # se esci dal for senza break: tutti i tentativi falliti
                        if (data.get("code") == "Ok" and any(tp is None for tp in data.get("tracepoints", []))):
                            print("  -> Ci sono tracepoints che sono None")
                        else:
                            print("\033[91m" + r.text + "\033[0m")

                except Exception:
                    print("ECCEZIONE!")

                finally:
                    tps = data.get("tracepoints", [])

                    for idx, (old_lon, old_lat) in enumerate(chunk):
                        if idx >= len(tps) or tps[idx] is None:
                            contatore_gps_errati += 1
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

            contatore_gps += len(xy)

            if contatore == 300 :
                break

    print("Contatore:", contatore)
    print("Contatore punti GPS in errore:", contatore_gps_errati, " / ", contatore_gps)
    print("Tempo impiegato:", time.time() - timewatch)
    print("Tempo medio per ActivityId:", (time.time() - timewatch) / contatore)
    print("Tempo medio per punto GPS:", (time.time() - timewatch) / contatore_gps)

    print("Tempo stimato su 78 milioni punti GPS:", (time.time() - timewatch) / contatore_gps * 78000000 / 3600, "ore")

    pd.DataFrame(matched_coords, columns=["ActivityId","Time","OLD_Latitude","OLD_Longitude","NEW_Latitude","NEW_Longitude"]).to_csv("matched_coords.csv", index=False)


## TODO
## OK - Verificare output OSRM API /match call
## OK - Associare ad ogni punto originale la nuova coordinata matched
## OK - Salvare su file CSV i risultati
## OK - Valutare, nuovamente, tempi di esecuzione. In data 05-09-2025, il tempo stimato era 8.55 ore (stimato elaborando 800k su 80M)