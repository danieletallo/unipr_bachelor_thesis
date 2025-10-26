# analyze_temporal_paths.py
# (1) Daily count on fixed axis Apr'17 → Oct'17 with ticks at mid-month
# (2) Distribution by hour: weekday vs weekend

import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

START_AXIS = pd.Timestamp("2017-04-01")
END_AXIS   = pd.Timestamp("2017-10-01")
CUTOFF     = pd.Timestamp("2017-10-01 23:59:59")  # include everything up to 1/10/2017

# --- add at the top of the file (after constants) ---
def italian_holidays_2017():
    """Returns {Timestamp->name} for major national holidays Apr–Oct 2017."""
    h = {
        pd.Timestamp("2017-04-16"): "Easter",
        pd.Timestamp("2017-04-17"): "Easter Monday",
        pd.Timestamp("2017-04-25"): "Liberation Day",
        pd.Timestamp("2017-05-01"): "Labor Day",
        pd.Timestamp("2017-06-02"): "Republic Day",
        pd.Timestamp("2017-08-15"): "Assumption Day",
    }
    # keep only those within the axis range
    return {d.normalize(): name for d, name in h.items() if START_AXIS <= d <= END_AXIS}


def load_starts(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, usecols=["ActivityId", "TimeFrom"])
    df["TimeFrom"] = pd.to_datetime(df["TimeFrom"], errors="coerce")
    df = df.dropna(subset=["TimeFrom"])
    df = df[df["TimeFrom"] <= CUTOFF]

    # only one start timestamp per activity
    starts = (
        df.groupby("ActivityId", as_index=False)["TimeFrom"]
          .min()
          .rename(columns={"TimeFrom": "Start"})
    )
    return starts

# --- replace your plot_daily_distribution with this ---
def plot_daily_distribution(outdir: Path, starts: pd.DataFrame):
    # daily count (normalized) + reindex on all days to show zeros as well
    daily = (
        starts["Start"].dt.normalize()
        .value_counts()
        .sort_index()
        .rename("count")
    )

    if daily.empty:
        print("No data after date filter. Skipping daily chart.")
        return

    full_days = pd.date_range(START_AXIS, END_AXIS, freq="D")
    daily = daily.reindex(full_days, fill_value=0)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(daily.index, daily.values, "-o", ms=2, lw=0.9, label="Daily count")

    # ax.set_title("Daily Activity Count (Apr–Oct 2017)", pad=10)
    ax.set_xlabel("Month")
    ax.set_ylabel("Count")
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(True, alpha=0.25, linestyle="--", linewidth=0.6)

    # ticks at the start of each month
    months = pd.date_range(START_AXIS, END_AXIS, freq="MS")
    ax.set_xticks(months)
    ax.set_xticklabels([d.strftime("%b") for d in months])
    ax.set_xlim(START_AXIS, END_AXIS)

    # --- highlight holidays with "*" ---
    holidays = italian_holidays_2017()
    holi_idx = [d for d in daily.index if d in holidays]
    holi_vals = [daily.loc[d] for d in holi_idx]

    if holi_idx:
        ax.scatter(
            holi_idx, holi_vals,
            marker="*", s=130, edgecolor="k", linewidths=0.6,
            zorder=3, label="Holidays"
        )

    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "daily_count.png", dpi=220)
    plt.close(fig)

def plot_hourly(outdir: Path, starts: pd.DataFrame):
    if starts.empty:
        print("No data after date filter. Skipping hourly chart.")
        return

    s = starts.copy()
    s["Hour"] = s["Start"].dt.hour
    s["IsWeekend"] = s["Start"].dt.weekday >= 5

    # Calculate the number of weekdays and weekends in the dataset
    num_weekdays = s[~s['IsWeekend']]['Start'].dt.normalize().nunique()
    num_weekends = s[s['IsWeekend']]['Start'].dt.normalize().nunique()

    # Ensure all 24 hours are present
    hours = pd.Index(range(24), name="Hour")
    hourly = (
        s.groupby(["Hour", "IsWeekend"])
         .size()
         .unstack(fill_value=0)
         .rename(columns={False: "Weekday", True: "Weekend"})
         .reindex(hours, fill_value=0)
    )

    # Convert totals to averages
    hourly["Weekday"] = hourly["Weekday"] / num_weekdays
    hourly["Weekend"] = hourly["Weekend"] / num_weekends

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(hourly.index, hourly["Weekday"], "-o", label="Weekday")
    ax.plot(hourly.index, hourly["Weekend"], "-s", label="Weekend")

    # ax.set_title("Average Trips per Hour: Weekday vs Weekend", pad=8)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Average Number of Trips")

    # Show all ticks from 0 to 23
    ax.set_xticks(range(24))  
    ax.set_xlim(-0.5, 23.5)   # so 23 is not squished at the edge
    ax.set_ylim(bottom=0)

    ax.grid(True, alpha=0.25, linestyle="--", linewidth=0.6)
    ax.legend()

    fig.tight_layout()
    fig.savefig(outdir / "hourly_weekday_vs_weekend.png", dpi=200)
    plt.close(fig)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", default="segments_all_activities.csv", help="CSV input")
    ap.add_argument("-o", "--outdir", default=".", help="Output folder")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    starts = load_starts(args.input)
    plot_daily_distribution(outdir, starts)
    plot_hourly(outdir, starts)

    print("Saved (if data is present):")
    print(f" - {outdir/'daily_count.png'}")
    print(f" - {outdir/'hourly_weekday_vs_weekend.png'}")

if __name__ == "__main__":
    main()
