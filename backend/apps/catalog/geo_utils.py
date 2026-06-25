import math
from rest_framework.exceptions import ValidationError

EARTH_RADIUS_M = 6371000.0
MIN_RADIUS_M = 100.0
MAX_RADIUS_M = 100000.0

def parse_bbox(value):
    """
    Parse and validate bounding box format: west,south,east,north
    or min_lng,min_lat,max_lng,max_lat.
    """
    if not value:
        return None
        
    if isinstance(value, bool):
        raise ValidationError("bbox parameter must be a string, not a boolean.")
        
    if not isinstance(value, str):
        raise ValidationError("bbox parameter must be a string.")
        
    parts = value.split(',')
    if len(parts) != 4:
        raise ValidationError("bbox parameter must have exactly 4 values (min_lng,min_lat,max_lng,max_lat).")
        
    coords = []
    for x in parts:
        stripped = x.strip()
        if not stripped:
            raise ValidationError("bbox values must not be empty.")
        try:
            val = float(stripped)
        except (ValueError, TypeError):
            raise ValidationError("bbox values must be valid numbers.")
            
        if isinstance(val, bool):
            raise ValidationError("bbox values must not be boolean.")
            
        if not math.isfinite(val):
            raise ValidationError("bbox values must be finite numbers.")
        coords.append(val)
        
    min_lng, min_lat, max_lng, max_lat = coords
    
    if not (-180 <= min_lng <= 180) or not (-180 <= max_lng <= 180):
        raise ValidationError("Longitude must be between -180 and 180.")
    if not (-90 <= min_lat <= 90) or not (-90 <= max_lat <= 90):
        raise ValidationError("Latitude must be between -90 and 90.")
        
    if min_lat > max_lat:
        raise ValidationError("min_latitude must be less than or equal to max_latitude.")
    if min_lng > max_lng:
        raise ValidationError("min_longitude must be less than or equal to max_longitude (dateline crossing is not supported).")
        
    return min_lng, min_lat, max_lng, max_lat

def parse_radius_params(params):
    """
    Parse and validate center coordinates (lat, lng) and radius parameters.
    """
    lat_val = params.get("lat")
    lng_val = params.get("lng")
    radius_val = params.get("radius")
    
    has_any = (lat_val is not None) or (lng_val is not None) or (radius_val is not None)
    if not has_any:
        return None
        
    if not (lat_val is not None and lng_val is not None and radius_val is not None):
        raise ValidationError("lat, lng, and radius must be provided together.")
        
    def validate_numeric(val, name):
        if isinstance(val, bool):
            raise ValidationError(f"{name} must be a valid number, not boolean.")
        try:
            parsed = float(val)
        except (ValueError, TypeError):
            raise ValidationError(f"{name} must be a valid number.")
        if not math.isfinite(parsed):
            raise ValidationError(f"{name} must be a finite number.")
        return parsed
        
    lat = validate_numeric(lat_val, "lat")
    lng = validate_numeric(lng_val, "lng")
    radius_m = validate_numeric(radius_val, "radius")
    
    if not (-90 <= lat <= 90):
        raise ValidationError("Latitude must be between -90 and 90.")
    if not (-180 <= lng <= 180):
        raise ValidationError("Longitude must be between -180 and 180.")
        
    if not (MIN_RADIUS_M <= radius_m <= MAX_RADIUS_M):
        raise ValidationError(f"radius must be between {MIN_RADIUS_M} and {MAX_RADIUS_M} meters.")
        
    return lat, lng, radius_m

def radius_bounding_box(latitude, longitude, radius_m):
    """
    Calculate rectangular bounding box around (latitude, longitude) center
    clamped inside global lat/lng boundaries.
    """
    if isinstance(latitude, bool) or isinstance(longitude, bool) or isinstance(radius_m, bool):
        raise ValidationError("Coordinates and radius must not be boolean values.")
        
    try:
        lat = float(latitude)
        lng = float(longitude)
        rad = float(radius_m)
    except (ValueError, TypeError):
        raise ValidationError("Coordinates and radius must be valid numbers.")
        
    if not (math.isfinite(lat) and math.isfinite(lng) and math.isfinite(rad)):
        raise ValidationError("Coordinates and radius must be finite numbers.")
        
    delta_lat = rad / 111320.0
    
    cos_lat = math.cos(math.radians(lat))
    abs_cos_lat = abs(cos_lat)
    
    if abs_cos_lat < 0.0001:
        min_lng = -180.0
        max_lng = 180.0
    else:
        delta_lng = rad / (111320.0 * abs_cos_lat)
        if delta_lng >= 180.0:
            min_lng = -180.0
            max_lng = 180.0
        else:
            min_lng = max(-180.0, lng - delta_lng)
            max_lng = min(180.0, lng + delta_lng)
            
    min_lat = max(-90.0, lat - delta_lat)
    max_lat = min(90.0, lat + delta_lat)
    
    return min_lng, min_lat, max_lng, max_lat

def haversine_distance_m(lat1, lng1, lat2, lng2):
    """
    Calculate exact great-circle distance between two points in meters.
    """
    if any(isinstance(v, bool) for v in (lat1, lng1, lat2, lng2)):
        raise ValueError("Coordinates must not be boolean values.")
        
    try:
        lat1 = float(lat1)
        lng1 = float(lng1)
        lat2 = float(lat2)
        lng2 = float(lng2)
    except (ValueError, TypeError):
        raise ValueError("Coordinates must be valid numbers.")
        
    if not all(math.isfinite(v) for v in (lat1, lng1, lat2, lng2)):
        raise ValueError("Coordinates must be finite numbers.")
        
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
         
    a = max(0.0, min(1.0, a))
    
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_M * c
