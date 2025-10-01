# analyze_temporal_paths.py
# (1) Daily count su asse forzato Apr'17 → Ott'17 con tick a metà mese
# (2) Distribuzione per ora: weekday vs weekend

import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

START_AXIS = pd.Timestamp("2017-04-01")
END_AXIS   = pd.Timestamp("2017-10-01")
CUTOFF     = pd.Timestamp("2017-10-01 23:59:59")  # includi tutto fino al 1/10/2017

# --- aggiungi in cima al file (dopo le costanti) ---
def italian_holidays_2017():
    """Ritorna {Timestamp->nome} per le principali festività nazionali Apr–Ott 2017."""
    h = {
        pd.Timestamp("2017-04-16"): "Pasqua",
        pd.Timestamp("2017-04-17"): "Pasquetta",
        pd.Timestamp("2017-04-25"): "Liberazione",
        pd.Timestamp("2017-05-01"): "Lavoro",
        pd.Timestamp("2017-06-02"): "Repubblica",
        pd.Timestamp("2017-08-15"): "Ferragosto",
    }
    # tieni solo quelle nel range asse
    return {d.normalize(): name for d, name in h.items() if START_AXIS <= d <= END_AXIS}


def load_starts(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, usecols=["ActivityId", "TimeFrom"])
    df["TimeFrom"] = pd.to_datetime(df["TimeFrom"], errors="coerce")
    df = df.dropna(subset=["TimeFrom"])
    df = df[df["TimeFrom"] <= CUTOFF]

    # un solo timestamp di inizio per attività
    starts = (
        df.groupby("ActivityId", as_index=False)["TimeFrom"]
          .min()
          .rename(columns={"TimeFrom": "Start"})
    )
    return starts

# --- sostituisci la tua plot_daily_distribution con questa ---
def plot_daily_distribution(outdir: Path, starts: pd.DataFrame):
    # conteggio per giorno (normalizzato) + reindex su tutti i giorni per mostrare anche gli zeri
    daily = (
        starts["Start"].dt.normalize()
        .value_counts()
        .sort_index()
        .rename("count")
    )

    if daily.empty:
        print("Nessun dato dopo il filtro date. Salto il grafico giornaliero.")
        return

    full_days = pd.date_range(START_AXIS, END_AXIS, freq="D")
    daily = daily.reindex(full_days, fill_value=0)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(daily.index, daily.values, "-o", ms=2, lw=0.9, label="Daily count")

    ax.set_title("Daily Activity Count (Apr–Oct 2017)", pad=10)
    ax.set_xlabel("Month")
    ax.set_ylabel("Count")
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(True, alpha=0.25, linestyle="--", linewidth=0.6)

    # ticks a inizio mese
    months = pd.date_range(START_AXIS, END_AXIS, freq="MS")
    ax.set_xticks(months)
    ax.set_xticklabels([d.strftime("%b") for d in months])
    ax.set_xlim(START_AXIS, END_AXIS)

    # --- evidenzia festività con "*" ---
    holidays = italian_holidays_2017()
    holi_idx = [d for d in daily.index if d in holidays]
    holi_vals = [daily.loc[d] for d in holi_idx]

    if holi_idx:
        ax.scatter(
            holi_idx, holi_vals,
            marker="*", s=130, edgecolor="k", linewidths=0.6,
            zorder=3, label="Festività"
        )

    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "daily_count.png", dpi=220)
    plt.close(fig)



def plot_hourly(outdir: Path, starts: pd.DataFrame):
    if starts.empty:
        print("Nessun dato dopo il filtro date. Salto il grafico orario.")
        return

    s = starts.copy()
    s["Hour"] = s["Start"].dt.hour
    s["IsWeekend"] = s["Start"].dt.weekday >= 5

    # Ensure all 24 hours are present
    hours = pd.Index(range(24), name="Hour")
    hourly = (
        s.groupby(["Hour", "IsWeekend"])
         .size()
         .unstack(fill_value=0)
         .rename(columns={False: "Weekday", True: "Weekend"})
         .reindex(hours, fill_value=0)
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(hourly.index, hourly["Weekday"], "-o", label="Weekday")
    ax.plot(hourly.index, hourly["Weekend"], "-s", label="Weekend")

    ax.set_title("Trips per Hour: Weekday vs Weekend", pad=8)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Number of Trips")

    # Mostra tutti i tick da 0 a 23
    ax.set_xticks(range(24))  
    ax.set_xlim(-0.5, 23.5)   # così il 23 non resta schiacciato al bordo
    ax.set_ylim(bottom=0)

    ax.grid(True, alpha=0.25, linestyle="--", linewidth=0.6)
    ax.legend()

    fig.tight_layout()
    fig.savefig(outdir / "hourly_weekday_vs_weekend.png", dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", default="segments_all_activities.csv", help="CSV input")
    ap.add_argument("-o", "--outdir", default=".", help="Cartella output")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    starts = load_starts(args.input)
    plot_daily_distribution(outdir, starts)
    plot_hourly(outdir, starts)

    print("Salvati (se presenti dati):")
    print(f" - {outdir/'daily_count.png'}")
    print(f" - {outdir/'hourly_weekday_vs_weekend.png'}")

if __name__ == "__main__":
    main()
