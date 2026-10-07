"""Offline state lookup from coordinates.

Reuses the same bundled US state boundary data the map already draws from
(assets/us-states.json) and the shapely dependency the map projection
already requires - no new dependencies, no network access, no API key. This
project has a standing rule against network/API-key-gated services (see
docs/HISTORY.md's basemap section for why) and this keeps that rule intact.

Deliberately resolves STATE only, not city. "Which state contains this
point" is an objective geometric fact; "what's the nearest named place" is
not - the nearest incorporated town to a rural RV park is often not what
anyone would call that stop, and attempting it would mean either bundling a
places database or guessing. merge.resolve_city_state() falls back to the
stop's own Location/Stop Name text for city instead of inventing one.
"""
from __future__ import annotations

import json
import os

from shapely.geometry import Point, shape

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")

STATE_ABBREV = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Puerto Rico": "PR", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}

_state_polys: list | None = None


def _load():
    global _state_polys
    if _state_polys is None:
        data = json.load(open(os.path.join(ASSETS, "us-states.json"), encoding="utf-8"))
        _state_polys = [
            (STATE_ABBREV.get(f["properties"]["name"], f["properties"]["name"]), shape(f["geometry"]))
            for f in data["features"]
        ]
    return _state_polys


def state_from_point(lat: float | None, lon: float | None) -> str | None:
    if lat is None or lon is None:
        return None
    pt = Point(lon, lat)
    for abbrev, poly in _load():
        if poly.contains(pt):
            return abbrev
    return None
