import osmium as osm
import folium
from folium.plugins import PolyLineTextPath

PBF_FILE = "osrm/bologna-2018.osm.pbf"

# TOP 3 PAIRS: node_src_from, node_src_to, node_dst_from, node_dst_to
TOP3 = [
    (250734660, 250734679, 280145073, 4496799435),
    (655135679, 3325048776, 3254498353, 346089939),
    (250713168, 245980471, 4449687200, 1617612971),
]

# --- read node coordinates from PBF 2018 ---
want_ids = {n for quad in TOP3 for n in quad}
class NodeGrabber(osm.SimpleHandler):
    def __init__(self, wanted):
        super().__init__()
        self.wanted = wanted
        self.coords = {}
    def node(self, n):
        if n.id in self.wanted and n.location.valid():
            self.coords[n.id] = (n.location.lat, n.location.lon)

h = NodeGrabber(want_ids)
h.apply_file(PBF_FILE, locations=True)
coords = h.coords

def midpoint(a, b):
    lat1, lon1 = coords[a]
    lat2, lon2 = coords[b]
    return ((lat1 + lat2) / 2.0, (lon1 + lon2) / 2.0)

# map center: average of source midpoints
src_mids = [midpoint(a, b) for a, b, _, _ in TOP3]
center_lat = sum(lat for lat, _ in src_mids) / len(src_mids)
center_lon = sum(lon for _, lon in src_mids) / len(src_mids)

# basemap: OSM standard
m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

for i, (s_from, s_to, d_from, d_to) in enumerate(TOP3, start=1):
    src_mid = midpoint(s_from, s_to)
    dst_mid = midpoint(d_from, d_to)

    # source/destination circles
    folium.CircleMarker(src_mid, radius=9, color="green", fill=True, fill_opacity=0.7,
                        tooltip=f"#{i} SRC {s_from}→{s_to}").add_to(m)
    folium.CircleMarker(dst_mid, radius=9, color="red", fill=True, fill_opacity=0.7,
                        tooltip=f"#{i} DST {d_from}→{d_to}").add_to(m)

    # arrow from source midpoint to destination midpoint
    line = folium.PolyLine([src_mid, dst_mid], weight=3, opacity=0.9).add_to(m)

m.save("top3_pairs.html")
print("Map saved: top3_pairs.html")
