import argparse
import sys

# Ensure UTF-8 stdout encoding on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from datetime import datetime, date
from sqlalchemy import text
from src.db import init_db, engine
from src.load import get_or_create_city, upsert_daily_metrics
from src.fetch import fetch_daily_forecast, fetch_air_quality
from src.transform import transform_weather_daily, transform_air_quality_hourly, merge_and_clean_metrics
from src.analytics import (
    compute_environmental_score,
    compute_activity_index,
    compute_city_risk_score,
    get_historical_and_anomaly_stats
)
from src.ai_narrate import generate_ai_narrative
from src.export_pdf import generate_daily_pdf_report
from src.config import PRECONFIGURED_CITIES, DEFAULT_CITY

def run_city_etl(city_name: str, generate_pdf: bool = True, force_ai: bool = False):
    """
    Execute daily ETL pipeline for a single city:
    Fetch -> Transform -> Load -> SQL Analytics -> AI Narration -> PDF Export.
    """
    print(f"\n==================================================")
    print(f"🌆 UrbanPulse Daily Pipeline: {city_name}")
    print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"==================================================")

    # 1. Look up city metadata
    city = get_or_create_city(city_name)
    city_id = city["city_id"]
    lat, lon = city["lat"], city["lon"]
    tz = city.get("timezone", "Asia/Kolkata")

    # 2. Fetch daily forecast (+ past_days=1 confirmed actuals) & air quality
    print(f"[1/6 Fetch] Calling Forecast API (past_days=1, forecast_days=16)...")
    weather_raw = fetch_daily_forecast(lat, lon, past_days=1, forecast_days=16, timezone=tz, city_name=city_name)
    weather_df = transform_weather_daily(weather_raw)

    print(f"[2/6 Fetch] Calling Air Quality API (past_days=1, forecast_days=7)...")
    aq_raw = fetch_air_quality(lat, lon, past_days=1, forecast_days=7, timezone=tz, city_name=city_name)
    aq_df = transform_air_quality_hourly(aq_raw)

    # 3. Transform & Merge
    print(f"[3/6 Transform] Normalizing and merging weather & air quality metrics...")
    merged_df = merge_and_clean_metrics(weather_df, aq_df)

    # 4. Load (SQL Upsert)
    print(f"[4/6 Load] Upserting {len(merged_df)} daily records into 'raw_daily_metrics' table...")
    upsert_count = upsert_daily_metrics(city_id, merged_df)

    # 5. SQL Analytics & Scoring
    print(f"[5/6 Analytics] Computing 7d/30d rolling baselines, Z-scores, and 3 scoring models...")
    today_str = date.today().strftime("%Y-%m-%d")
    stats = get_historical_and_anomaly_stats(city_id, target_date=today_str)
    
    if not stats or not stats.get("latest_metrics"):
        print(f"[Warning] No analytical baseline found for {city_name}. Running backfill is recommended.")
        return False

    latest_metrics = stats["latest_metrics"]
    env_score = compute_environmental_score(latest_metrics)
    act_index = compute_activity_index(latest_metrics)
    risk_score = compute_city_risk_score(latest_metrics, stats.get("z_scores", {}))

    facts_payload = {
        "city_name": city_name,
        "date": today_str,
        "latest_metrics": latest_metrics,
        "environmental_score": env_score,
        "activity_index": act_index,
        "risk_score": risk_score,
        "pm25_stats": stats.get("pm25_stats", {}),
        "temp_stats": stats.get("temp_stats", {}),
        "rain_stats": stats.get("rain_stats", {}),
        "percentiles": stats.get("percentiles", {})
    }

    # 6. AI Narration
    print(f"[6/6 AI Narration] Generating executive daily summary...")
    narrative = generate_ai_narrative(
        city_name=city_name,
        date_str=today_str,
        facts_payload=facts_payload,
        city_id=city_id,
        force_refresh=force_ai
    )

    # Optional: PDF Export
    pdf_path = None
    if generate_pdf:
        try:
            pdf_path = generate_daily_pdf_report(
                city_name=city_name,
                date_str=today_str,
                facts_payload=facts_payload,
                ai_narrative=narrative
            )
            print(f"📄 Generated Daily PDF Report: {pdf_path}")
        except Exception as e:
            print(f"[PDF Warning] Failed to generate PDF: {e}")

    print(f"\n✨ SUMMARY FOR {city_name.upper()} ({today_str}):")
    print(f"   • Environmental Score: {env_score['score']}/100 ({env_score['category']})")
    print(f"   • Outdoor Jogging:     {act_index['jogging']['score']}/100 ({act_index['jogging']['label']})")
    print(f"   • City Risk Band:      {risk_score['composite_risk']} Risk")
    print(f"   • AI Briefing:         {narrative[:120]}...\n")

    return True

from concurrent.futures import ThreadPoolExecutor, as_completed

def run_daily_pipeline(city: str = "default", generate_pdf: bool = True, force_ai: bool = False, max_workers: int = 10):
    """Run master daily ETL with concurrent thread execution for lightning speed."""
    init_db()

    if city == "all":
        # Get all distinct cities in database
        with engine.connect() as conn:
            city_rows = conn.execute(text("SELECT city_name FROM cities ORDER BY city_id ASC")).fetchall()
        cities_to_run = [r[0] for r in city_rows] if city_rows else list(PRECONFIGURED_CITIES.keys())[:10]
    elif city == "top":
        # 36 Key State Capitals & Major Metros for fast recurring telemetry sync
        from src.config import PRECONFIGURED_CITIES
        state_capitals = [
            "Hyderabad", "Amaravati", "Itanagar", "Dispur", "Patna", "Raipur", "Panaji", "Gandhinagar",
            "Chandigarh", "Shimla", "Ranchi", "Bengaluru", "Thiruvananthapuram", "Bhopal", "Mumbai",
            "Imphal", "Shillong", "Aizawl", "Kohima", "Bhubaneswar", "Jaipur", "Gangtok", "Chennai",
            "Agartala", "Lucknow", "Dehradun", "Kolkata", "Delhi", "Srinagar", "Pune", "Ahmedabad", "Kochi"
        ]
        cities_to_run = [c for c in state_capitals if c in PRECONFIGURED_CITIES]
    elif city == "default":
        cities_to_run = [DEFAULT_CITY]
    else:
        cities_to_run = [city]

    total_cities = len(cities_to_run)
    print(f"\n🚀 Launching UrbanPulse Parallel ETL for {total_cities} cities with {max_workers} worker threads...")

    completed = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_city = {
            executor.submit(run_city_etl, c, generate_pdf=generate_pdf, force_ai=force_ai): c
            for c in cities_to_run
        }
        for future in as_completed(future_to_city):
            c_name = future_to_city[future]
            try:
                success = future.result()
                if success:
                    completed += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                print(f"[ETL Error] {c_name} failed: {e}")

    print(f"\n🏁 Parallel ETL Complete: {completed}/{total_cities} cities updated successfully ({errors} failed).")

def main():
    parser = argparse.ArgumentParser(description="UrbanPulse Daily ETL Orchestrator")
    parser.add_argument("--city", type=str, default="top", help="City name, 'all', 'top', or 'default'")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent worker threads (default: 10)")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF report generation")
    parser.add_argument("--force-ai", action="store_true", help="Force re-generation of AI narrative")
    args = parser.parse_args()

    run_daily_pipeline(
        city=args.city,
        generate_pdf=not args.no_pdf,
        force_ai=args.force_ai,
        max_workers=args.workers
    )

if __name__ == "__main__":
    main()
