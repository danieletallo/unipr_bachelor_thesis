import pandas as pd
import osmnx as ox
from pyrosm import OSM
from shapely.geometry import LineString
import numpy as np
import os
import requests
import time

BASE_URL = "http://localhost:5000"

### MAIN
if __name__ == '__main__':
    
    # -------- Carica e filtra dati GPS --------
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'cycle.csv')

    print("Caricamento file CSV da:", csv_path)
    df_all = pd.read_csv(csv_path, usecols=["ActivityId","Latitude","Longitude","Time"]).dropna(subset=["Latitude","Longitude"])
    
    print(f"Totale punti GPS letti: {len(df_all)}")
    df_all['ParsedTime'] = pd.to_datetime(df_all['Time'], dayfirst=True, errors='coerce')

    # -------- Scorro gli ActivityId e applico match() --------
    activity_ids = df_all['ActivityId'].unique()
    print(f"Totale ActivityId unici: {len(activity_ids)}")

    matched_segments = []

    contatore = 0
    contatore_gps = 0
    contatore_gps_errati = 0
    errors_match = 0
    counter_iterations = 0

    chunk_per_query = 100

    timewatch = time.time()
    for activity_id, rows_by_activity_id in df_all.groupby("ActivityId", sort=False):
        xy = rows_by_activity_id[["Longitude", "Latitude"]].to_numpy()

        if len(xy) >= 2:
            print(f"ActivityId {activity_id}: {len(xy)} punti GPS")

            # xy count > 100 -> split in piu' query
            # tramite for
            for i in range(0, len(xy), chunk_per_query):
                chunk = xy[i:i+chunk_per_query]
                coords = ";".join([f"{lon},{lat}" for lon, lat in chunk])
                chunk_times = rows_by_activity_id["ParsedTime"].iloc[i:i+chunk_per_query]

                print(f"  Query OSRM con {len(chunk)} punti GPS")
                # Query OSRM server
                # try:
                #     counter_iterations += 1
                #     r = requests.get(
                #         f"{BASE_URL}/match/v1/bicycle/{coords}",
                #         params={
                #             "steps": "false",
                #             "geometries": "geojson",
                #             "overview": "full",
                #             "annotations": "true",
                #             "timestamps": ";".join(
                #                 (chunk_times.astype("int64") // 10**9).astype(str).tolist()
                #             )#,
                #             #"radiuses": ";".join(["10"] * len(chunk))  ## aggiunto alla fine
                #         }
                #     )

                #     r.raise_for_status()
                #     data = r.json()

                # except:
                #     errors_match += 1
                #     contatore_gps_errati += len(chunk)
                #     print("\033[91m" + r.text + "\033[0m")

                try:
                    counter_iterations += 1

                    # tentativi con radius crescente SOLO se fallisce
                    for rad in [None, 10, 15]:
                        params = {
                            "steps": "false",
                            "geometries": "geojson",
                            "overview": "full",
                            "annotations": "true",
                            "timestamps": ";".join(
                                (chunk_times.astype("int64") // 10**9).astype(str).tolist()
                            )
                        }
                        if rad is not None:
                            params["radiuses"] = ";".join([str(rad)] * len(chunk))

                        r = requests.get(f"{BASE_URL}/match/v1/bicycle/{coords}", params=params)

                        if r.ok:
                            data = r.json()
                            if data.get("code") == "Ok":
                                break  # successo: esci dal loop
                            if data.get("code") == "NoSegment":
                                continue  # prova con radius più grande
                            # altri codici -> non insistere col radius
                            break
                        else:
                            # HTTP error: se 400 NoSegment, riprova; altrimenti esci
                            try:
                                j = r.json()
                                if j.get("code") == "NoSegment":
                                    continue
                            except Exception:
                                pass
                            break
                    else:
                        # se esci dal for senza break: tutti i tentativi falliti
                        errors_match += 1
                        contatore_gps_errati += len(chunk)
                        print("\033[91m" + r.text + "\033[0m")

                except Exception:
                    errors_match += 1
                    contatore_gps_errati += len(chunk)
                    print("\033[91m" + "Errore di rete/altro durante la richiesta" + "\033[0m")

            contatore += 1
            contatore_gps += len(xy)
            print("Attivita' n.", contatore)

            if contatore == 100 :
                break

    print("Contatore:", contatore)
    print("Contatore punti GPS in errore:", contatore_gps_errati, " / ", contatore_gps)
    print("Tempo impiegato:", time.time() - timewatch)
    print("Tempo medio per ActivityId:", (time.time() - timewatch) / contatore)
    print("Tempo medio per punto GPS:", (time.time() - timewatch) / contatore_gps)

    print("Tempo stimato su 78 milioni punti GPS:", (time.time() - timewatch) / contatore_gps * 78000000 / 3600, "ore")
    print("Errori match:", errors_match, " su", counter_iterations, "iterazioni")



## TODO
## - Verificare output OSRM API /match call
## - Associare ad ogni punto originale la nuova coordinata matched
## - Salvare su file CSV i risultati
## - Valutare, nuovamente, tempi di esecuzione. In data 05-09-2025, il tempo stimato era 8.55 ore (stimato elaborando 800k su 80M)