from datetime import date

import pytest

from rv_trip_visualizer import parser
from .conftest import ALL_HEADERS


def test_parse_file_basic(make_workbook):
    path = make_workbook("basic.xlsx", ALL_HEADERS, [
        {"Stop Name": "Austin, TX", "Miles": 0, "Total": 0, "Arrival Date": "6/27/19",
         "Nights": 2, "Departure Date": "6/29/19", "Location": "Austin, TX",
         "Latitude": 30.3, "Longitude": -97.7},
        {"Stop Name": "Dallas, TX", "Miles": 200, "Total": 200, "Arrival Date": "6/29/19",
         "Nights": 1, "Departure Date": "6/30/19", "Location": "Dallas, TX",
         "Latitude": 32.78, "Longitude": -96.8},
    ])
    pf = parser.parse_file(path)
    assert len(pf.stops) == 2
    assert pf.stops[0]["arrival"] == date(2019, 6, 27)
    assert pf.stops[0]["arrival_inferred"] is False
    assert pf.stops[1]["miles"] == 200
    assert pf.total_col_last == 200
    assert pf.miles_sum == 200


def test_parse_file_infers_missing_dates_from_nights(make_workbook):
    path = make_workbook("inferred.xlsx", ALL_HEADERS, [
        {"Stop Name": "Austin, TX", "Miles": 0, "Nights": 2,
         "Location": "Austin, TX", "Latitude": 30.3, "Longitude": -97.7},
        {"Stop Name": "Dallas, TX", "Miles": 200, "Nights": 1,
         "Location": "Dallas, TX", "Latitude": 32.78, "Longitude": -96.8},
    ], start_date_label="Start Date: Thursday, June 27, 2019")
    pf = parser.parse_file(path)
    assert pf.stops[0]["arrival"] == date(2019, 6, 27)
    assert pf.stops[0]["arrival_inferred"] is True
    assert pf.stops[0]["departure"] == date(2019, 6, 29)
    assert pf.stops[0]["departure_inferred"] is True
    # second stop's arrival walks forward from the first stop's departure
    assert pf.stops[1]["arrival"] == date(2019, 6, 29)
    assert pf.stops[1]["arrival_inferred"] is True


def test_parse_file_sorts_scrambled_rows_by_arrival(make_workbook):
    # Row order deliberately not chronological - a real corrupted export did this.
    path = make_workbook("scrambled.xlsx", ALL_HEADERS, [
        {"Stop Name": "Later Stop", "Miles": 50, "Arrival Date": "7/5/19", "Nights": 1,
         "Departure Date": "7/6/19", "Location": "Later, TX", "Latitude": 1, "Longitude": -1},
        {"Stop Name": "Earlier Stop", "Miles": 10, "Arrival Date": "6/27/19", "Nights": 1,
         "Departure Date": "6/28/19", "Location": "Earlier, TX", "Latitude": 2, "Longitude": -2},
    ])
    pf = parser.parse_file(path)
    assert [s["stop_name"] for s in pf.stops] == ["Earlier Stop", "Later Stop"]


def test_parse_file_flags_non_numeric_nights_without_crashing(make_workbook):
    path = make_workbook("badnights.xlsx", ALL_HEADERS, [
        {"Stop Name": "Austin, TX", "Miles": 0, "Arrival Date": "6/27/19", "Nights": "n/a",
         "Departure Date": "6/29/19", "Location": "Austin, TX", "Latitude": 30.3, "Longitude": -97.7},
    ])
    pf = parser.parse_file(path)
    assert pf.stops[0]["nights"] is None
    assert pf.stops[0]["nights_raw"] == "n/a"


def test_parse_file_raises_schema_error_when_header_missing(make_workbook):
    missing_lat = [h for h in ALL_HEADERS if h != "Latitude"]
    path = make_workbook("nolat.xlsx", missing_lat, [
        {"Stop Name": "Austin, TX", "Miles": 0, "Arrival Date": "6/27/19", "Nights": 1,
         "Departure Date": "6/28/19", "Location": "Austin, TX", "Longitude": -97.7},
    ])
    with pytest.raises(parser.SchemaError) as exc:
        parser.parse_file(path)
    assert "Latitude" in exc.value.missing
