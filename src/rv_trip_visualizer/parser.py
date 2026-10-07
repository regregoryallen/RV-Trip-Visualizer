"""Per-file extraction of stops from a source export.

Pure extraction - this module never invents or corrects a value. Where a
value can't be read (a required column missing, a date that's neither
present nor inferable, a non-numeric Nights cell), the row carries `None`
and/or an entry in `ParsedFile.row_issues`, for integrity.py to turn into a
blocking finding. Two things it *does* legitimately infer, because they're
TripWizard's own documented export conventions rather than guesses about bad
data (see docs/HISTORY.md):

- A blank per-row Arrival/Departure date, reconstructed by walking forward
  from the file's own "Start Date:" label using each row's Nights count.
- Row order is not trusted; stops are sorted by Arrival Date, since at least
  one real-world export has been seen with rows in scrambled order.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import openpyxl

from . import schema


class SchemaError(Exception):
    """Raised when no sheet in the workbook has every required header."""

    def __init__(self, path: str, missing: list, closest_sheet: str | None):
        self.path = path
        self.missing = missing
        self.closest_sheet = closest_sheet
        super().__init__(
            f"{os.path.basename(path)}: missing required column(s): "
            + ", ".join(missing)
        )


@dataclass
class ParsedFile:
    path: str
    stops: list = field(default_factory=list)
    miles_sum: float = 0.0
    total_col_last: float | None = None

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


_START_DATE_RE = re.compile(r"Start Date:\s*\w+,\s*(.+)")


def _find_start_label(ws, header_row: int) -> date | None:
    """TripWizard carries a 'Start Date: <Weekday>, <Month> <day>, <year>'
    label somewhere above the header row. Searched for, rather than assumed
    to be a fixed cell, so a tool that places its equivalent label elsewhere
    (or omits it) doesn't break the rest of the parse - it just means dates
    can't be inferred for that file, which shows up as a missing-date finding
    if any row actually needs the inference.
    """
    for r in range(1, header_row):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if not v:
                continue
            m = _START_DATE_RE.search(str(v))
            if m:
                try:
                    return datetime.strptime(m.group(1).strip(), "%B %d, %Y").date()
                except ValueError:
                    continue
    return None


def parse_file(path: str) -> ParsedFile:
    wb = openpyxl.load_workbook(path, data_only=True)
    hm = schema.resolve_headers(wb)
    if hm is None:
        missing, closest_sheet = schema.missing_headers(wb)
        raise SchemaError(path, missing, closest_sheet)

    ws = wb[hm.sheet_name]
    col = hm.columns
    cursor = _find_start_label(ws, hm.header_row)
    filename = os.path.basename(path)

    stops = []
    r = hm.header_row + 1
    while True:
        name = ws.cell(r, col["Stop Name"]).value
        nights_raw = ws.cell(r, col["Nights"]).value
        if name is None and nights_raw is None:
            break

        if nights_raw is None:
            nights = 0  # TripWizard's own convention for an unset Nights cell
        else:
            try:
                nights = int(nights_raw)
            except (TypeError, ValueError):
                nights = None  # non-numeric - a real problem, not inferred

        arr = _parse_date(ws.cell(r, col["Arrival Date"]).value)
        arrival_inferred = False
        if arr is None and cursor is not None:
            arr = cursor
            arrival_inferred = True

        dep = _parse_date(ws.cell(r, col["Departure Date"]).value)
        departure_inferred = False
        if dep is None and arr is not None and nights is not None:
            dep = arr + timedelta(days=nights)
            departure_inferred = True

        lat_v = ws.cell(r, col["Latitude"]).value
        lon_v = ws.cell(r, col["Longitude"]).value
        miles_v = ws.cell(r, col["Miles"]).value

        stops.append({
            "source_file": filename,
            "row": r,
            "stop_name": (name or "").strip(),
            "location": (ws.cell(r, col["Location"]).value or "").strip(),
            "nights": nights,
            "nights_raw": nights_raw,
            "arrival": arr,
            "departure": dep,
            "arrival_inferred": arrival_inferred,
            "departure_inferred": departure_inferred,
            "lat": float(lat_v) if isinstance(lat_v, (int, float)) else None,
            "lon": float(lon_v) if isinstance(lon_v, (int, float)) else None,
            "miles": float(miles_v) if isinstance(miles_v, (int, float)) else 0.0,
        })
        cursor = dep if dep is not None else cursor
        r += 1

    stops.sort(key=lambda s: (s["arrival"] is None, s["arrival"] or date.max, s["row"]))

    total_col_last = None
    for r2 in range(hm.header_row + 1, r):
        v = ws.cell(r2, col["Total"]).value
        if isinstance(v, (int, float)):
            total_col_last = v
    miles_sum = sum(s["miles"] for s in stops)

    return ParsedFile(path=path, stops=stops, miles_sum=miles_sum, total_col_last=total_col_last)
