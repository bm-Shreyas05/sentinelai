"""Indian city coordinates and distance helpers."""
import math

CITIES = {
    "Mumbai": (19.076, 72.878), "Delhi": (28.614, 77.209), "Bengaluru": (12.972, 77.595),
    "Hyderabad": (17.385, 78.487), "Chennai": (13.083, 80.271), "Kolkata": (22.573, 88.364),
    "Pune": (18.520, 73.857), "Ahmedabad": (23.023, 72.571), "Jaipur": (26.912, 75.787),
    "Surat": (21.170, 72.831), "Lucknow": (26.847, 80.947), "Kochi": (9.931, 76.267),
    "Chandigarh": (30.733, 76.779), "Nagpur": (21.146, 79.088), "Bhopal": (23.260, 77.413),
}


def haversine_km(a: str, b: str) -> float:
    if a not in CITIES or b not in CITIES or a == b:
        return 0.0
    (la1, lo1), (la2, lo2) = CITIES[a], CITIES[b]
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))
