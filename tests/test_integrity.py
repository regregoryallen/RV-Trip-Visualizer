from rv_trip_visualizer import integrity
from .conftest import ALL_HEADERS


def test_check_is_clean_for_two_consecutive_files(make_workbook):
    f1 = make_workbook("trip1.xlsx", ALL_HEADERS, [
        {"Stop Name": "Austin, TX", "Miles": 0, "Total": 0, "Arrival Date": "6/27/19",
         "Nights": 2, "Departure Date": "6/29/19", "Location": "Austin, TX",
         "Latitude": 30.3, "Longitude": -97.7},
    ])
    f2 = make_workbook("trip2.xlsx", ALL_HEADERS, [
        {"Stop Name": "Dallas, TX", "Miles": 200, "Total": 200, "Arrival Date": "6/29/19",
         "Nights": 1, "Departure Date": "6/30/19", "Location": "Dallas, TX",
         "Latitude": 32.78, "Longitude": -96.8},
    ])
    report = integrity.check([f1, f2])
    assert report.is_clean, report.findings
    assert len(report.merged_stays) == 2
    assert report.merged_stays[0]["city"] == "Austin"
    assert report.merged_stays[1]["miles"] == 200


def test_check_reports_missing_required_column(make_workbook):
    headers = [h for h in ALL_HEADERS if h != "Longitude"]
    f1 = make_workbook("nolong.xlsx", headers, [
        {"Stop Name": "Austin, TX", "Miles": 0, "Arrival Date": "6/27/19",
         "Nights": 2, "Departure Date": "6/29/19", "Location": "Austin, TX", "Latitude": 30.3},
    ])
    report = integrity.check([f1])
    assert not report.is_clean
    assert any("Longitude" in f.message for f in report.findings)
    assert report.merged_stays == []


def test_check_reports_a_cross_file_gap(make_workbook):
    f1 = make_workbook("trip1.xlsx", ALL_HEADERS, [
        {"Stop Name": "Austin, TX", "Miles": 0, "Total": 0, "Arrival Date": "6/27/19",
         "Nights": 2, "Departure Date": "6/29/19", "Location": "Austin, TX",
         "Latitude": 30.3, "Longitude": -97.7},
    ])
    f2 = make_workbook("trip2.xlsx", ALL_HEADERS, [
        {"Stop Name": "Dallas, TX", "Miles": 200, "Total": 200, "Arrival Date": "7/15/19",
         "Nights": 1, "Departure Date": "7/16/19", "Location": "Dallas, TX",
         "Latitude": 32.78, "Longitude": -96.8},
    ])
    report = integrity.check([f1, f2])
    assert not report.is_clean
    assert any("gap" in f.message.lower() for f in report.findings)


def test_check_reports_unresolvable_city_state(make_workbook):
    f1 = make_workbook("ambiguous.xlsx", ALL_HEADERS, [
        {"Stop Name": "Golden Eagle RV Park", "Miles": 0, "Total": 0, "Arrival Date": "6/27/19",
         "Nights": 2, "Departure Date": "6/29/19", "Location": "Golden Eagle RV Park",
         "Latitude": 30.3, "Longitude": -97.7},
    ])
    report = integrity.check([f1])
    assert not report.is_clean
    assert any("City, ST" in f.message for f in report.findings)


def test_check_reports_miles_total_mismatch_beyond_tolerance(make_workbook):
    f1 = make_workbook("mismatch.xlsx", ALL_HEADERS, [
        {"Stop Name": "Austin, TX", "Miles": 10, "Total": 10, "Arrival Date": "6/27/19",
         "Nights": 1, "Departure Date": "6/28/19", "Location": "Austin, TX",
         "Latitude": 30.3, "Longitude": -97.7},
        {"Stop Name": "Dallas, TX", "Miles": 200, "Total": 999, "Arrival Date": "6/28/19",
         "Nights": 1, "Departure Date": "6/29/19", "Location": "Dallas, TX",
         "Latitude": 32.78, "Longitude": -96.8},
    ])
    report = integrity.check([f1])
    # Not blocking: TripWizard's own rounding drift isn't something the user
    # can "go fix" in the source data, so it's surfaced as a transparency
    # note rather than a finding that refuses to build.
    assert report.is_clean, report.findings
    assert any("Total column" in l for l in report.log)
