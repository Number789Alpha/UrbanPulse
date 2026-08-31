import time
import requests
from typing import Dict, Any, Optional, Tuple
from sqlalchemy import text
from src.db import engine
from src.load import get_or_create_city

STATE_ALIASES = {
    "national capital territory of delhi": "Delhi",
    "nct of delhi": "Delhi",
    "delhi": "Delhi",
    "nct": "Delhi",
    "orissa": "Odisha",
    "pondicherry": "Puducherry",
    "uttaranchal": "Uttarakhand",
    "the government of nct of delhi": "Delhi",
    "andaman & nicobar islands": "Andaman and Nicobar Islands",
    "andaman and nicobar": "Andaman and Nicobar Islands",
    "jammu & kashmir": "Jammu and Kashmir",
    "jammu and kashmir": "Jammu and Kashmir",
    "dadra and nagar haveli and daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
    "dadra & nagar haveli and daman & diu": "Dadra and Nagar Haveli and Daman and Diu",
    "telangana state": "Telangana",
    "telengana": "Telangana"
}

def normalize_state_name(state: Optional[str]) -> str:
    """Normalize state/province string to standard Indian State / Territory name."""
    if not state:
        return ""
    s_clean = str(state).strip()
    lower_s = s_clean.lower()
    if lower_s.startswith("state of "):
        s_clean = s_clean[9:].strip()
    elif lower_s.startswith("union territory of "):
        s_clean = s_clean[19:].strip()
    return STATE_ALIASES.get(s_clean.lower(), s_clean)

def detect_ip_location() -> Optional[Dict[str, Any]]:
    """
    Detect user's approximate location via high-speed IP/Network Geolocation endpoints.
    Tries multiple providers with fallback for 100% uptime.
    Returns dictionary with city_name, admin1 (state), country, lat, lon, timezone.
    """
    endpoints = [
        # Provider 1: IPWhoIs (Fast, global, JSON)
        (
            "https://ipwhois.app/json/",
            lambda r: (
                r.get("city"),
                r.get("region"),
                r.get("country"),
                float(r.get("latitude")),
                float(r.get("longitude")),
                r.get("timezone", "Asia/Kolkata"),
                r.get("isp")
            )
        ),
        # Provider 2: BigDataCloud Client IP
        (
            "https://api.bigdatacloud.net/data/client-ip",
            lambda r: (
                r.get("city") or r.get("locality"),
                r.get("countrySubdivisionName"),
                r.get("countryName"),
                float(r.get("latitude")),
                float(r.get("longitude")),
                r.get("timeZone", "Asia/Kolkata"),
                r.get("organisation")
            )
        ),
        # Provider 3: IP-API (HTTP fallback)
        (
            "http://ip-api.com/json/",
            lambda r: (
                r.get("city"),
                r.get("regionName"),
                r.get("country"),
                float(r.get("lat")),
                float(r.get("lon")),
                r.get("timezone", "Asia/Kolkata"),
                r.get("isp")
            )
        )
    ]

    for url, parser in endpoints:
        try:
            res = requests.get(url, timeout=4)
            if res.status_code == 200:
                data = res.json()
                city, state, country, lat, lon, tz, isp = parser(data)
                if city and lat and lon:
                    city = str(city).strip()
                    state = normalize_state_name(str(state).strip() if state else "")
                    country = str(country).strip() if country else "India"
                    return {
                        "city_name": city,
                        "admin1": state,
                        "country": country,
                        "lat": round(lat, 4),
                        "lon": round(lon, 4),
                        "timezone": tz or "Asia/Kolkata",
                        "isp": isp or "Network",
                        "source": "ip_network"
                    }
        except Exception:
            continue

    return None

