from rest_framework.filters import BaseFilterBackend
from rest_framework.exceptions import ValidationError
from .geo_utils import (
    parse_bbox,
    parse_radius_params,
    radius_bounding_box,
    haversine_distance_m
)

class GeoFilterBackend(BaseFilterBackend):
    """
    Geographic Filtering Backend for DRF catalog listing.
    Supports bounding box (bbox) and center-radius filters.
    """
    def filter_queryset(self, request, queryset, view):
        query_params = request.query_params
        
        bbox_val = query_params.get("bbox")
        
        has_radius_params = (
            query_params.get("lat") is not None or
            query_params.get("lng") is not None or
            query_params.get("radius") is not None
        )
        
        # 1. Geo mode conflicts validation
        if bbox_val is not None and has_radius_params:
            raise ValidationError("Cannot use bbox and radius filters together. Please specify only one geographic filter mode.")
            
        # 2. Bounding Box Mode (Returns lazy QuerySet)
        if bbox_val is not None:
            min_lng, min_lat, max_lng, max_lat = parse_bbox(bbox_val)
            
            queryset = queryset.filter(
                latitude__isnull=False,
                longitude__isnull=False,
                latitude__gte=min_lat,
                latitude__lte=max_lat,
                longitude__gte=min_lng,
                longitude__lte=max_lng
            )
            return queryset
            
        # 3. Radius Mode (Returns evaluated Python list after database bounding-box prefilter)
        radius_parsed = parse_radius_params(query_params)
        if radius_parsed is not None:
            lat, lng, radius_m = radius_parsed
            
            # Calculate rectangular bounding box deltas
            min_lng, min_lat, max_lng, max_lat = radius_bounding_box(lat, lng, radius_m)
            
            # Database prefilter
            prefiltered_qs = queryset.filter(
                latitude__isnull=False,
                longitude__isnull=False,
                latitude__gte=min_lat,
                latitude__lte=max_lat,
                longitude__gte=min_lng,
                longitude__lte=max_lng
            )
            
            # Evaluate candidate set into a list
            candidates = list(prefiltered_qs)
            
            matches = []
            for service in candidates:
                try:
                    s_lat = float(service.latitude)
                    s_lng = float(service.longitude)
                except (ValueError, TypeError):
                    continue
                    
                dist = haversine_distance_m(lat, lng, s_lat, s_lng)
                if dist <= radius_m:
                    service.distance_m = round(dist)
                    matches.append(service)
                    
            # Deterministic sorting or preserving explicit ordering
            ordering_param = query_params.get("ordering")
            if ordering_param:
                # Preserve the QuerySet ordering already applied by OrderingFilter
                pass
            else:
                # Nearest-first distance ordering with stable PK tie-break
                matches.sort(key=lambda s: (s.distance_m, s.id))
                
            return matches
            
        # 4. No geo parameters
        return queryset
