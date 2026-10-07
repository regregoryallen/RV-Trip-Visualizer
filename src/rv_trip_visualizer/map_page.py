"""Projects a merged stay list onto an Albers-USA basemap and bakes the
result into a self-contained HTML file.

assets/us-states.json / assets/mexico.json are cached public-domain boundary
data (US Census TIGER derivative / world.geo.json) so this never needs
network access to build. assets/map_shell.html is the editable page template
(styling + the dual SVG/Leaflet basemap logic) - this module only swaps in
the data and title.
"""
from __future__ import annotations

import html
import json
import math
import os

from shapely.geometry import box, mapping, shape
from shapely.ops import transform as shp_transform

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
SHELL_PATH = os.path.join(ASSETS, "map_shell.html")

# Standard "Albers USA" conic equal-area parameters (D3's d3.geoAlbers defaults).
PHI1, PHI2, LAMBDA0, PHI0 = (math.radians(x) for x in (29.5, 45.5, -96, 37.5))
N = (math.sin(PHI1) + math.sin(PHI2)) / 2
C = math.cos(PHI1) ** 2 + 2 * N * math.sin(PHI1)
RHO0 = math.sqrt(C - 2 * N * math.sin(PHI0)) / N

EXCLUDE_STATES = {"Alaska", "Hawaii", "Puerto Rico"}


def _project(lon, lat):
    lam, phi = math.radians(lon), math.radians(lat)
    rho = math.sqrt(C - 2 * N * math.sin(phi)) / N
    theta = N * (lam - LAMBDA0)
    return (rho * math.sin(theta), -(RHO0 - rho * math.cos(theta)))  # flip y: north = up


def _project_geom(geom):
    return shp_transform(lambda x, y, z=None: _project(x, y), geom)


def render(stays: list[dict], out_path: str, title: str) -> None:
    states = json.load(open(os.path.join(ASSETS, "us-states.json")))
    state_paths = []
    state_geojson_features = []  # unprojected (raw lon/lat) - for the Leaflet overlay
    for f in states["features"]:
        name = f["properties"]["name"]
        if name in EXCLUDE_STATES:
            continue
        simplified = shape(f["geometry"]).simplify(0.02, preserve_topology=True)
        state_paths.append((name, _project_geom(simplified)))
        state_geojson_features.append({
            "type": "Feature", "properties": {"name": name},
            "geometry": mapping(simplified),
        })

    mexico = json.load(open(os.path.join(ASSETS, "mexico.json")))
    mgeom = shape(mexico["features"][0]["geometry"])
    mgeom = mgeom.intersection(box(-118, 22, -97, 33))  # just the northern border region
    mproj = _project_geom(mgeom.simplify(0.02, preserve_topology=True))

    pts = [(s, _project(s["lon"], s["lat"])) for s in stays]

    xs, ys = [], []
    for _, g in state_paths:
        b = g.bounds
        xs += [b[0], b[2]]
        ys += [b[1], b[3]]
    b = mproj.bounds
    xs += [b[0], b[2]]
    ys += [b[1], b[3]]
    for _, (x, y) in pts:
        xs.append(x)
        ys.append(y)
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)

    SCALE, PAD = 1500, 40
    tx = lambda x: (x - minx) * SCALE + PAD
    ty = lambda y: (y - miny) * SCALE + PAD
    vb_w = (maxx - minx) * SCALE + 2 * PAD
    vb_h = (maxy - miny) * SCALE + 2 * PAD

    def to_svg_path(geom):
        polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        d = []
        for poly in polys:
            for ring in [poly.exterior] + list(poly.interiors):
                coords = list(ring.coords)
                if coords:
                    d.append("M" + " L".join(f"{tx(x):.2f},{ty(y):.2f}" for x, y in coords) + "Z")
        return " ".join(d)

    data = {
        "viewbox": [0, 0, round(vb_w, 1), round(vb_h, 1)],
        "states": [{"name": n, "d": to_svg_path(g)} for n, g in state_paths],
        "mexico_d": to_svg_path(mproj),
        "states_geojson": {"type": "FeatureCollection", "features": state_geojson_features},
        "points": [
            {
                "x": round(tx(x), 2), "y": round(ty(y), 2),
                "lat": s["lat"], "lon": s["lon"],
                "city": s["city"], "state": s["state"], "nights": s["nights"],
                "arrival": str(s["arrival"]), "departure": str(s["departure"]), "miles": s["miles"],
            }
            for s, (x, y) in pts
        ],
    }

    shell = open(SHELL_PATH).read()
    out_html = (
        shell
        .replace("<!--TITLE-->", html.escape(title))
        .replace("/*__DATA__*/", json.dumps(data, separators=(",", ":")))
    )
    with open(out_path, "w") as f:
        f.write(out_html)
