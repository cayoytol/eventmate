import json
import urllib.request
import urllib.parse
import urllib.error
import logging
import hashlib
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

def map_locale(locale):
    """
    Map locale to 2GIS standard:
    - ru -> ru_KZ
    - kz -> kk_KZ
    - en -> omit (returns None)
    """
    if locale == "ru":
        return "ru_KZ"
    if locale == "kz":
        return "kk_KZ"
    return None

def get_geocode_cache_key(query, locale, city=None):
    # Normalize inputs
    norm_query = " ".join((query or "").strip().lower().split())
    norm_city = " ".join((city or "").strip().lower().split())
    
    # Hash query and city to prevent huge cache keys
    hasher = hashlib.md5()
    hasher.update(norm_query.encode("utf-8"))
    hasher.update(norm_city.encode("utf-8"))
    hasher.update(locale.encode("utf-8"))
    
    return f"geocode_{hasher.hexdigest()}"

def get_reverse_geocode_cache_key(latitude, longitude, locale):
    # Round coordinates to 5 decimal places (approx 1m accuracy)
    lat_rounded = round(float(latitude), 5)
    lng_rounded = round(float(longitude), 5)
    
    return f"rev_geocode_{lat_rounded}_{lng_rounded}_{locale}"

def make_dgis_request(params):
    """
    Perform a GET request to 2GIS items geocoder.
    Logs only safe summaries and filters out DGIS_API_KEY from logs.
    """
    # Create request params safely without editing settings object
    req_params = {k: v for k, v in params.items() if v is not None}
    
    query_string = urllib.parse.urlencode(req_params)
    url = f"{settings.DGIS_API_URL}?{query_string}"
    
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
        },
        method="GET"
    )
    
    op_type = "geocode" if "q" in params else "reverse_geocode"
    
    try:
        with urllib.request.urlopen(req, timeout=settings.DGIS_TIMEOUT_SECONDS) as response:
            raw_body = response.read().decode('utf-8')
            parsed_json = json.loads(raw_body)
            # Log successful status summary
            logger.info(f"2GIS API request successful: operation={op_type}, status_code={response.status}")
            return parsed_json
    except urllib.error.HTTPError as e:
        logger.error(f"2GIS API HTTP error occurred: operation={op_type}, status_code={e.code}, error_type=HTTPError")
        return None
    except urllib.error.URLError as e:
        logger.error(f"2GIS API network error occurred: operation={op_type}, reason={type(e.reason).__name__}, error_type=URLError")
        return None
    except json.JSONDecodeError:
        logger.error(f"2GIS API response decoding error occurred: operation={op_type}, error_type=JSONDecodeError")
        return None
    except Exception as e:
        logger.error(f"2GIS API unexpected error: operation={op_type}, error_class={e.__class__.__name__}")
        return None

def extract_city(item, default_city=None):
    """
    Safely extract city from 2GIS item structure or fall back to defaults.
    """
    adm_div = item.get("adm_div")
    if isinstance(adm_div, dict):
        city_data = adm_div.get("city")
        if isinstance(city_data, dict):
            city_name = city_data.get("name")
            if city_name:
                return city_name
                
    # Fallback to parsing from full_name / address
    full_name = item.get("full_name") or item.get("name") or ""
    if full_name:
        parts = [p.strip() for p in full_name.split(",")]
        # Typically the city is the first or second part
        for part in parts:
            if part.lower() not in ("казахстан", "kazakhstan", "россия", "russia"):
                return part
                
    return default_city or ""

def normalize_item(item, default_city=None):
    """
    Normalize 2GIS item structure to project's internal Geocode result shape.
    Coordinates point format in 2GIS is point: { lat: X, lon: Y }
    """
    if not isinstance(item, dict):
        return None
        
    item_id = str(item.get("id", ""))
    name = item.get("name", "")
    full_name = item.get("full_name") or item.get("address") or name
    
    point = item.get("point")
    if not isinstance(point, dict):
        return None
        
    lat_val = point.get("lat")
    lon_val = point.get("lon")
    
    if lat_val is None or lon_val is None:
        return None
        
    try:
        latitude = float(lat_val)
        longitude = float(lon_val)
    except (ValueError, TypeError):
        return None
        
    # Coordinate range validation
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return None
        
    city_name = extract_city(item, default_city)
    
    return {
        "id": item_id,
        "name": name,
        "address": full_name,
        "city": city_name,
        "latitude": latitude,
        "longitude": longitude
    }

def geocode_address(query, locale, city=None):
    """
    Direct geocoding: searches for address and returns list of results.
    """
    if not settings.DGIS_GEOCODING_ENABLED:
        return []
        
    cache_key = get_geocode_cache_key(query, locale, city)
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
        
    # Normalize query by combining city with search string
    combined_q = f"{city}, {query}" if city else query
    combined_q = " ".join(combined_q.strip().split())
    
    mapped_locale = map_locale(locale)
    
    params = {
        "q": combined_q,
        "key": settings.DGIS_API_KEY,
        "fields": "items.point,items.address,items.full_address_name,items.adm_div",
        "limit": settings.DGIS_GEOCODING_RESULT_LIMIT,
    }
    
    if mapped_locale:
        params["locale"] = mapped_locale
        
    raw_res = make_dgis_request(params)
    if not raw_res or "result" not in raw_res:
        return []
        
    items = raw_res["result"].get("items", [])
    normalized_results = []
    
    for item in items:
        norm = normalize_item(item, city)
        if norm:
            normalized_results.append(norm)
            
    # Cache the successful normalized results
    cache.set(cache_key, normalized_results, settings.DGIS_GEOCODING_CACHE_SECONDS)
    return normalized_results

def reverse_geocode(latitude, longitude, locale):
    """
    Reverse geocoding: finds closest address from latitude & longitude coordinates.
    """
    if not settings.DGIS_GEOCODING_ENABLED:
        return None
        
    cache_key = get_reverse_geocode_cache_key(latitude, longitude, locale)
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data
        
    mapped_locale = map_locale(locale)
    
    # 2GIS coordinate ordering: longitude,latitude
    params = {
        "location": f"{longitude},{latitude}",
        "key": settings.DGIS_API_KEY,
        "fields": "items.point,items.address,items.full_address_name,items.adm_div",
        "limit": 1,
    }
    
    if mapped_locale:
        params["locale"] = mapped_locale
        
    raw_res = make_dgis_request(params)
    if not raw_res or "result" not in raw_res:
        return None
        
    items = raw_res["result"].get("items", [])
    if not items:
        return None
        
    norm = normalize_item(items[0])
    if norm:
        cache.set(cache_key, norm, settings.DGIS_GEOCODING_CACHE_SECONDS)
        
    return norm
