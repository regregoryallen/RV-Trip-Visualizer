from datetime import date

from rv_trip_visualizer import merge
from rv_trip_visualizer.parser import ParsedFile


def _stop(**kw):
    base = {
        "source_file": "f.xlsx", "row": 5, "stop_name": "", "location": "",
        "nights": 0, "nights_raw": 0, "arrival": None, "departure": None,
        "arrival_inferred": False, "departure_inferred": False,
        "lat": None, "lon": None, "miles": 0.0,
    }
    base.update(kw)
    return base


def test_extract_city_state_simple():
    assert merge.extract_city_state("", "Austin, TX") == ("Austin", "TX")


def test_extract_city_state_with_trailing_parenthetical():
    assert merge.extract_city_state("", "Durant, OK (Choctaw Casino)") == ("Durant", "OK")


def test_extract_city_state_unresolvable_returns_none():
    assert merge.extract_city_state("Golden Eagle RV Park", "Golden Eagle RV Park") == (None, None)


def test_resolve_city_state_prefers_parsed_text():
    city, state = merge.resolve_city_state("", "Austin, TX", 30.3, -97.7)
    assert (city, state) == ("Austin", "TX")


def test_resolve_city_state_falls_back_to_geocoding_when_text_is_unparseable():
    city, state = merge.resolve_city_state(
        "Golden Eagle RV Park", "Golden Eagle RV Park", 30.3, -97.7  # central Texas
    )
    assert state == "TX"
    assert city == "Golden Eagle RV Park"  # raw text, not invented


def test_resolve_city_state_geocode_fallback_strips_duplicated_state():
    # Location text ends in the same state abbreviation geocoding resolves -
    # the fallback city shouldn't read "540 Therma Way, NM" next to a State
    # column that also says "NM".
    city, state = merge.resolve_city_state("Golden Eagle RV Park", "540 Therma Way, NM", 36.5, -105.3)
    assert state == "NM"
    assert city == "540 Therma Way"


def test_resolve_city_state_returns_none_without_lat_lon_or_parseable_text():
    assert merge.resolve_city_state("Mystery Spot", "Mystery Spot", None, None) == (None, None)


def test_fold_waypoint_mileage_folds_zero_night_leg_forward():
    stops = [
        _stop(stop_name="Gas Stop", location="Waco, TX", nights=0, miles=100,
              arrival=date(2024, 1, 1), departure=date(2024, 1, 1)),
        _stop(stop_name="Austin, TX", location="Austin, TX", nights=2, miles=50,
              arrival=date(2024, 1, 1), departure=date(2024, 1, 3)),
    ]
    stays, log = merge.fold_waypoint_mileage(stops)
    assert len(stays) == 1
    assert stays[0]["leg_miles"] == 150
    assert log == []


def test_fold_waypoint_mileage_warns_on_trailing_unfolded_miles():
    stops = [_stop(stop_name="Gas Stop", nights=0, miles=42,
                    arrival=date(2024, 1, 1), departure=date(2024, 1, 1))]
    stays, log = merge.fold_waypoint_mileage(stops)
    assert stays == []
    assert len(log) == 1
    assert "42" in log[0]


def test_resolve_overlaps_rescues_mileage_on_the_gordonville_pattern():
    """Later file's first stop re-records the same physical location the
    earlier file already arrived at (same day), with Miles=0 (TripWizard's
    "current location" convention) - a stop is only "fully superseded" (vs.
    truncated) when its own arrival is on/after the new file's start, so
    both stops have to arrive the same day for this path to trigger. The
    real mileage on the dropped stop should be rescued onto the survivor
    rather than discarded.
    """
    earlier = ParsedFile(path="a.xlsx", stops=[
        _stop(source_file="a.xlsx", stop_name="Gordonville, TX", location="Gordonville, TX",
              nights=2, miles=35, arrival=date(2024, 1, 2), departure=date(2024, 1, 4)),
    ])
    later = ParsedFile(path="b.xlsx", stops=[
        _stop(source_file="b.xlsx", stop_name="Gordonville, TX", location="Gordonville, TX",
              nights=5, miles=0, arrival=date(2024, 1, 2), departure=date(2024, 1, 7)),
    ])
    master, log = merge.resolve_overlaps([earlier, later])
    assert len(master) == 1
    assert master[0]["miles"] == 35
    assert any("rescued" in l for l in log)


def test_resolve_overlaps_discards_mileage_on_a_genuine_plan_change():
    earlier = ParsedFile(path="a.xlsx", stops=[
        _stop(source_file="a.xlsx", stop_name="Plan A Stop", location="Waco, TX",
              nights=2, miles=80, arrival=date(2024, 1, 2), departure=date(2024, 1, 4)),
    ])
    later = ParsedFile(path="b.xlsx", stops=[
        _stop(source_file="b.xlsx", stop_name="Plan B Stop", location="Dallas, TX",
              nights=5, miles=0, arrival=date(2024, 1, 2), departure=date(2024, 1, 7)),
    ])
    master, log = merge.resolve_overlaps([earlier, later])
    assert len(master) == 1
    assert master[0]["location"] == "Dallas, TX"
    assert any("discarded" in l for l in log)


def test_merge_same_location_combines_adjacent_stays():
    stays = [
        {"arrival": date(2024, 1, 1), "departure": date(2024, 1, 3), "nights": 2,
         "leg_miles": 10.0, "city": "Austin", "state": "TX"},
        {"arrival": date(2024, 1, 3), "departure": date(2024, 1, 5), "nights": 2,
         "leg_miles": 0.0, "city": "Austin", "state": "TX"},
    ]
    merged = merge.merge_same_location(stays)
    assert len(merged) == 1
    assert merged[0]["nights"] == 4
    assert merged[0]["leg_miles"] == 10.0
    assert merged[0]["departure"] == date(2024, 1, 5)
