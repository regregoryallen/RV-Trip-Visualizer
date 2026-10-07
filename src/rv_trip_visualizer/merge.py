"""Merging multiple export files into one chronological stay list.

Everything here is general algorithmic handling of how RV trip planners
export overlapping, re-planned trips - not a correction of bad data, and not
configurable per-user. See docs/HISTORY.md for the reasoning behind each
piece, especially the mileage-rescue fix.
"""
from __future__ import annotations

import re
from datetime import date

STATES = set(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN "
    "MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA "
    "WA WV WI WY DC".split()
)


def resolve_overlaps(parsed_files) -> tuple[list, list]:
    """Later export wins for any date range it re-covers (the plan changed
    mid-trip and was re-exported). Returns (resolved_stops_sorted, log_lines).

    Carries the mileage-rescue fix: TripWizard always records a new export's
    first stop as "current location", Miles=0 (no travel logged yet in that
    file). If the stop being dropped from the earlier file shares the exact
    same Location text as the new file's first stop, the real mileage to
    reach that physical place only exists on the side being discarded -
    rescue it onto the survivor rather than silently losing it.
    """
    units = [(pf.stops[0]["arrival"], pf.stops) for pf in parsed_files if pf.stops]
    units.sort(key=lambda u: (u[0] is None, u[0] or date.max))

    log = []
    master = []
    for start, stops in units:
        new_master = []
        for s in master:
            if start is not None and s["arrival"] is not None and s["arrival"] >= start:
                first = stops[0]
                same_place = bool(
                    s["location"] and first["location"]
                    and s["location"].strip() == first["location"].strip()
                )
                if same_place and first["miles"] == 0 and s["miles"] > 0:
                    log.append(
                        f"rescued {s['miles']:.0f} mi for '{s['location']}' from "
                        f"{s['source_file']} (dropped, superseded by {stops[0]['source_file']})"
                    )
                    first["miles"] = s["miles"]
                elif s["miles"] > 0 and not same_place:
                    log.append(
                        f"discarded {s['miles']:.0f} mi for '{s['stop_name'][:40]}' "
                        f"from {s['source_file']} (superseded by {stops[0]['source_file']}, plan changed)"
                    )
                continue
            elif start is not None and s["departure"] is not None and s["departure"] > start:
                s = dict(s)
                s["departure"] = start
                if s["arrival"] is not None:
                    s["nights"] = (start - s["arrival"]).days
                new_master.append(s)
            else:
                new_master.append(s)
        master = new_master + list(stops)

    master.sort(key=lambda s: (
        s["arrival"] is None, s["arrival"] or date.max,
        s["departure"] is None, s["departure"] or date.max,
    ))
    return master, log


def fold_waypoint_mileage(stops: list) -> tuple[list, list]:
    """0-night waypoint stops (gas, lunch, quick errands) don't appear in the
    itinerary, but the distance TripWizard recorded to reach them is real -
    fold it forward onto the next real (>=1 night) stay. Returns
    (stays_with_leg_miles, log_lines).
    """
    log = []
    pending = 0.0
    stays = []
    for s in stops:
        pending += s["miles"]
        if (s["nights"] or 0) >= 1:
            stay = dict(s)
            stay["leg_miles"] = pending
            stays.append(stay)
            pending = 0.0
    if pending > 0.5:
        log.append(
            f"{pending:.1f} miles of trailing 0-night waypoint(s) at the end of "
            "the record were never folded into a stay (nothing came after them)"
        )
    return stays, log


def extract_city_state(stop_name: str, location: str) -> tuple[str | None, str | None]:
    """Pull a 'City, ST' pair out of free-text Location/Stop Name. Pure text
    parsing - if neither field contains a recognizable pair, returns
    (None, None) rather than guessing; the caller treats that as something
    the user needs to fix in the source planner.
    """
    for src in (location, stop_name):
        src = (src or "").strip()
        m = re.match(r"^([A-Za-z][A-Za-z.'\- ]*?),\s*([A-Z]{2})(?:\s*\(.*\))?$", src)
        if m and m.group(2) in STATES:
            return m.group(1).strip(), m.group(2)
    for src in (location, stop_name):
        parts = [p.strip() for p in (src or "").split(",")]
        for i in range(len(parts) - 1):
            city, statetok = parts[i], parts[i + 1]
            msm = re.match(r"^([A-Z]{2})\b", statetok)
            if msm and msm.group(1) in STATES and city and not re.search(r"\d", city) and len(city.split()) <= 4:
                return city, msm.group(1)
    loc = (location or "").strip()
    if loc in STATES:
        return None, loc
    return None, None


def merge_same_location(stays: list) -> list:
    """Two stays at the same resolved city/state with no gap between them
    (a stay split across two export files) collapse into one line."""
    def norm(s):
        return (s.get("city") or "").strip().lower(), (s.get("state") or "").strip().lower()

    stays = sorted(stays, key=lambda s: (s["arrival"], s["departure"]))
    merged = []
    for s in stays:
        if merged and norm(merged[-1]) == norm(s) and merged[-1]["departure"] == s["arrival"]:
            merged[-1]["departure"] = s["departure"]
            merged[-1]["nights"] += s["nights"]
            merged[-1]["leg_miles"] += s["leg_miles"]
            continue
        merged.append(dict(s))
    return merged
