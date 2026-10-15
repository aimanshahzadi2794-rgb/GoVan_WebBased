"""
Reverse geocoding proxy.

Nominatim's usage policy requires a descriptive User-Agent identifying the
calling application, and explicitly disallows calling it directly from
client-side JavaScript. This endpoint makes that call server-side.
"""
import httpx
from fastapi import APIRouter, Depends, Query

from .. import models
from ..deps import get_current_user

router = APIRouter(prefix="/geocode", tags=["geocode"])

_cache: dict[str, str] = {}


def _cache_key(lat: float, lng: float) -> str:
    return f"{lat:.4f},{lng:.4f}"


@router.get("/reverse")
async def reverse_geocode(
    lat: float = Query(...),
    lng: float = Query(...),
    user: models.User = Depends(get_current_user),
):
    key = _cache_key(lat, lng)
    if key in _cache:
        return {"label": _cache[key]}

    fallback = f"{lat:.3f}, {lng:.3f}"
    label = fallback

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"format": "json", "lat": lat, "lon": lng, "zoom": 16, "addressdetails": 1},
                headers={"User-Agent": "GoVan-FYP/1.0 (student project; contact: admin@govan.dev)"},
            )
        if resp.status_code == 200:
            data = resp.json()
            addr = data.get("address", {})
            parts = [
                addr.get("neighbourhood") or addr.get("suburb") or addr.get("road"),
                addr.get("city") or addr.get("town") or addr.get("county"),
            ]
            parts = [p for p in parts if p]
            label = ", ".join(parts) if parts else data.get("display_name", fallback)
    except Exception:
        label = fallback

    _cache[key] = label
    return {"label": label}