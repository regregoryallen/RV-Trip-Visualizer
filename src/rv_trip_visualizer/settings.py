"""Persistent UI settings - last-used files/folders/titles, remembered
across runs. Stdlib only, deliberately: this module ends up inside a
PyInstaller executable on both Windows and Linux, and a config-dir
dependency isn't worth adding for something this small.
"""
from __future__ import annotations

import json
import os

APP_NAME = "RVTripVisualizer"

DEFAULTS = {
    "selected_files": [],
    "last_browse_dir": "",
    "output_dir": "",
    "base_name": "RV-Trip",
    "itinerary_title": "The Itinerary",
    "map_title": "Everywhere We've Stayed",
}


def _config_path() -> str:
    if os.name == "nt":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, APP_NAME, "settings.json")
    root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(root, "rv-trip-visualizer", "settings.json")


def load() -> dict:
    path = _config_path()
    data = dict(DEFAULTS)
    try:
        with open(path) as f:
            saved = json.load(f)
        data.update({k: v for k, v in saved.items() if k in DEFAULTS})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    # Drop any remembered file that no longer exists rather than surfacing
    # a confusing "selected" file the picker can't find.
    data["selected_files"] = [p for p in data["selected_files"] if os.path.isfile(p)]
    return data


def save(data: dict) -> None:
    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    to_save = {k: data.get(k, DEFAULTS[k]) for k in DEFAULTS}
    with open(path, "w") as f:
        json.dump(to_save, f, indent=1)
