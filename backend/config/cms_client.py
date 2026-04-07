"""
cms_client.py
--------------
Authenticated HTTP client for the Firebelly CMS API.
Matches the same pattern as the voice agent:
  API_BASE_URL, API_KEY, TENANT_ID from .env
"""

import os
from dotenv import load_dotenv
load_dotenv()
import requests
from functools import lru_cache
from datetime import datetime, timedelta
import logging
logging.basicConfig(level=logging.INFO)
from typing import Any

# # ── Config (mirrors voice agent pattern) ──────────────────────────────────────
# API_BASE_URL = os.getenv("API_BASE_URL", "https://firbelly-ai-production-c4fb.up.railway.app/api")
# API_KEY      = os.getenv("API_KEY",      "HpSU281XZ97YhtyXxqN67bNcynZPeZ1Xpmwq")
# TENANT_ID    = os.getenv("TENANT_ID",    os.getenv("RESTAURANT_ID", "329aab80-82d3-42a4-a1c2-61c3efdbe081"))
# ── Config (mirrors voice agent pattern) ──────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "")
API_KEY      = os.getenv("API_KEY", "")
TENANT_ID    = os.getenv("TENANT_ID", os.getenv("RESTAURANT_ID", ""))

# ── Simple in-memory cache (avoids hammering CMS on every DM) ─────────────────
_cache: dict[str, tuple[Any, datetime]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes — config changes rarely


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
    }


def _get(endpoint: str, params: dict | None = None, cache_key: str | None = None) -> dict:
    """
    GET request to CMS with optional caching.
    cache_key: if provided, result is cached for CACHE_TTL_SECONDS
    """
    if cache_key and cache_key in _cache:
        value, expires_at = _cache[cache_key]
        if datetime.utcnow() < expires_at:
            return value

    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.get(url, headers=_headers(), params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if cache_key:
            _cache[cache_key] = (data, datetime.utcnow() + timedelta(seconds=CACHE_TTL_SECONDS))
        return data
    except requests.exceptions.HTTPError as e:
        print(f"CMS HTTP error [{e.response.status_code}] {endpoint}: {e}")
        return {}
    except Exception as e:
        print(f"CMS request failed {endpoint}: {e}")
        return {}


def _post(endpoint: str, body: dict) -> dict:
    """POST request to CMS (no cache — mutations)."""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.post(url, headers=_headers(), json=body, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"CMS POST error [{e.response.status_code}] {endpoint}: {e}")
        return {"error": str(e)}
    except Exception as e:
        print(f"CMS POST failed {endpoint}: {e}")
        return {"error": str(e)}


# ── Public API ────────────────────────────────────────────────────────────────

def get_restaurant_config(restaurant_id: str = TENANT_ID) -> dict:
    """
    Full restaurant config: name, hours, contact, menu highlights,
    social handles, voice settings, reservation rules, ordering rules.
    Cached for 5 minutes.
    """
    return _get(
        f"/restaurants/{restaurant_id}/config",
        cache_key=f"config_{restaurant_id}"
    )


def get_menu(
    restaurant_id: str = TENANT_ID,
    search: str | None = None,
    category: str | None = None,
    is_vegetarian: bool | None = None,
    is_vegan: bool | None = None,
    is_gluten_free: bool | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
) -> dict:
    """
    Full menu organized by categories with optional filters.
    Prices are in paise (divide by 100 for rupees).
    Cached for 5 minutes.
    """
    params = {}
    if search: params["search"] = search
    if category: params["category"] = category
    if is_vegetarian is not None: params["isVegetarian"] = is_vegetarian
    if is_vegan is not None: params["isVegan"] = is_vegan
    if is_gluten_free is not None: params["isGlutenFree"] = is_gluten_free
    if min_price is not None: params["minPrice"] = min_price
    if max_price is not None: params["maxPrice"] = max_price

    cache_key = f"menu_{restaurant_id}_{hash(str(params))}"
    return _get(f"/restaurants/{restaurant_id}/menu", params=params, cache_key=cache_key)


def get_availability(
    restaurant_id: str = TENANT_ID,
    date: str | None = None,
    party_size: int | None = None,
) -> dict:
    """Check table availability for a given date and party size."""
    params = {}
    if date: params["date"] = date
    if party_size: params["partySize"] = party_size
    return _get(f"/restaurants/{restaurant_id}/availability", params=params)


def get_reservations(
    restaurant_id: str = TENANT_ID,
    date: str | None = None,
    status: str | None = None,
) -> dict:
    """Get reservations (for analytics/context)."""
    params = {}
    if date: params["date"] = date
    if status: params["status"] = status
    return _get(f"/restaurants/{restaurant_id}/reservations", params=params)


def create_reservation(
    restaurant_id: str = TENANT_ID,
    *,
    customer_name: str,
    customer_phone: str,
    party_size: int,
    date: str,
    time: str,
    special_requests: str = "",
) -> dict:
    """
    Create a reservation directly from a DM conversation.
    date: YYYY-MM-DD, time: HH:MM
    """
    return _post(f"/restaurants/{restaurant_id}/reservations", {
        "customerName": customer_name,
        "customerPhone": customer_phone,
        "partySize": party_size,
        "date": date,
        "time": time,
        "specialRequests": special_requests,
        "source": "social_media_dm",
    })


def list_restaurants() -> dict:
    """List all restaurants (for multi-tenant dashboard)."""
    return _get("/restaurants", cache_key="all_restaurants")


def invalidate_cache(restaurant_id: str | None = None):
    """Call this when CMS data is updated to force refresh."""
    global _cache
    if restaurant_id:
        _cache = {k: v for k, v in _cache.items() if restaurant_id not in k}
    else:
        _cache = {}