import os
import glob
import pandas as pd

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
