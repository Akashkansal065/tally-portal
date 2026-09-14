import math
from typing import Optional, Tuple

def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great circle distance between two points on Earth in meters.
    Uses the Haversine formula.
    """
    # Earth radius in meters
    R = 6371000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = R * c
    return round(distance, 1)

def evaluate_checkin_proximity(
    checkin_lat: float,
    checkin_lon: float,
    shop_lat: Optional[float],
    shop_lon: Optional[float]
) -> Tuple[Optional[float], str]:
    """
    Evaluate check-in proximity relative to the established shop coordinates.
    Returns: (distance_meters, verification_status)
    Verification statuses:
      - NO_BASE_COORDINATE: Shop has no master GPS yet
      - VERIFIED_ON_SITE: <= 75m (salesperson is right at shop)
      - NEARBY: 75m - 250m (in vicinity / market lane)
      - MISMATCH_FAR: > 250m (flagged: check-in done away from shop)
    """
    if shop_lat is None or shop_lon is None:
        return (None, "NO_BASE_COORDINATE")

    dist = calculate_haversine_distance(checkin_lat, checkin_lon, shop_lat, shop_lon)
    if dist <= 75.0:
        return (dist, "VERIFIED_ON_SITE")
    elif dist <= 250.0:
        return (dist, "NEARBY")
    else:
        return (dist, "MISMATCH_FAR")
