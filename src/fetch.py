import time
import requests
from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta
from sqlalchemy import text
from src.db import engine
from src.config import PRECONFIGURED_CITIES

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

def log_api_call(endpoint: str, city_name: Optional[str], status_code: int, latency_ms: float, success: bool, error_message: Optional[str] = None):
    """Save API call metric to the api_logs table for reliability monitoring."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO api_logs (endpoint, city_name, status_code, latency_ms, success, error_message, timestamp)
                    VALUES (:endpoint, :city_name, :status_code, :latency_ms, :success, :error_message, :timestamp)
                """),
                {
                    "endpoint": endpoint,
                    "city_name": city_name,
                    "status_code": status_code,
                    "latency_ms": round(latency_ms, 2),
                    "success": 1 if success else 0,
                    "error_message": error_message,
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                }
            )
    except Exception as e:
        print(f"[API Log Error] Failed to write API metric: {e}")

def _safe_get_request(url: str, params: Dict[str, Any], max_retries: int = 3, timeout: int = 20) -> requests.Response:
    """Execute GET request with automatic exponential retry."""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            res = requests.get(url, params=params, timeout=timeout)
            res.raise_for_status()
            return res
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
    raise last_err

def geocode_city(city_name: str) -> Dict[str, Any]:
    """
    Geocode a city name to latitude, longitude, and timezone using Open-Meteo.
    Uses preconfigured cache first if available, and includes resilient alias fallbacks.
    """
    clean_name = city_name.strip()
    if clean_name in PRECONFIGURED_CITIES:
        data = PRECONFIGURED_CITIES[clean_name].copy()
        data["city_name"] = clean_name
        return data

    search_candidates = [clean_name]
    if " " in clean_name:
        search_candidates.append(clean_name.replace(" ", ""))
        search_candidates.append(clean_name.split()[0])
    if "-" in clean_name:
        search_candidates.append(clean_name.replace("-", " "))
        search_candidates.append(clean_name.split("-")[0])

    start_time = time.time()
    for candidate in search_candidates:
        params = {"name": candidate, "count": 1, "language": "en", "format": "json"}
        try:
            res = _safe_get_request(GEOCODING_URL, params, timeout=15)
            data = res.json()
            if "results" in data and len(data["results"]) > 0:
                latency = (time.time() - start_time) * 1000
                log_api_call(GEOCODING_URL, clean_name, res.status_code, latency, True)
                result = data["results"][0]
                return {
                    "city_name": clean_name,
                    "lat": result.get("latitude"),
                    "lon": result.get("longitude"),
                    "timezone": result.get("timezone", "Asia/Kolkata"),
                    "country": result.get("country", "India"),
                    "admin1": result.get("admin1", "")
                }
        except Exception:
            continue

    latency = (time.time() - start_time) * 1000
    log_api_call(GEOCODING_URL, clean_name, 404, latency, False, "No coordinates found")
    raise ValueError(f"No coordinates found for city '{clean_name}'")

def fetch_historical_archive(lat: float, lon: float, start_date: str, end_date: str, timezone: str = "Asia/Kolkata", city_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch historical daily weather archive from Open-Meteo Archive API.
    """
    start_time = time.time()
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "precipitation_sum",
            "windspeed_10m_max",
            "relative_humidity_2m_mean",
            "uv_index_max",
            "shortwave_radiation_sum"
        ],
        "timezone": timezone
    }
    try:
        res = _safe_get_request(ARCHIVE_URL, params, timeout=25)
        latency = (time.time() - start_time) * 1000
        log_api_call(ARCHIVE_URL, city_name, res.status_code, latency, True)
        return res.json()
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        status = getattr(e, "response", None)
        status_code = status.status_code if status else 500
        log_api_call(ARCHIVE_URL, city_name, status_code, latency, False, str(e))
        raise

def fetch_daily_forecast(lat: float, lon: float, past_days: int = 1, forecast_days: int = 16, timezone: str = "Asia/Kolkata", city_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch real-time current conditions and daily forecast alongside past confirmed actuals.
    """
    start_time = time.time()
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "wind_speed_10m",
            "uv_index"
        ],
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "precipitation_sum",
            "windspeed_10m_max",
            "relative_humidity_2m_mean",
            "uv_index_max",
            "shortwave_radiation_sum"
        ],
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timezone": timezone
    }
    try:
        res = _safe_get_request(FORECAST_URL, params, timeout=20)
        latency = (time.time() - start_time) * 1000
        log_api_call(FORECAST_URL, city_name, res.status_code, latency, True)
        return res.json()
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        status = getattr(e, "response", None)
        status_code = status.status_code if status else 500
        log_api_call(FORECAST_URL, city_name, status_code, latency, False, str(e))
        raise

def fetch_air_quality(lat: float, lon: float, past_days: int = 1, forecast_days: int = 7, timezone: str = "Asia/Kolkata", city_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch real-time current air quality and hourly pollutant data from Open-Meteo Air Quality API.
    """
    start_time = time.time()
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "pm10",
            "pm2_5",
            "nitrogen_dioxide",
            "ozone",
            "us_aqi"
        ],
        "hourly": [
            "pm10",
            "pm2_5",
            "nitrogen_dioxide",
            "ozone",
            "uv_index",
            "grass_pollen",
            "birch_pollen",
            "ragweed_pollen"
        ],
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timezone": timezone
    }
    try:
        res = _safe_get_request(AIR_QUALITY_URL, params, timeout=20)
        latency = (time.time() - start_time) * 1000
        log_api_call(AIR_QUALITY_URL, city_name, res.status_code, latency, True)
        return res.json()
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        status = getattr(e, "response", None)
        status_code = status.status_code if status else 500
        log_api_call(AIR_QUALITY_URL, city_name, status_code, latency, False, str(e))
        raise
