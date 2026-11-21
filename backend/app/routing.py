"""Configurable road routing with a dependency-free straight-line fallback.

Set ROUTING_BASE_URL to an OSRM-compatible endpoint to enable road geometry,
distance and duration. The public OSRM demo endpoint is intentionally not the
default because it has no production availability guarantee.
"""
from functools import lru_cache
import json
import os
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .geo import estimate_duration_minutes, route_distance_km

TRAFFIC_MULTIPLIERS = {"low": 1.0, "moderate": 1.2, "heavy": 1.5}


def apply_traffic_scenario(duration_minutes: int):
    """Apply an explicitly selected demo multiplier; never implies live traffic."""
    scenario = os.getenv("TRAFFIC_SCENARIO", "").strip().lower()
    multiplier = TRAFFIC_MULTIPLIERS.get(scenario)
    if multiplier is None:
        return duration_minutes, None
    return round(duration_minutes * multiplier), scenario


@lru_cache(maxsize=256)
def _osrm_route(base_url: str, coordinates: tuple[tuple[float, float], ...]):
    coord_path = ";".join(f"{lng},{lat}" for lat, lng in coordinates)
    url = f"{base_url.rstrip('/')}/route/v1/driving/{quote(coord_path, safe=';,.-')}?overview=full&geometries=geojson&steps=false"
    request = Request(url, headers={"User-Agent": "GoVan/1.0 (student fleet coordination project)"})
    with urlopen(request, timeout=float(os.getenv("ROUTING_TIMEOUT_SECONDS", "2.5"))) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise ValueError("OSRM returned no route")
    result = payload["routes"][0]
    # Leaflet expects [latitude, longitude], while GeoJSON provides [longitude, latitude].
    geometry = [[lat, lng] for lng, lat in result["geometry"]["coordinates"]]
    return round(result["distance"] / 1000, 2), max(0, round(result["duration"] / 60)), geometry


def route_metrics(stops):
    coordinates = tuple((float(stop.lat), float(stop.lng)) for stop in stops)
    straight_km = route_distance_km(stops)
    fallback_geometry = [[lat, lng] for lat, lng in coordinates]
    if len(coordinates) < 2:
        base_duration = estimate_duration_minutes(straight_km)
        duration, scenario = apply_traffic_scenario(base_duration)
        return straight_km, duration, fallback_geometry, "straight_line", base_duration, scenario

    base_url = os.getenv("ROUTING_BASE_URL", "").strip()
    if not base_url:
        base_duration = estimate_duration_minutes(straight_km)
        duration, scenario = apply_traffic_scenario(base_duration)
        return straight_km, duration, fallback_geometry, "straight_line", base_duration, scenario
    try:
        distance, duration, geometry = _osrm_route(base_url, coordinates)
        adjusted_duration, scenario = apply_traffic_scenario(duration)
        return distance, adjusted_duration, geometry, "osrm", duration, scenario
    except (URLError, TimeoutError, ValueError, KeyError, OSError, json.JSONDecodeError):
        base_duration = estimate_duration_minutes(straight_km)
        duration, scenario = apply_traffic_scenario(base_duration)
        return straight_km, duration, fallback_geometry, "straight_line_fallback", base_duration, scenario
