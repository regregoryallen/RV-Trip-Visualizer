from rv_trip_visualizer import geocode


def test_state_from_point_austin_tx():
    assert geocode.state_from_point(30.2672, -97.7431) == "TX"


def test_state_from_point_denver_co():
    assert geocode.state_from_point(39.7392, -104.9903) == "CO"


def test_state_from_point_outside_any_state_returns_none():
    assert geocode.state_from_point(10.0, -160.0) is None  # middle of the Pacific


def test_state_from_point_requires_both_coordinates():
    assert geocode.state_from_point(None, -97.7431) is None
    assert geocode.state_from_point(30.2672, None) is None
    assert geocode.state_from_point(None, None) is None
