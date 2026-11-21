from types import SimpleNamespace
from urllib.error import URLError

from app import routing
from app.routing import apply_traffic_scenario, route_metrics


def test_route_metrics_fallback_is_explicit_and_returns_leaflet_geometry(monkeypatch):
    monkeypatch.delenv("ROUTING_BASE_URL", raising=False)
    monkeypatch.delenv("TRAFFIC_SCENARIO", raising=False)
    stops = [
        SimpleNamespace(lat=31.52, lng=74.35),
        SimpleNamespace(lat=31.53, lng=74.36),
    ]

    distance, duration, geometry, source, base_duration, scenario = route_metrics(stops)

    assert distance > 0
    assert duration == base_duration
    assert geometry == [[31.52, 74.35], [31.53, 74.36]]
    assert source == "straight_line"
    assert scenario is None


def test_demo_traffic_scenario_is_labeled_and_applies_multiplier(monkeypatch):
    monkeypatch.setenv("TRAFFIC_SCENARIO", "heavy")
    assert apply_traffic_scenario(20) == (30, "heavy")


def test_unavailable_osrm_provider_falls_back_with_explicit_source(monkeypatch):
    monkeypatch.setenv("ROUTING_BASE_URL", "http://unavailable.invalid")
    monkeypatch.delenv("TRAFFIC_SCENARIO", raising=False)

    def unavailable(*_args):
        raise URLError("simulated network failure")

    monkeypatch.setattr(routing, "_osrm_route", unavailable)
    stops = [
        SimpleNamespace(lat=31.52, lng=74.35),
        SimpleNamespace(lat=31.53, lng=74.36),
    ]
    distance, duration, geometry, source, base_duration, scenario = route_metrics(stops)
    assert distance > 0
    assert duration == base_duration
    assert len(geometry) == 2
    assert source == "straight_line_fallback"
    assert scenario is None
