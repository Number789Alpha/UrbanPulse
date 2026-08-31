import pandas as pd
from typing import Dict, Any, Optional
from sqlalchemy import text
from src.db import engine
from src.fetch import geocode_city

def get_or_create_city(city_name: str, admin1: Optional[str] = None) -> Dict[str, Any]:
    """
    Look up city in `cities` table with state-level disambiguation; if not found, geocode and insert it.
    Returns city dict with city_id, lat, lon, timezone, etc.
    """
    clean_name = city_name.strip()
    from src.geolocation import normalize_state_name
    admin1_norm = normalize_state_name(admin1) if admin1 else ""
    
    with engine.begin() as conn:
        if admin1_norm and admin1_norm.lower() != "all states & territories":
            result = conn.execute(
                text("SELECT city_id, city_name, latitude, longitude, timezone, country, admin1 FROM cities WHERE LOWER(city_name) = LOWER(:name) AND LOWER(admin1) = LOWER(:admin1)"),
                {"name": clean_name, "admin1": admin1_norm}
            ).fetchone()
        else:
            result = conn.execute(
                text("SELECT city_id, city_name, latitude, longitude, timezone, country, admin1 FROM cities WHERE LOWER(city_name) = LOWER(:name)"),
                {"name": clean_name}
            ).fetchone()

        if result:
            return {
                "city_id": result[0],
                "city_name": result[1],
                "lat": result[2],
                "lon": result[3],
                "timezone": result[4],
                "country": result[5],
                "admin1": result[6]
            }

        # Not found: geocode city with state context and insert
        search_query = f"{clean_name}, {admin1_norm}, India" if admin1_norm and admin1_norm.lower() != "all states & territories" else clean_name
        geo = geocode_city(search_query)
        admin1_geo = normalize_state_name(geo.get("admin1", "")) or admin1_norm

        insert_res = conn.execute(
            text("""
                INSERT INTO cities (city_name, latitude, longitude, timezone, country, admin1)
                VALUES (:city_name, :lat, :lon, :timezone, :country, :admin1)
            """),
            {
                "city_name": geo["city_name"],
                "lat": geo["lat"],
                "lon": geo["lon"],
                "timezone": geo["timezone"],
                "country": geo.get("country", "India"),
                "admin1": admin1_geo or geo.get("admin1")
            }
        )

        city_id = conn.execute(
            text("SELECT city_id FROM cities WHERE LOWER(city_name) = LOWER(:name) AND (LOWER(admin1) = LOWER(:admin1) OR :admin1 = '')"),
            {"name": geo["city_name"], "admin1": admin1_geo}
        ).scalar()

        geo["city_id"] = city_id
        geo["admin1"] = admin1_geo or geo.get("admin1")
        return geo

def upsert_daily_metrics(city_id: int, df: pd.DataFrame) -> int:
    """
    Upsert batch daily metrics into raw_daily_metrics.
    Uses ON CONFLICT(city_id, date) to safely overwrite/update existing records without duplicates.
    """
    if df.empty:
        return 0

    inserted_count = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            params = {
                "city_id": city_id,
                "date": str(row["date"]),
                "temp_max": None if pd.isna(row.get("temp_max")) else float(row["temp_max"]),
                "temp_min": None if pd.isna(row.get("temp_min")) else float(row["temp_min"]),
                "temp_mean": None if pd.isna(row.get("temp_mean")) else float(row["temp_mean"]),
                "humidity": None if pd.isna(row.get("humidity")) else float(row["humidity"]),
                "rainfall_mm": None if pd.isna(row.get("rainfall_mm")) else float(row["rainfall_mm"]),
                "wind_speed": None if pd.isna(row.get("wind_speed")) else float(row["wind_speed"]),
                "uv_index": None if pd.isna(row.get("uv_index")) else float(row["uv_index"]),
                "solar_radiation": None if pd.isna(row.get("solar_radiation")) else float(row["solar_radiation"]),
                "pm2_5": None if pd.isna(row.get("pm2_5")) else float(row["pm2_5"]),
                "pm10": None if pd.isna(row.get("pm10")) else float(row["pm10"]),
                "no2": None if pd.isna(row.get("no2")) else float(row["no2"]),
                "ozone": None if pd.isna(row.get("ozone")) else float(row["ozone"]),
                "pollen_grass": None if pd.isna(row.get("pollen_grass")) else float(row["pollen_grass"]),
                "pollen_birch": None if pd.isna(row.get("pollen_birch")) else float(row["pollen_birch"]),
                "pollen_ragweed": None if pd.isna(row.get("pollen_ragweed")) else float(row["pollen_ragweed"]),
                "aqi_us": None if pd.isna(row.get("aqi_us")) else int(row["aqi_us"]),
                "is_forecast": int(row.get("is_forecast", 0))
            }

            stmt = text("""
                INSERT INTO raw_daily_metrics (
                    city_id, date, temp_max, temp_min, temp_mean, humidity, rainfall_mm,
                    wind_speed, uv_index, solar_radiation, pm2_5, pm10, no2, ozone,
                    pollen_grass, pollen_birch, pollen_ragweed, aqi_us, is_forecast
                ) VALUES (
                    :city_id, :date, :temp_max, :temp_min, :temp_mean, :humidity, :rainfall_mm,
                    :wind_speed, :uv_index, :solar_radiation, :pm2_5, :pm10, :no2, :ozone,
                    :pollen_grass, :pollen_birch, :pollen_ragweed, :aqi_us, :is_forecast
                )
                ON CONFLICT(city_id, date) DO UPDATE SET
                    temp_max = COALESCE(excluded.temp_max, raw_daily_metrics.temp_max),
                    temp_min = COALESCE(excluded.temp_min, raw_daily_metrics.temp_min),
                    temp_mean = COALESCE(excluded.temp_mean, raw_daily_metrics.temp_mean),
                    humidity = COALESCE(excluded.humidity, raw_daily_metrics.humidity),
                    rainfall_mm = COALESCE(excluded.rainfall_mm, raw_daily_metrics.rainfall_mm),
                    wind_speed = COALESCE(excluded.wind_speed, raw_daily_metrics.wind_speed),
                    uv_index = COALESCE(excluded.uv_index, raw_daily_metrics.uv_index),
                    solar_radiation = COALESCE(excluded.solar_radiation, raw_daily_metrics.solar_radiation),
                    pm2_5 = COALESCE(excluded.pm2_5, raw_daily_metrics.pm2_5),
                    pm10 = COALESCE(excluded.pm10, raw_daily_metrics.pm10),
                    no2 = COALESCE(excluded.no2, raw_daily_metrics.no2),
                    ozone = COALESCE(excluded.ozone, raw_daily_metrics.ozone),
                    pollen_grass = COALESCE(excluded.pollen_grass, raw_daily_metrics.pollen_grass),
                    pollen_birch = COALESCE(excluded.pollen_birch, raw_daily_metrics.pollen_birch),
                    pollen_ragweed = COALESCE(excluded.pollen_ragweed, raw_daily_metrics.pollen_ragweed),
                    aqi_us = COALESCE(excluded.aqi_us, raw_daily_metrics.aqi_us),
                    is_forecast = excluded.is_forecast,
                    fetched_at = CURRENT_TIMESTAMP
            """)
            conn.execute(stmt, params)
            inserted_count += 1

    return inserted_count