def reverse_geocode_coordinates(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Reverse-geocode exact GPS coordinates (lat, lon) to human-readable city, state, country.
    Uses BigDataCloud reverse geocode API with OpenStreetMap Nominatim fallback.
    """
    # 1. BigDataCloud Client Reverse Geocode API (Extremely accurate, no API key required)
    try:
        url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=en"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            city = data.get("locality") or data.get("city") or data.get("principalSubdivision")
            admin1 = normalize_state_name(data.get("principalSubdivision", ""))
            country = data.get("countryName", "India")
            locality = data.get("locality", "")
            district = ""
            for admin in data.get("localityInfo", {}).get("administrative", []):
                desc = str(admin.get("description", "")).lower()
                name = str(admin.get("name", "")).strip()
                if "district" in desc and name:
                    district = name.replace(" district", "").replace(" District", "").strip()
                    break
            if city:
                return {
                    "city_name": str(city).strip(),
                    "locality": str(locality).strip() if locality else str(city).strip(),
                    "district": district or "",
                    "admin1": admin1.strip(),
                    "country": str(country).strip(),
                    "lat": round(float(lat), 4),
                    "lon": round(float(lon), 4),
                    "timezone": "Asia/Kolkata" if "India" in country else "UTC",
                    "source": "gps_bigdatacloud"
                }
    except Exception:
        pass

    # 2. OSM Nominatim Reverse Geocoder fallback
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        headers = {"User-Agent": "UrbanPulse-Environmental-Intelligence/1.0"}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            addr = data.get("address", {})
            city = (
                addr.get("city")
                or addr.get("town")
                or addr.get("village")
                or addr.get("city_district")
                or addr.get("municipality")
                or addr.get("suburb")
                or addr.get("county")
            )
            district = (addr.get("state_district") or addr.get("county") or "").replace(" district", "").replace(" District", "").strip()
            admin1 = normalize_state_name(addr.get("state") or addr.get("region") or "")
            country = addr.get("country", "India")
            if city:
                return {
                    "city_name": str(city).strip(),
                    "locality": str(addr.get("suburb", city)).strip(),
                    "district": district or "",
                    "admin1": admin1.strip(),
                    "country": str(country).strip(),
                    "lat": round(float(lat), 4),
                    "lon": round(float(lon), 4),
                    "timezone": "Asia/Kolkata" if "India" in country else "UTC",
                    "source": "gps_nominatim"
                }
    except Exception:
        pass

    return None

def resolve_and_register_location(
    lat: float,
    lon: float,
    preferred_city: Optional[str] = None,
    admin1: Optional[str] = None,
    country: Optional[str] = None,
    auto_etl: bool = True
) -> Dict[str, Any]:
    """
    Given coordinates, resolves or accepts city metadata, registers into SQLite database,
    and automatically runs daily ETL if metrics don't exist yet.
    Ensures state-level disambiguation and exact coordinate assignment.
    """
    admin1_clean = normalize_state_name(admin1)
    district_clean = ""
    resolved = None
    if not preferred_city:
        resolved = reverse_geocode_coordinates(lat, lon)
        if resolved:
            city_name = resolved["city_name"]
            admin1_clean = resolved.get("admin1") or admin1_clean or ""
            district_clean = resolved.get("district") or ""
            country = resolved.get("country") or country or "India"
        else:
            city_name = f"Location ({lat:.2f}N, {lon:.2f}E)"
    else:
        city_name = preferred_city

    clean_city = city_name.strip()
    with engine.begin() as conn:
        # Check if matching city exists in DB for this specific state
        if admin1_clean:
            row = conn.execute(
                text("SELECT city_id, city_name, latitude, longitude, timezone, country, admin1 FROM cities WHERE LOWER(city_name) = LOWER(:name) AND LOWER(admin1) = LOWER(:admin1)"),
                {"name": clean_city, "admin1": admin1_clean}
            ).fetchone()
        else:
            row = conn.execute(
                text("SELECT city_id, city_name, latitude, longitude, timezone, country, admin1 FROM cities WHERE LOWER(city_name) = LOWER(:name)"),
                {"name": clean_city}
            ).fetchone()

        if row:
            # Update coordinates to exact high-precision GPS if provided
            conn.execute(
                text("UPDATE cities SET latitude = :lat, longitude = :lon, admin1 = :admin1 WHERE city_id = :city_id"),
                {"lat": lat, "lon": lon, "admin1": admin1_clean or row[6] or "", "city_id": row[0]}
            )
            city_dict = {
                "city_id": row[0],
                "city_name": row[1],
                "lat": lat,
                "lon": lon,
                "timezone": row[4],
                "country": row[5],
                "admin1": admin1_clean or row[6] or "",
                "district": district_clean
            }
        else:
            # Insert new city with exact detected coordinates and state
            tz = "Asia/Kolkata" if country and "India" in country else "UTC"
            conn.execute(
                text("""
                    INSERT INTO cities (city_name, latitude, longitude, timezone, country, admin1)
                    VALUES (:city_name, :lat, :lon, :timezone, :country, :admin1)
                """),
                {
                    "city_name": clean_city,
                    "lat": lat,
                    "lon": lon,
                    "timezone": tz,
                    "country": country or "India",
                    "admin1": admin1_clean or ""
                }
            )
            city_id = conn.execute(
                text("SELECT city_id FROM cities WHERE LOWER(city_name) = LOWER(:name) AND (LOWER(admin1) = LOWER(:admin1) OR :admin1 = '')"),
                {"name": clean_city, "admin1": admin1_clean}
            ).scalar()

            city_dict = {
                "city_id": city_id,
                "city_name": clean_city,
                "lat": lat,
                "lon": lon,
                "timezone": tz,
                "country": country or "India",
                "admin1": admin1_clean or "",
                "district": district_clean
            }

    # Auto-run ETL if no data exists in DB yet
    if auto_etl:
        with engine.connect() as conn:
            cnt = conn.execute(
                text("SELECT COUNT(*) FROM raw_daily_metrics WHERE city_id = :city_id"),
                {"city_id": city_dict["city_id"]}
            ).scalar()

        if cnt == 0:
            try:
                from daily_etl import run_city_etl
                run_city_etl(city_dict["city_name"], generate_pdf=False, force_ai=True)
            except Exception as e:
                print(f"[Auto-ETL Notice] Initial fetch for {city_dict['city_name']}: {e}")

    return city_dict

    return city_dict
