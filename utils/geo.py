"""
Geocoding utilities - city to region resolution.
Uses local dictionary first, then external APIs.
Priority: Visicom -> OpenCage -> Nominatim
"""
import os
import json
import logging
from typing import Optional, Dict
import asyncio

import aiohttp

from core.constants import CITIES, CITY_TO_REGION

logger = logging.getLogger(__name__)

# API keys
VISICOM_API_KEY = os.environ.get('VISICOM_API_KEY', '')
OPENCAGE_API_KEY = os.environ.get('OPENCAGE_API_KEY', '')

# Cache for geocoding results
_cache: Dict[str, Optional[str]] = {}
_cache_file = os.environ.get('GEOCODE_CACHE_FILE', 'geocode_cache.json')


def _load_cache():
    """Load cache from disk."""
    global _cache
    try:
        if os.path.exists(_cache_file):
            with open(_cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for k, v in data.items():
                    if isinstance(v, dict):
                        _cache[k] = v.get('region')
                    else:
                        _cache[k] = v
            logger.info(f"Geocode cache loaded: {len(_cache)} entries")
    except Exception as e:
        logger.warning(f"Failed to load geocode cache: {e}")


def _save_cache():
    """Save cache to disk."""
    try:
        with open(_cache_file, 'w', encoding='utf-8') as f:
            json.dump(_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save geocode cache: {e}")


# Load cache on import
_load_cache()


def get_region_for_city(city: str, hint: str = None) -> Optional[str]:
    """
    Get region for a city name.
    
    Priority:
    1. Local CITIES dictionary (instant)
    2. Geocode cache (instant)
    3. AI fallback (if available)
    
    Args:
        city: City name (normalized)
        hint: Optional region hint
        
    Returns:
        Region in format "Назва обл." or None
    """
    if not city:
        return None
    
    # 1. Check local dictionary (fast path)
    if city in CITIES:
        return CITIES[city]
    city_lower = city.lower()
    region = CITY_TO_REGION.get(city_lower)
    if region:
        return region
    
    # 2. Check cache
    cache_key = city_lower
    if cache_key in _cache:
        return _cache[cache_key]
    
    # 3. Return hint if provided
    return hint


async def geocode_city(city: str, hint_region: str = None) -> Optional[str]:
    """
    Geocode city using external API.
    
    Uses OpenCage first, then Nominatim as fallback.
    Results are cached.
    
    Args:
        city: City name
        hint_region: Optional region hint for disambiguation
        
    Returns:
        Region or None
    """
    if not city:
        return None
    
    # Check local first
    result = get_region_for_city(city, hint_region)
    if result:
        return result
    
    cache_key = city.lower()
    
    # Try Visicom first (Ukrainian API, best for Ukrainian cities)
    if VISICOM_API_KEY:
        result = await _visicom_geocode(city, hint_region)
        if result:
            _cache[cache_key] = result
            _save_cache()
            logger.info(f"Visicom: {city} -> {result}")
            return result
    
    # Fallback to OpenCage
    if OPENCAGE_API_KEY:
        result = await _opencage_geocode(city, hint_region)
        if result:
            _cache[cache_key] = result
            _save_cache()
            logger.info(f"OpenCage: {city} -> {result}")
            return result
    
    # Last resort: Nominatim
    result = await _nominatim_geocode(city)
    if result:
        _cache[cache_key] = result
        _save_cache()
        logger.info(f"Nominatim: {city} -> {result}")
        return result
    
    # Mark as not found
    _cache[cache_key] = None
    _save_cache()
    return None


async def _visicom_geocode(city: str, hint_region: str = None) -> Optional[str]:
    """Geocode using Visicom API (Ukrainian geocoder)."""
    try:
        query = f"{city}, Україна"
        if hint_region:
            region_clean = hint_region.replace('обл.', '').replace('область', '').strip()
            query = f"{city}, {region_clean}, Україна"
        
        url = "https://api.visicom.ua/data-api/5.0/uk/geocode.json"
        params = {
            'text': query,
            'key': VISICOM_API_KEY,
            'country': 'ua',
            'limit': 1
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 402 or response.status == 403:
                    logger.warning("Visicom quota/auth error")
                    return None
                
                if not response.ok:
                    logger.debug(f"Visicom error: {response.status}")
                    return None
                
                data = await response.json()
                
                # Visicom returns single Feature or FeatureCollection
                if data.get('type') == 'Feature':
                    props = data.get('properties', {})
                elif data.get('type') == 'FeatureCollection':
                    features = data.get('features', [])
                    if not features:
                        return None
                    props = features[0].get('properties', {})
                else:
                    return None
                
                # Check it's in Ukraine
                country = props.get('country', '') or props.get('country_code', '')
                if country and 'україн' not in country.lower() and 'ua' not in country.lower():
                    return None
                
                # Get region from level1 (область)
                region = props.get('level1', '')
                
                # Special case: Київ (no level1, it's a special city)
                if not region:
                    name = props.get('name', '')
                    if name.lower() == 'київ':
                        region = 'Київська область'
                
                if region:
                    return _format_region(region)
        
    except asyncio.TimeoutError:
        logger.debug(f"Visicom timeout for {city}")
    except Exception as e:
        logger.debug(f"Visicom error: {e}")
    
    return None


async def _opencage_geocode(city: str, hint_region: str = None) -> Optional[str]:
    """Geocode using OpenCage API."""
    try:
        query = f"{city}, Україна"
        if hint_region:
            region_clean = hint_region.replace('обл.', '').replace('область', '').strip()
            query = f"{city}, {region_clean}, Україна"
        
        url = "https://api.opencagedata.com/geocode/v1/json"
        params = {
            'q': query,
            'key': OPENCAGE_API_KEY,
            'countrycode': 'ua',
            'limit': 1,
            'no_annotations': 1,
            'language': 'uk'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 402:
                    logger.warning("OpenCage quota exceeded")
                    return None
                
                if not response.ok:
                    return None
                
                data = await response.json()
                results = data.get('results', [])
                
                if not results:
                    return None
                
                components = results[0].get('components', {})
                if components.get('country_code', '').lower() != 'ua':
                    return None
                
                state = components.get('state', '')
                if state:
                    return _format_region(state)
        
    except Exception as e:
        logger.debug(f"OpenCage error: {e}")
    
    return None


async def _nominatim_geocode(city: str) -> Optional[str]:
    """Geocode using Nominatim (OpenStreetMap)."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': f"{city}, Україна",
            'format': 'json',
            'addressdetails': 1,
            'limit': 1,
            'accept-language': 'uk'
        }
        headers = {
            'User-Agent': 'TelegramForwarder/2.0'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=5) as response:
                if not response.ok:
                    return None
                
                data = await response.json()
                if not data:
                    return None
                
                address = data[0].get('address', {})
                state = address.get('state', '')
                
                if state:
                    return _format_region(state)
        
    except asyncio.TimeoutError:
        logger.debug(f"Nominatim timeout for {city}")
    except Exception as e:
        logger.debug(f"Nominatim error: {e}")
    
    return None


def _format_region(region_raw: str) -> Optional[str]:
    """Format region to standard format."""
    if not region_raw:
        return None
    
    region = region_raw.strip()
    
    if region.endswith(' обл.'):
        return region
    
    if 'Крим' in region:
        return 'АР Крим'
    
    region = region.replace(' область', '').replace(' Область', '')
    region = region.replace(' обл.', '').replace(' обл', '')
    region = region.strip()
    
    if region:
        region = region[0].upper() + region[1:]
        return f"{region} обл."
    
    return None
