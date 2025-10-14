#!/usr/bin/env python3
import argparse
import sys
import math
import osmnx as ox
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

def parse_args():
    p = argparse.ArgumentParser(description="Plot attorno a Piazza Maggiore con frecce e pesi interi.")
    p.add_argument("--graph", required=True, help="Percorso al file GraphML (es. bologna_graph_NEW.graphml)")
    p.add_argument("--dist", type=float, default=400.0, help="Raggio (metri) attorno a Piazza Maggiore (default: 400)")
    p.add_argument("--out", type=str, default="piazza_maggiore_weights2.png", help="PNG di output")
    p.add_argument("--weight-key", type=str, default="weight", help="Nome attributo da usare come peso (default: 'weight')")
    p.add_argument("--max-labels", type=int, default=250, help="Massimo numero di etichette da disegnare (default: 250)")
    p.add_argument("--arrow-scale", type=float, default=10.0, help="Scala della freccia (default: 10)")
    p.add_argument("--alpha-edges", type=float, default=0.9, help="Trasparenza delle linee degli archi (default: 0.9)")
    p.add_argument("--debug-miss", action="store_true", help="Stampa perché salta le etichette (debug)")
    return p.parse_args()

def load_graph_robust(path: str):
    return ox.load_graphml(
        path,
        edge_dtypes={
            "oneway": str, "bridge": str, "tunnel": str, "roundabout": str, "junction": str,
        }
    )

def arrow_on_segment(ax, x0, y0, x1, y1, mutation_scale=10.0, alpha=0.9):
    arr = FancyArrowPatch((x0, y0), (x1, y1),
                          arrowstyle='-|>', mutation_scale=mutation_scale,
                          linewidth=0.8, alpha=alpha, color="#222222")
    ax.add_patch(arr)

def mid_point(xs, ys):
    if not xs or not ys: return None
    i = len(xs)//2
    return xs[i], ys[i]

def dir_points(xs, ys):
    if len(xs) >= 2 and len(ys) >= 2:
        return xs[-2], ys[-2], xs[-1], ys[-1]
    return None

def coerce_number(val):
    """Tenta float(val). Restituisce float oppure None."""
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).strip())
    except Exception:
        return None

def pick_weight(data, primary_key):
    """Restituisce un numero (float) cercando in più chiavi note."""
    candidates = [primary_key, "EstimatedTime_s", "time_s", "length"]
    for k in candidates:
        if k in data:
            num = coerce_number(data[k])
            if num is not None:
                return num, k
    return None, None

def main():
    args = parse_args()
    center = (44.4938, 11.3431)  # Piazza Maggiore

    try:
        G = load_graph_robust(args.graph)
    except Exception as e:
        print(f"[errore] Impossibile caricare '{args.graph}': {e}", file=sys.stderr)
        sys.exit(2)

    bbox = ox.utils_geo.bbox_from_point(center, dist=args.dist)
    try:
        sub = ox.truncate.truncate_graph_bbox(G, bbox=bbox)
    except TypeError:
        n, s, e, w = bbox
        sub = ox.truncate.truncate_graph_bbox(G, n, s, e, w)

    if sub.number_of_edges() == 0:
        print("[attenzione] Nessun arco nella bbox. Aumenta --dist.", file=sys.stderr)

    fig, ax = ox.plot_graph(
        sub, node_size=2, edge_linewidth=0.6, bgcolor="white",
        show=False, close=False, edge_color="#555555", node_color="#111111",
        edge_alpha=args.alpha_edges
    )
    
    # --- Aggiungi marker rosso per Piazza Maggiore ---
    piazza_lat, piazza_lon = 44.4938, 11.3431  # coordinate
    ax.scatter(
        piazza_lon, piazza_lat,               # lon = x, lat = y
        s=90,                                # dimensione media
        c="red", marker="o", edgecolors="black", linewidths=0.4, zorder=5,
        label="Piazza Maggiore"
    )

    # Aggiungi piccola legenda in basso a destra
    ax.legend(loc="lower right", fontsize=8)
    # -----------------------------------------------


    labels_drawn = 0
    fontsize = 6 #max(4, int(8 - math.log10(max(100.0, args.dist))))
    debug_skips = 0

    for u, v, k, data in sub.edges(keys=True, data=True):
        geom = data.get("geometry")
        if geom is not None and hasattr(geom, "coords"):
            xs = [p[0] for p in geom.coords]; ys = [p[1] for p in geom.coords]
        else:
            ux, uy = sub.nodes[u].get("x"), sub.nodes[u].get("y")
            vx, vy = sub.nodes[v].get("x"), sub.nodes[v].get("y")
            if None in (ux, uy, vx, vy): 
                continue
            xs, ys = [ux, vx], [uy, vy]

        # freccia (u->v)
        dp = dir_points(xs, ys)
        if dp is not None:
            x0, y0, x1, y1 = dp
            arrow_on_segment(ax, x0, y0, x1, y1, mutation_scale=args.arrow_scale, alpha=0.9)

        # etichetta peso
        if labels_drawn < args.max_labels:
            w, used_key = pick_weight(data, args.weight_key)
            if w is not None and 70 <= w <= 72:
                print(f"DEBUG: trovato peso 71 su arco {u}->{v} (key usata: {used_key})")
            if w is not None:
                mp = mid_point(xs, ys)
                if mp:
                    mx, my = mp
                    ax.text(mx, my, f"{int(round(w))}", fontsize=fontsize, alpha=0.7,
                            ha="center", va="center", color="#333333")
                    labels_drawn += 1
            elif args.debug_miss:
                debug_skips += 1

    ax.set_title(
        f"Grafo attorno a Piazza Maggiore — {int(args.dist)} m\n"
        f"Frecce direzione u→v  |  Etichette: interi (max {args.max_labels})",
        fontsize=9
    )

    fig.savefig(args.out, dpi=240, bbox_inches="tight")
    plt.close(fig)

    print(f"[ok] Salvato: {args.out}")
    print(f"     Nodi: {sub.number_of_nodes():,} | Archi: {sub.number_of_edges():,}")
    print(f"     Etichette disegnate: {labels_drawn}")
    if args.debug_miss:
        print(f"     Archi senza etichetta (peso mancante/non numerico): {debug_skips}")
    print(f"     Centro: lat={center[0]:.6f}, lon={center[1]:.6f} | Raggio: {args.dist} m")

if __name__ == "__main__":
    main()
