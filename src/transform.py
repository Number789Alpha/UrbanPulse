import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Dict, Any, Optional

def calculate_aqi_pm25(pm25: float) -> int:
    """Calculate US EPA standard Air Quality Index sub-index for PM2.5 (µg/m³)."""
    if pd.isna(pm25) or pm25 < 0:
        return 0
    # Standard EPA breakpoints: (c_low, c_high, i_low, i_high)
    breakpoints = [
        (0.0, 12.0, 0, 50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300),
        (250.5, 350.4, 301, 400),
        (350.5, 500.4, 401, 500)
    ]
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= pm25 <= c_high:
            aqi = ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_low) + i_low
            return int(round(aqi))
    if pm25 > 500.4:
        return 500
    return 0

def calculate_aqi_pm10(pm10: float) -> int:
    """Calculate US EPA standard Air Quality Index sub-index for PM10 (µg/m³)."""
    if pd.isna(pm10) or pm10 < 0:
        return 0
    breakpoints = [
        (0, 54, 0, 50),
        (55, 154, 51, 100),
        (155, 254, 101, 150),
        (255, 354, 151, 200),
        (355, 424, 201, 300),
        (425, 504, 301, 400),
        (505, 604, 401, 500)
    ]
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= pm10 <= c_high:
            aqi = ((i_high - i_low) / (c_high - c_low)) * (pm10 - c_low) + i_low
            return int(round(aqi))
    if pm10 > 604:
        return 500
    return 0

def transform_air_quality_hourly(aq_data: Dict[str, Any]) -> pd.DataFrame:
    """Transform hourly air quality payload to daily aggregated metrics, incorporating real-time current values."""
    if not aq_data or ("hourly" not in aq_data and "current" not in aq_data):
        return pd.DataFrame()

    hourly = aq_data.get("hourly", {})
    df = pd.DataFrame({
        "time": hourly.get("time", []),
        "pm2_5": hourly.get("pm2_5", []),
        "pm10": hourly.get("pm10", []),
        "no2": hourly.get("nitrogen_dioxide", []),
        "ozone": hourly.get("ozone", []),
        "pollen_grass": hourly.get("grass_pollen", []),
        "pollen_birch": hourly.get("birch_pollen", []),
        "pollen_ragweed": hourly.get("ragweed_pollen", [])
    })

    if df.empty:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")

    daily_aq = df.groupby("date").agg({
        "pm2_5": "mean",
        "pm10": "mean",
        "no2": "max",
        "ozone": "max",
        "pollen_grass": "mean",
        "pollen_birch": "mean",
        "pollen_ragweed": "mean"
    }).reset_index()

    # Calculate overall daily AQI
    daily_aq["aqi_pm25"] = daily_aq["pm2_5"].apply(calculate_aqi_pm25)
    daily_aq["aqi_pm10"] = daily_aq["pm10"].apply(calculate_aqi_pm10)
    daily_aq["aqi_us"] = daily_aq[["aqi_pm25", "aqi_pm10"]].max(axis=1)
    daily_aq.drop(columns=["aqi_pm25", "aqi_pm10"], inplace=True)

    # If current air quality is provided, update today's row with live current numbers
    current = aq_data.get("current")
    if current:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str in daily_aq["date"].values:
            idx = daily_aq[daily_aq["date"] == today_str].index[0]
            if "pm2_5" in current and current["pm2_5"] is not None:
                daily_aq.at[idx, "pm2_5"] = float(current["pm2_5"])
            if "pm10" in current and current["pm10"] is not None:
                daily_aq.at[idx, "pm10"] = float(current["pm10"])
            if "nitrogen_dioxide" in current and current["nitrogen_dioxide"] is not None:
                daily_aq.at[idx, "no2"] = float(current["nitrogen_dioxide"])
            if "ozone" in current and current["ozone"] is not None:
                daily_aq.at[idx, "ozone"] = float(current["ozone"])
            if "us_aqi" in current and current["us_aqi"] is not None:
                daily_aq.at[idx, "aqi_us"] = int(current["us_aqi"])

    return daily_aq

def transform_weather_daily(weather_data: Dict[str, Any]) -> pd.DataFrame:
    """Transform daily weather forecast / archive payload to standardized DataFrame with live current injection."""
    if not weather_data or ("daily" not in weather_data and "current" not in weather_data):
        return pd.DataFrame()

    daily = weather_data.get("daily", {})
    df = pd.DataFrame({
        "date": daily.get("time", []),
        "temp_max": daily.get("temperature_2m_max", []),
        "temp_min": daily.get("temperature_2m_min", []),
        "temp_mean": daily.get("temperature_2m_mean", []),
        "rainfall_mm": daily.get("precipitation_sum", []),
        "wind_speed": daily.get("windspeed_10m_max", []),
        "humidity": daily.get("relative_humidity_2m_mean", []),
        "uv_index": daily.get("uv_index_max", []),
        "solar_radiation": daily.get("shortwave_radiation_sum", [])
    })

    # If temp_mean is missing in some endpoints, compute as average of max & min
    if "temp_mean" not in df.columns or df["temp_mean"].isnull().all():
        df["temp_mean"] = (df["temp_max"] + df["temp_min"]) / 2.0

    # If real-time current condition is provided, inject into today's row
    current = weather_data.get("current")
    if current:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if today_str in df["date"].values:
            idx = df[df["date"] == today_str].index[0]
            if "temperature_2m" in current and current["temperature_2m"] is not None:
                df.at[idx, "temp_mean"] = float(current["temperature_2m"])
            if "relative_humidity_2m" in current and current["relative_humidity_2m"] is not None:
                df.at[idx, "humidity"] = float(current["relative_humidity_2m"])
            if "wind_speed_10m" in current and current["wind_speed_10m"] is not None:
                df.at[idx, "wind_speed"] = float(current["wind_speed_10m"])
            if "uv_index" in current and current["uv_index"] is not None:
                df.at[idx, "uv_index"] = float(current["uv_index"])

    return df

def merge_and_clean_metrics(weather_df: pd.DataFrame, aq_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Merge weather and air quality datasets on date and fill defaults."""
    if weather_df.empty:
        return pd.DataFrame()

    if aq_df is not None and not aq_df.empty:
        merged = pd.merge(weather_df, aq_df, on="date", how="left")
    else:
        merged = weather_df.copy()
        for col in ["pm2_5", "pm10", "no2", "ozone", "pollen_grass", "pollen_birch", "pollen_ragweed", "aqi_us"]:
            merged[col] = np.nan

    today_str = datetime.now().strftime("%Y-%m-%d")
    merged["is_forecast"] = (merged["date"] > today_str).astype(int)

    # Clean numeric columns
    numeric_cols = [
        "temp_max", "temp_min", "temp_mean", "humidity", "rainfall_mm",
        "wind_speed", "uv_index", "solar_radiation", "pm2_5", "pm10",
        "no2", "ozone", "pollen_grass", "pollen_birch", "pollen_ragweed", "aqi_us"
    ]
    for col in numeric_cols:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").round(2)

    # Estimate default fallback AQI if PM2.5 missing (e.g. historical archive)
    if merged["aqi_us"].isnull().all() and "pm2_5" in merged.columns:
        merged["aqi_us"] = merged["pm2_5"].apply(calculate_aqi_pm25)

    return merged.dropna(subset=["date"])

    return merged.dropna(subset=["date"])
