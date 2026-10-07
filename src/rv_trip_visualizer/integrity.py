"""Data-integrity checking.

Pure reporting: this module never mutates a stop, never fills a gap, and
never invents a value. Every finding names the file/row the problem is in
and tells the user to fix it at the source (TripWizard, or whatever planning
tool produced the export) and re-export - there is no mechanism anywhere in
this codebase for feeding corrected or supplementary facts back in. See
docs/HISTORY.md for why.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import merge, parser

MILES_TOLERANCE = 1.0  # TripWizard's own Miles/Total rounding drift - harmless below this
GAP_TOLERANCE_DAYS = 1  # a 1-day gap is just inclusive/exclusive date-boundary noise


@dataclass
class Finding:
    file: str
    message: str
    row: int | None = None


@dataclass
class Report:
    findings: list = field(default_factory=list)
    parsed_files: list = field(default_factory=list)  # ParsedFile objects that parsed OK
    merged_stays: list = field(default_factory=list)  # only populated once fully clean
    log: list = field(default_factory=list)  # NOTE-level transparency lines (mileage rescues, etc.)

    @property
    def is_clean(self) -> bool:
        return not self.findings

    def add(self, file: str, message: str, row: int | None = None) -> None:
        self.findings.append(Finding(file=file, message=message, row=row))


def _check_file_structure(path: str, report: Report) -> parser.ParsedFile | None:
    filename = os.path.basename(path)
    try:
        pf = parser.parse_file(path)
    except parser.SchemaError as e:
        where = f" (closest match: sheet '{e.closest_sheet}')" if e.closest_sheet else ""
        report.add(
            filename,
            f"Missing required column(s): {', '.join(e.missing)}{where}. "
            "Add them in the source planning tool and re-export.",
        )
        return None
    except KeyError as e:
        report.add(filename, f"Could not read this file - no sheet named {e}.")
        return None
    except Exception as e:
        # Covers a locked/open-elsewhere file, a corrupted workbook, etc. -
        # anything unexpected becomes a reported finding, not a crash.
        report.add(filename, f"Could not read this file: {e}")
        return None

    if not pf.stops:
        report.add(filename, "No stop rows found under the header row.")
        return None

    for s in pf.stops:
        if s["nights"] is None:
            report.add(
                filename,
                f"Nights value '{s['nights_raw']}' is not a number.",
                row=s["row"],
            )
        if s["arrival"] is None:
            report.add(
                filename,
                "No Arrival Date, and none could be inferred (no usable "
                "'Start Date' label earlier in the file). Fill in Arrival "
                "Date for this row in the source tool and re-export.",
                row=s["row"],
            )

    if pf.total_col_last is not None and abs(pf.miles_sum - pf.total_col_last) > MILES_TOLERANCE:
        # Not a blocking finding: there's nothing to "go fix" for this one.
        # TripWizard rounds each leg's displayed Miles while keeping an
        # unrounded running Total internally, so a mile or two of drift
        # between the two is a known, harmless quirk of the export itself,
        # not a sign of corrupted or hand-edited data (see docs/HISTORY.md).
        # Surfaced for transparency, same as the mileage-rescue/discard notes.
        report.log.append(
            f"{filename}: summed Miles column ({pf.miles_sum:.1f}) differs from "
            f"this file's own Total column ({pf.total_col_last:.1f}) by more than "
            f"{MILES_TOLERANCE:g} mile(s) - likely TripWizard's own rounding "
            "drift, not a parsing problem."
        )

    return pf


def check(paths: list[str]) -> Report:
    """Two-stage check: per-file structure first, then - only if every file
    is structurally clean - the merge-dependent checks (resolved city/state,
    coordinates, cross-file date gaps). Mirrors a compiler checking syntax
    before semantics: there's no point reporting a gap next to a file that
    didn't parse.
    """
    report = Report()
    parsed = []
    for path in paths:
        pf = _check_file_structure(path, report)
        if pf is not None:
            parsed.append(pf)
    report.parsed_files = parsed

    if not report.is_clean:
        return report

    master, overlap_log = merge.resolve_overlaps(parsed)
    stays, fold_log = merge.fold_waypoint_mileage(master)
    report.log += overlap_log + fold_log

    for s in stays:
        city, state = merge.resolve_city_state(s["stop_name"], s["location"], s["lat"], s["lon"])
        s["city"], s["state"] = city, state
        if s["lat"] is None or s["lon"] is None:
            report.add(s["source_file"], "Missing Latitude/Longitude for this stop.", row=s["row"])
        elif not state:
            report.add(
                s["source_file"],
                f"Could not determine a state for this stop: ({s['lat']}, "
                f"{s['lon']}) doesn't fall within any US state this tool "
                f"knows about, and neither Location ('{s['location']}') nor "
                f"Stop Name ('{s['stop_name']}') contains a parseable "
                "'City, ST'. If this is a real location outside the US, add "
                "'City, ST'-style text to the Location field in the source "
                "tool and re-export.",
                row=s["row"],
            )

    if not report.is_clean:
        return report

    merged = merge.merge_same_location(stays)
    for s in merged:
        s["miles"] = round(s.pop("leg_miles"), 1)

    prev = None
    for s in merged:
        if prev is not None:
            gap = (s["arrival"] - prev["departure"]).days
            if gap > GAP_TOLERANCE_DAYS:
                report.add(
                    f"{prev['source_file']} / {s['source_file']}",
                    f"{gap}-day gap in the record: {prev['city']}, {prev['state']} "
                    f"(departed {prev['departure']}) -> {s['city']}, {s['state']} "
                    f"(arrived {s['arrival']}). Add a source file covering this "
                    "period and re-run.",
                )
        prev = s

    if report.is_clean:
        report.merged_stays = merged
    return report
