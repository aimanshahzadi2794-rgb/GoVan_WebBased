"""Small geo utilities -- just enough to find the nearest stop on a route
and estimate a route's total distance."""
import math


def haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in kilometers."""
    R = 6371.0  # Earth's radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# Assumed average speed for urban van/bus routes with frequent stops --
# used only to turn a straight-line distance into a rough duration
# estimate. This is deliberately a simple constant, not a routing-API
# call: real driving distance/time (accounting for roads, traffic) would
# need a paid routing service, which is out of scope for the MVP.
ASSUMED_AVG_SPEED_KMH = 25.0


def route_distance_km(stops_in_order) -> float:
    """Sum of straight-line distances between consecutive stops.
    stops_in_order: list of objects with .lat and .lng, already ordered
    by sequence. Returns 0.0 for 0 or 1 stops (nothing to travel between)."""
    if len(stops_in_order) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(stops_in_order, stops_in_order[1:]):
        total += haversine_distance_km(a.lat, a.lng, b.lat, b.lng)
    return total


def estimate_duration_minutes(distance_km: float) -> int:
    if distance_km <= 0:
        return 0
    return round(distance_km / ASSUMED_AVG_SPEED_KMH * 60)
# """Geospatial helpers for the backend.

# This module provides small, dependency-free utilities for working with
# latitude/longitude values in API and business logic code.
# """

# from __future__ import annotations

# from math import atan2, cos, radians, sin, sqrt
# from typing import Iterable, Tuple


# Coordinate = Tuple[float, float]


# def haversine_km(
#     lat1: float,
#     lon1: float,
#     lat2: float,
#     lon2: float,
# ) -> float:
#     """Return the distance in kilometers between two geographic points."""
#     earth_radius_km = 6371.0

#     lat1_rad = radians(lat1)
#     lon1_rad = radians(lon1)
#     lat2_rad = radians(lat2)
#     lon2_rad = radians(lon2)

#     dlat = lat2_rad - lat1_rad
#     dlon = lon2_rad - lon1_rad

#     a = (
#         sin(dlat / 2) ** 2
#         + cos(lat1_rad)
#         * cos(lat2_rad)
#         * sin(dlon / 2) ** 2
#     )

#     c = 2 * atan2(sqrt(a), sqrt(1 - a))

#     return earth_radius_km * c


# def haversine_miles(
#     lat1: float,
#     lon1: float,
#     lat2: float,
#     lon2: float,
# ) -> float:
#     """Return the distance in miles between two geographic points."""
#     return haversine_km(lat1, lon1, lat2, lon2) * 0.621371


# def is_within_radius_km(
#     center_lat: float,
#     center_lon: float,
#     point_lat: float,
#     point_lon: float,
#     radius_km: float,
# ) -> bool:
#     """Check whether a point falls within a given radius around a center."""
#     return (
#         haversine_km(
#             center_lat,
#             center_lon,
#             point_lat,
#             point_lon,
#         )
#         <= radius_km
#     )


# def sort_by_distance(
#     origin: Coordinate,
#     points: Iterable[Coordinate],
# ) -> list[Coordinate]:
#     """Return points sorted by increasing distance from the origin."""
#     return sorted(
#         points,
#         key=lambda point: haversine_km(
#             origin[0],
#             origin[1],
#             point[0],
#             point[1],
#         ),
#     )


# def normalize_latitude(lat: float) -> float:
#     """Clamp latitude into a valid range."""
#     return max(-90.0, min(90.0, float(lat)))


# def normalize_longitude(lon: float) -> float:
#     """Clamp longitude into a valid range."""
#     return max(-180.0, min(180.0, float(lon)))


# def normalize_coordinate(
#     lat: float,
#     lon: float,
# ) -> Coordinate:
#     """Return a valid latitude/longitude tuple."""
#     return (
#         normalize_latitude(lat),
#         normalize_longitude(lon),
#     )


# # ---------------------------------------------------------------------------
# # Route distance and duration helpers
# # ---------------------------------------------------------------------------

# ASSUMED_AVG_SPEED_KMH = 25.0


# def route_distance_km(stops_in_order) -> float:
#     """Return total straight-line distance between consecutive route stops.

#     The distance is calculated using the Haversine formula.
#     """
#     if not stops_in_order or len(stops_in_order) < 2:
#         return 0.0

#     total = 0.0

#     for a, b in zip(
#         stops_in_order,
#         stops_in_order[1:],
#     ):
#         total += haversine_km(
#             a.lat,
#             a.lng,
#             b.lat,
#             b.lng,
#         )

#     return total


# def estimate_duration_minutes(
#     distance_km: float,
# ) -> int:
#     """Estimate route duration using the assumed average speed.

#     This is an estimate based on straight-line distance and does not
#     account for actual road routing, traffic, stops, or congestion.
#     """
#     if distance_km <= 0:
#         return 0

#     return round(
#         distance_km
#         / ASSUMED_AVG_SPEED_KMH
#         * 60
#     )
