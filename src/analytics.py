import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from src.db import engine
from src.config import THRESHOLDS

def compute_environmental_score(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute overall Environmental Score (0-100) and component sub-scores.
    Higher score = healthier, cleaner, more comfortable environment.
    """
    aqi = metrics.get("aqi_us") or 50
    temp_max = metrics.get("temp_max") or 25.0
    temp_min = metrics.get("temp_min") or 18.0
    temp_mean = metrics.get("temp_mean") or ((temp_max + temp_min) / 2.0)
    humidity = metrics.get("humidity") or 50.0
    rainfall = metrics.get("rainfall_mm") or 0.0
    uv = metrics.get("uv_index") or 5.0

    # 1. Air Quality Sub-Score (0-100): 100 = 0 AQI, 0 = 300+ AQI
    if aqi <= 50:
        air_score = 100 - (aqi / 50.0) * 15 # 100 -> 85
    elif aqi <= 100:
        air_score = 85 - ((aqi - 50) / 50.0) * 25 # 85 -> 60
    elif aqi <= 200:
        air_score = 60 - ((aqi - 100) / 100.0) * 35 # 60 -> 25
    else:
        air_score = max(0, 25 - ((aqi - 200) / 100.0) * 25)

    # 2. Thermal Comfort Sub-Score (0-100): Ideal ~22°C - 26°C
    if 20.0 <= temp_mean <= 26.0:
        thermal_score = 100
    elif temp_mean > 26.0:
        thermal_score = max(0, 100 - (temp_mean - 26.0) * 5.0)
    else:
        thermal_score = max(0, 100 - (20.0 - temp_mean) * 4.5)

    # 3. Humidity Balance Sub-Score (0-100): Ideal ~40% - 60%
    if 40.0 <= humidity <= 60.0:
        humidity_score = 100
    elif humidity > 60.0:
        humidity_score = max(0, 100 - (humidity - 60.0) * 2.2)
    else:
        humidity_score = max(0, 100 - (40.0 - humidity) * 2.2)

    # 4. UV Safety Sub-Score (0-100): 0-2 (Low) = 100, 11+ (Extreme) = 10
    uv_score = max(0, min(100, 100 - (uv / 11.0) * 75))

    # 5. Precipitation Stability (0-100)
    rain_score = max(0, 100 - (rainfall * 2.5))

    # Weighted Composite Environmental Score
    overall_score = (
        0.35 * air_score +
        0.25 * thermal_score +
        0.15 * humidity_score +
        0.15 * uv_score +
        0.10 * rain_score
    )
    overall_score = round(max(0.0, min(100.0, overall_score)), 1)

    if overall_score >= 80:
        category = "Optimal"
        color = "#10b981" # Green
    elif overall_score >= 60:
        category = "Good"
        color = "#3b82f6" # Blue
    elif overall_score >= 40:
        category = "Moderate"
        color = "#f59e0b" # Amber
    else:
        category = "Degraded"
        color = "#ef4444" # Red

    return {
        "score": overall_score,
        "category": category,
        "color": color,
        "components": {
            "air_quality": round(air_score, 1),
            "thermal_comfort": round(thermal_score, 1),
            "humidity_balance": round(humidity_score, 1),
            "uv_safety": round(uv_score, 1),
            "rain_stability": round(rain_score, 1)
        }
    }

def compute_activity_index(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute activity-specific suitability scores (0-100%), pros, cons, and recommended time windows
    across 6 core outdoor activities.
    """
    aqi = float(metrics.get("aqi_us") or 50.0)
    temp_max = float(metrics.get("temp_max") or 25.0)
    temp_min = float(metrics.get("temp_min") or 20.0)
    humidity = float(metrics.get("humidity") or 50.0)
    wind_speed = float(metrics.get("wind_speed") or 10.0)
    rainfall = float(metrics.get("rainfall_mm") or 0.0)
    solar = float(metrics.get("solar_radiation") or 15.0)
    uv = float(metrics.get("uv_index") or 5.0)
    pm25 = float(metrics.get("pm2_5") or 20.0)

    # 1. Jogging / Running Score
    jog_aqi_penalty = min(55, (aqi / 150.0) * 55)
    jog_temp_penalty = max(0, (temp_max - 23.0) * 3.8) if temp_max > 23 else max(0, (12.0 - temp_max) * 3.2)
    jog_rain_penalty = min(50, rainfall * 6.0)
    jog_humidity_penalty = max(0, (humidity - 65.0) * 0.9)
    jog_score = max(0, min(100, 100 - (jog_aqi_penalty + jog_temp_penalty + jog_rain_penalty + jog_humidity_penalty)))

    jog_pros = []
    jog_cons = []
    if aqi <= 50: jog_pros.append("Clean air with low particulate load (AQI " + str(int(aqi)) + ")")
    else: jog_cons.append("Elevated AQI (" + str(int(aqi)) + ") increases respiratory strain during cardio")
    if 16 <= temp_max <= 24: jog_pros.append(f"Optimal running temperature ({temp_max:.1f}°C)")
    elif temp_max > 28: jog_cons.append(f"High daytime temperature ({temp_max:.1f}°C) poses dehydration risk")
    elif temp_max < 12: jog_cons.append(f"Chilly air ({temp_max:.1f}°C) may cause airway constriction")
    if rainfall == 0: jog_pros.append("Dry running tracks with zero slip hazard")
    else: jog_cons.append(f"Wet precipitation ({rainfall:.1f} mm) creates slippery surfaces")
    if humidity < 65: jog_pros.append(f"Comfortable sweat evaporation (Humidity {humidity:.0f}%)")
    else: jog_cons.append(f"High humidity ({humidity:.0f}%) hampers thermal cooling")

    # 2. Cycling & Commuting Score
    cycle_wind_penalty = min(45, max(0, (wind_speed - 15.0) * 2.8))
    cycle_rain_penalty = min(60, rainfall * 7.5)
    cycle_aqi_penalty = min(40, (aqi / 180.0) * 40)
    cycle_temp_penalty = max(0, (temp_max - 28.0) * 3.0) if temp_max > 28 else max(0, (10.0 - temp_max) * 3.0)
    cycle_score = max(0, min(100, 100 - (cycle_wind_penalty + cycle_rain_penalty + cycle_aqi_penalty + cycle_temp_penalty)))

    cycle_pros = []
    cycle_cons = []
    if wind_speed <= 15: cycle_pros.append(f"Gentle headwinds / crosswinds ({wind_speed:.1f} km/h)")
    else: cycle_cons.append(f"Strong headwinds ({wind_speed:.1f} km/h) require extra pedaling effort")
    if rainfall == 0: cycle_pros.append("High road traction and clear line of sight")
    else: cycle_cons.append(f"Rainfall ({rainfall:.1f} mm) increases braking distance and spray")
    if aqi <= 65: cycle_pros.append(f"Moderate to good air quality for sustained riding")
    else: cycle_cons.append(f"PM2.5 exposure ({pm25:.1f} µg/m³) along traffic routes")

    # 3. Outdoor Sports & Field Athletics (Cricket, Football, Tennis)
    sport_temp_pen = max(0, (temp_max - 26.0) * 3.2) if temp_max > 26 else max(0, (14.0 - temp_max) * 2.5)
    sport_rain_pen = min(70, rainfall * 8.0)
    sport_aqi_pen = min(45, (aqi / 160.0) * 45)
    sport_uv_pen = min(20, max(0, (uv - 6.0) * 4.0))
    sports_score = max(0, min(100, 100 - (sport_temp_pen + sport_rain_pen + sport_aqi_pen + sport_uv_pen)))

    sports_pros = []
    sports_cons = []
    if rainfall == 0: sports_pros.append("Dry turf / court conditions with true ball bounce")
    else: sports_cons.append(f"Field waterlogging risk ({rainfall:.1f} mm rain)")
    if uv < 6: sports_pros.append("Safe solar irradiance levels for prolonged field play")
    else: sports_cons.append(f"High UV radiation (Index {uv:.1f}) requires sunscreen and hydration breaks")
    if temp_max <= 28: sports_pros.append(f"Manageable thermal load for high-intensity matches")
    else: sports_cons.append(f"Heat exhaustion risk during afternoon hours ({temp_max:.1f}°C)")

    # 4. Walking & Senior Citizen Strolls
    walk_aqi_pen = min(50, (aqi / 140.0) * 50)
    walk_temp_pen = max(0, (temp_max - 27.0) * 3.0) if temp_max > 27 else max(0, (12.0 - temp_max) * 2.5)
    walk_rain_pen = min(60, rainfall * 6.5)
    walk_uv_pen = min(25, max(0, (uv - 5.0) * 3.5))
    walk_score = max(0, min(100, 100 - (walk_aqi_pen + walk_temp_pen + walk_rain_pen + walk_uv_pen)))

    walk_pros = []
    walk_cons = []
    if aqi <= 60: walk_pros.append("Pleasant atmospheric purity suitable for elderly & families")
    else: walk_cons.append(f"Airborne particulates (PM2.5: {pm25:.1f} µg/m³) may irritate sensitive lungs")
    if 18 <= temp_max <= 27: walk_pros.append(f"Comfortable walking climate ({temp_max:.1f}°C)")
    else: walk_cons.append(f"Extreme temperatures ({temp_max:.1f}°C) may cause fatigue")
    if rainfall == 0: walk_pros.append("Pavement and parks are dry and safe")
    else: walk_cons.append("Wet pathways pose slipping hazard for seniors")

    # 5. Photography & Sightseeing
    photo_rain_penalty = min(70, rainfall * 8.0)
    photo_aqi_penalty = min(40, (aqi / 160.0) * 40)
    photo_solar_bonus = min(20, (solar / 20.0) * 20)
    photo_score = max(0, min(100, 80 + photo_solar_bonus - (photo_rain_penalty + photo_aqi_penalty)))

    photo_pros = []
    photo_cons = []
    if solar >= 12 and rainfall == 0: photo_pros.append(f"Crisp ambient natural lighting (Solar: {solar:.1f} MJ/m²)")
    if aqi <= 50: photo_pros.append("High atmospheric transparency & horizon visibility")
    else: photo_cons.append("Haze/smog may reduce distant landscape clarity")
    if rainfall > 0: photo_cons.append(f"Overcast skies and rain ({rainfall:.1f} mm) may obscure optics")

    # 6. Open-Air Dining & Leisure Gatherings
    dine_rain_pen = min(80, rainfall * 10.0)
    dine_temp_pen = max(0, (temp_max - 28.0) * 3.5) if temp_max > 28 else max(0, (15.0 - temp_max) * 3.0)
    dine_wind_pen = min(40, max(0, (wind_speed - 16.0) * 3.0))
    dine_aqi_pen = min(30, (aqi / 150.0) * 30)
    dine_score = max(0, min(100, 100 - (dine_rain_pen + dine_temp_pen + dine_wind_pen + dine_aqi_pen)))

    dine_pros = []
    dine_cons = []
    if rainfall == 0 and wind_speed <= 15: dine_pros.append("Calm winds and dry patios ideal for al fresco dining")
    if 20 <= temp_max <= 27: dine_pros.append(f"Comfortable evening ambiance ({temp_max:.1f}°C)")
    if rainfall > 0: dine_cons.append("Rain requires covered terrace or indoor seating")
    if wind_speed > 18: dine_cons.append(f"Breezy gusts ({wind_speed:.1f} km/h) may disrupt outdoor table setups")

    def _get_badge(score: float):
        if score >= 80:
            return {"label": "Ideal", "color": "#10b981", "advice": "Prime environmental conditions across all metrics"}
        elif score >= 60:
            return {"label": "Good", "color": "#3b82f6", "advice": "Favorable outdoor window with standard hydration"}
        elif score >= 40:
            return {"label": "Moderate Caution", "color": "#f59e0b", "advice": "Schedule around early morning or post-sunset"}
        else:
            return {"label": "Avoid", "color": "#ef4444", "advice": "Unfavorable environmental stress; indoor alternative advised"}

    return {
        "jogging": {
            "name": "Jogging & Running",
            "score": round(jog_score, 1),
            **_get_badge(jog_score),
            "pros": jog_pros or ["Standard running baseline"],
            "cons": jog_cons or ["No significant environmental risks"],
            "best_window": "05:30 AM – 08:30 AM (Cooler & low UV)" if temp_max > 25 else "07:00 AM – 10:00 AM"
        },
        "cycling": {
            "name": "Cycling & Commuting",
            "score": round(cycle_score, 1),
            **_get_badge(cycle_score),
            "pros": cycle_pros or ["Standard road cycling conditions"],
            "cons": cycle_cons or ["No severe wind or rain barriers"],
            "best_window": "06:00 AM – 09:00 AM or 17:30 – 19:30"
        },
        "outdoor_sports": {
            "name": "Outdoor Sports & Athletics",
            "score": round(sports_score, 1),
            **_get_badge(sports_score),
            "pros": sports_pros or ["Playable court and field conditions"],
            "cons": sports_cons or ["Standard game precautions"],
            "best_window": "06:30 AM – 09:30 AM or 16:30 – 18:30"
        },
        "walking": {
            "name": "Walking & Senior Strolls",
            "score": round(walk_score, 1),
            **_get_badge(walk_score),
            "pros": walk_pros or ["Comfortable pedestrian conditions"],
            "cons": walk_cons or ["No critical hazards"],
            "best_window": "06:00 AM – 08:30 AM or 17:00 – 19:00"
        },
        "photography": {
            "name": "Photography & Sightseeing",
            "score": round(photo_score, 1),
            **_get_badge(photo_score),
            "pros": photo_pros or ["Acceptable daytime outdoor lighting"],
            "cons": photo_cons or ["Standard exposure adjustments needed"],
            "best_window": "06:30 AM – 09:00 AM (Golden Hour) & 17:00 – 18:30"
        },
        "open_air_dining": {
            "name": "Open-Air Dining & Leisure",
            "score": round(dine_score, 1),
            **_get_badge(dine_score),
            "pros": dine_pros or ["Pleasant patio environment"],
            "cons": dine_cons or ["Check local breeze conditions"],
            "best_window": "18:00 – 22:00 (Evening breeze)"
        }
    }

def compute_city_risk_score(metrics: Dict[str, Any], z_scores: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Compute multi-hazard City Risk Score across Heat, Air Quality, Flooding, and Wind storms.
    """
    temp_max = metrics.get("temp_max") or 25.0
    pm25 = metrics.get("pm2_5") or 25.0
    aqi = metrics.get("aqi_us") or 50
    rainfall = metrics.get("rainfall_mm") or 0.0
    wind_speed = metrics.get("wind_speed") or 10.0
    uv = metrics.get("uv_index") or 5.0

    z_scores = z_scores or {}
    pm25_z = z_scores.get("pm2_5_zscore", 0.0)
    temp_z = z_scores.get("temp_zscore", 0.0)
    rain_z = z_scores.get("rainfall_zscore", 0.0)

    alerts: List[Dict[str, str]] = []

    # 1. Heatwave Risk
    if temp_max >= THRESHOLDS["heatwave_severe_temp"] or temp_z >= 2.5:
        heat_risk = "Severe"
        alerts.append({"type": "Heat Alert", "severity": "Severe", "msg": f"Extreme heatwave warning: {temp_max}°C (+{temp_z:.1f}σ anomaly). Stay hydrated."})
    elif temp_max >= THRESHOLDS["heatwave_high_temp"] or temp_z >= 1.8:
        heat_risk = "High"
        alerts.append({"type": "Heat Warning", "severity": "High", "msg": f"Elevated thermal stress: {temp_max}°C. Limit afternoon exposure."})
    elif temp_max >= 32.0:
        heat_risk = "Moderate"
    else:
        heat_risk = "Low"

    # 2. Air Quality / Smog Risk
    if pm25 >= THRESHOLDS["air_severe_pm25"] or aqi >= 250 or pm25_z >= 2.5:
        air_risk = "Severe"
        alerts.append({"type": "Air Hazard", "severity": "Severe", "msg": f"Hazardous air pollution (PM2.5: {pm25} µg/m³, AQI: {aqi}). N95 masks advised."})
    elif pm25 >= THRESHOLDS["air_high_pm25"] or aqi >= 150 or pm25_z >= 1.8:
        air_risk = "High"
        alerts.append({"type": "Air Advisory", "severity": "High", "msg": f"Unhealthy air for sensitive groups (AQI: {aqi}). Keep windows closed."})
    elif pm25 >= 35.0 or aqi >= 100:
        air_risk = "Moderate"
    else:
        air_risk = "Low"

    # 3. Flash Flood / Heavy Rain Risk
    if rainfall >= THRESHOLDS["flood_severe_rain"] or rain_z >= 2.5:
        rain_risk = "Severe"
        alerts.append({"type": "Flood Warning", "severity": "Severe", "msg": f"Torrential precipitation ({rainfall} mm). Waterlogging & commute disruptions likely."})
    elif rainfall >= THRESHOLDS["flood_high_rain"] or rain_z >= 1.8:
        rain_risk = "High"
        alerts.append({"type": "Rain Advisory", "severity": "High", "msg": f"Heavy rainfall ({rainfall} mm). Plan travel accordingly."})
    elif rainfall >= 10.0:
        rain_risk = "Moderate"
    else:
        rain_risk = "Low"

    # 4. Windstorm Risk
    if wind_speed >= THRESHOLDS["storm_severe_wind"]:
        wind_risk = "Severe"
        alerts.append({"type": "Gale Warning", "severity": "Severe", "msg": f"Severe wind gusts ({wind_speed} km/h). Secure outdoor items."})
    elif wind_speed >= THRESHOLDS["storm_high_wind"]:
        wind_risk = "High"
        alerts.append({"type": "Wind Advisory", "severity": "High", "msg": f"High winds ({wind_speed} km/h). Caution for cycling & high-profile vehicles."})
    elif wind_speed >= 25.0:
        wind_risk = "Moderate"
    else:
        wind_risk = "Low"

    # Overall Composite Risk Band
    risk_rank = {"Severe": 4, "High": 3, "Moderate": 2, "Low": 1}
    max_rank = max(risk_rank[heat_risk], risk_rank[air_risk], risk_rank[rain_risk], risk_rank[wind_risk])
    rank_to_label = {4: "Severe", 3: "High", 2: "Moderate", 1: "Low"}
    composite_risk = rank_to_label[max_rank]

    risk_colors = {
        "Severe": "#dc2626", # Crimson
        "High": "#ea580c",   # Orange
        "Moderate": "#f59e0b", # Amber
        "Low": "#10b981"     # Emerald
    }

    return {
        "composite_risk": composite_risk,
        "risk_color": risk_colors[composite_risk],
        "categories": {
            "heat": {"level": heat_risk, "color": risk_colors[heat_risk]},
            "air": {"level": air_risk, "color": risk_colors[air_risk]},
            "rain": {"level": rain_risk, "color": risk_colors[rain_risk]},
            "wind": {"level": wind_risk, "color": risk_colors[wind_risk]}
        },
        "alerts": alerts,
        "active_alerts_count": len(alerts)
    }

def get_historical_and_anomaly_stats(city_id: int, target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Query database for rolling averages, 30-day standard deviations, Z-score anomalies,
    and 90-day percentile ranks for the given city and date.
    """
    with engine.connect() as conn:
        # Fetch the target row with rolling context
        if target_date:
            date_filter = "AND m.date <= :target_date"
            params = {"city_id": city_id, "target_date": target_date}
        else:
            date_filter = ""
            params = {"city_id": city_id}

        query = text(f"""
            SELECT 
                m.date, m.temp_max, m.temp_min, m.temp_mean, m.humidity, m.rainfall_mm,
                m.wind_speed, m.uv_index, m.solar_radiation, m.pm2_5, m.pm10, m.aqi_us,
                m.no2, m.ozone, m.pollen_grass, m.is_forecast
            FROM raw_daily_metrics m
            WHERE m.city_id = :city_id {date_filter}
            ORDER BY m.date DESC
            LIMIT 90
        """)
        df = pd.read_sql(query, conn, params=params)

    if df.empty:
        return {}

    latest_row = df.iloc[0].to_dict()

    # Calculate rolling baseline stats on the fly for complete precision
    past_30 = df.head(30)
    past_7 = df.head(7)

    def calc_stats(series: pd.Series, val: float):
        clean = series.dropna()
        if len(clean) < 2:
            return {"7d_avg": val, "30d_avg": val, "std": 0.0, "zscore": 0.0, "diff_pct": 0.0}
        avg_7 = float(clean.head(7).mean())
        avg_30 = float(clean.mean())
        std_30 = float(clean.std(ddof=1))
        zscore = float((val - avg_30) / std_30) if std_30 > 0.001 else 0.0
        diff_pct = float(((val - avg_7) / avg_7) * 100.0) if avg_7 > 0.001 else 0.0
        return {
            "7d_avg": round(avg_7, 2),
            "30d_avg": round(avg_30, 2),
            "std": round(std_30, 2),
            "zscore": round(zscore, 2),
            "diff_pct": round(diff_pct, 1)
        }

    pm25_val = latest_row.get("pm2_5") or 0.0
    temp_val = latest_row.get("temp_max") or 0.0
    rain_val = latest_row.get("rainfall_mm") or 0.0
    wind_val = latest_row.get("wind_speed") or 0.0

    pm25_stats = calc_stats(df["pm2_5"], pm25_val)
    temp_stats = calc_stats(df["temp_max"], temp_val)
    rain_stats = calc_stats(df["rainfall_mm"], rain_val)
    wind_stats = calc_stats(df["wind_speed"], wind_val)

    # 90-day percentile rank
    def calc_percentile(series: pd.Series, val: float) -> int:
        clean = series.dropna()
        if len(clean) == 0:
            return 50
        rank = (clean < val).sum() / len(clean) * 100.0
        return int(round(rank))

    pm25_pctl = calc_percentile(df["pm2_5"], pm25_val)
    temp_pctl = calc_percentile(df["temp_max"], temp_val)

    return {
        "latest_metrics": latest_row,
        "pm25_stats": pm25_stats,
        "temp_stats": temp_stats,
        "rain_stats": rain_stats,
        "wind_stats": wind_stats,
        "percentiles": {
            "pm2_5": pm25_pctl,
            "temp_max": temp_pctl
        },
        "z_scores": {
            "pm2_5_zscore": pm25_stats["zscore"],
            "temp_zscore": temp_stats["zscore"],
            "rainfall_zscore": rain_stats["zscore"],
            "wind_zscore": wind_stats["zscore"]
        }
    }
