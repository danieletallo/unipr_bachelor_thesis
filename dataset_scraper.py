import os
import glob
import pandas as pd
import folium

# Imposta la cartella corrente
cartella = os.getcwd()

# Trova tutti i file CSV nella cartella
csv_files = glob.glob(os.path.join(cartella, "*.csv"))

# Lista per salvare tutte le righe ciclabili
dati_cycle = []

# Contatore del numero totale di righe trovate
total_rows = 0

# Legge e filtra ogni file CSV
for file in csv_files:
    try:
        print(f"Elaborando il file: {file}")
        df = pd.read_csv(file)

        if "ActivityType" in df.columns:
            df = df[df["ActivityType"] == "Cycle"]

            if not df.empty:
                df["source_file"] = os.path.basename(file)
                dati_cycle.append(df)
                total_rows += len(df)
                print(f"Trovate {len(df)} righe 'Cycle' in questo file")

    except Exception as e:
        print(f"Errore nel file {file}: {e}")

# Verifica se ci sono righe ciclabili
if not dati_cycle:
    print("Nessuna attività 'Cycle' trovata.")
    exit()

# Unisci tutti i dati filtrati in un unico DataFrame
df_cycle = pd.concat(dati_cycle, ignore_index=True)

# Rimuove righe senza coordinate valide
df_cycle = df_cycle.dropna(subset=["Latitude", "Longitude"])

# Salva su file
df_cycle.to_csv("cycle.csv", index=False)
print("Dati salvati nel file 'cycle.csv'.")

# Mostra riepilogo finale
print(f"Totale righe ciclabili trovate: {len(df_cycle)}")
print(f"Totale attività distinte trovate: {df_cycle['ActivityId'].nunique()}")

# Visualizza su mappa un'attività di esempio
# Prendi il primo ActivityId disponibile
activity_id = df_cycle["ActivityId"].iloc[0]
example_track = df_cycle[df_cycle["ActivityId"] == activity_id].copy()

# Ordina per tempo se possibile
if "Time" in example_track.columns:
    example_track["Time"] = pd.to_datetime(example_track["Time"], errors='coerce')
    example_track = example_track.sort_values(by="Time")

# Centra la mappa sul primo punto
start_coords = [example_track["Latitude"].iloc[0], example_track["Longitude"].iloc[0]]
m = folium.Map(location=start_coords, zoom_start=15)

# Aggiungi linea del percorso
folium.PolyLine(
    locations=list(zip(example_track["Latitude"], example_track["Longitude"])),
    color="blue",
    weight=4,
    opacity=0.7
).add_to(m)

# Aggiungi marker per inizio e fine
folium.Marker(
    location=[example_track["Latitude"].iloc[0], example_track["Longitude"].iloc[0]],
    popup="Inizio",
    icon=folium.Icon(color="green")
).add_to(m)

folium.Marker(
    location=[example_track["Latitude"].iloc[-1], example_track["Longitude"].iloc[-1]],
    popup="Fine",
    icon=folium.Icon(color="red")
).add_to(m)

# Salva la mappa
m.save("mappa_attivita_esempio.html")
print(f"Mappa generata per l'attività {activity_id} in 'mappa_attivita_esempio.html'")
