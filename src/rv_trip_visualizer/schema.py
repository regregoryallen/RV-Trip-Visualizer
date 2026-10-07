"""The column contract every source export must satisfy.

Deliberately matches TripWizard's own export headers exactly (see
docs/HISTORY.md) - any planning tool that exports the same header row works
too, since columns are located by header *name*, not position. Extra columns
are ignored; the required ones may appear in any order, in any column, on
any sheet, with any number of leading title/metadata rows above them.
"""
from __future__ import annotations

from dataclasses import dataclass

# Columns the pipeline actually reads. Missing any of these is a blocking
# integrity failure - there is no fallback or inference for a missing column.
REQUIRED_HEADERS = [
    "Stop Name",
    "Miles",
    "Total",
    "Arrival Date",
    "Nights",
    "Departure Date",
    "Location",
    "Latitude",
    "Longitude",
]

# How many rows (from the top of a sheet) to search for a header row before
# giving up on that sheet. Generous, since some export formats carry several
# title/metadata rows above the real header (TripWizard uses 3).
HEADER_SEARCH_ROWS = 20


def _norm(s) -> str:
    return str(s).strip().lower() if s is not None else ""


@dataclass
class HeaderMap:
    sheet_name: str
    header_row: int
    columns: dict  # required header name -> 1-based column index


def find_header_row(ws) -> tuple[int, dict] | None:
    """Scan the top of a worksheet for a row containing every required
    header. Returns (row_index, {header: col_index}) or None.
    """
    required_norm = {_norm(h): h for h in REQUIRED_HEADERS}
    max_row = min(ws.max_row, HEADER_SEARCH_ROWS)
    for r in range(1, max_row + 1):
        found = {}
        for c in range(1, ws.max_column + 1):
            v = _norm(ws.cell(r, c).value)
            if v in required_norm:
                found[required_norm[v]] = c
        if len(found) == len(REQUIRED_HEADERS):
            return r, found
    return None


def resolve_headers(wb) -> HeaderMap | None:
    """Find a sheet (preferring one literally named 'Trip Summary') with a
    header row that has every required column. Returns None if no sheet in
    the workbook qualifies.
    """
    sheet_names = list(wb.sheetnames)
    if "Trip Summary" in sheet_names:
        sheet_names.remove("Trip Summary")
        sheet_names.insert(0, "Trip Summary")
    for name in sheet_names:
        ws = wb[name]
        found = find_header_row(ws)
        if found:
            row, columns = found
            return HeaderMap(sheet_name=name, header_row=row, columns=columns)
    return None


def missing_headers(wb) -> list:
    """Best-effort diagnostic for the error message when resolve_headers()
    fails: for the sheet that came closest (most required headers present),
    report which ones are missing. Used only for a clearer integrity message.
    """
    required_norm = {_norm(h): h for h in REQUIRED_HEADERS}
    best_sheet, best_found = None, set()
    for name in wb.sheetnames:
        ws = wb[name]
        max_row = min(ws.max_row, HEADER_SEARCH_ROWS)
        for r in range(1, max_row + 1):
            found = set()
            for c in range(1, ws.max_column + 1):
                v = _norm(ws.cell(r, c).value)
                if v in required_norm:
                    found.add(required_norm[v])
            if len(found) > len(best_found):
                best_found, best_sheet = found, name
    missing = [h for h in REQUIRED_HEADERS if h not in best_found]
    return missing, best_sheet
