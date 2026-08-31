import argparse
import sys

# Ensure UTF-8 stdout encoding on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from datetime import datetime, date, timedelta
from src.db import init_db
from src.load import get_or_create_city, upsert_daily_metrics
from src.fetch import fetch_historical_archive, fetch_air_quality
from src.transform import transform_weather_daily, transform_air_quality_hourly, merge_and_clean_metrics
from src.config import PRECONFIGURED_CITIES, DEFAULT_BACKFILL_DAYS

def run_backfill(city_name: str, days: int = 180):
    """
    Backfill historical data (90-365 days) for a city using Open-Meteo Archive API.
    """
    print(f"\n==================================================")
    print(f"🚀 UrbanPulse Historical Backfill: {city_name}")
    print(f"   Backfilling last {days} days of meteorological data...")
    print(f"==================================================")

    init_db()

    # 1. Get or create city record
    city = get_or_create_city(city_name)
    city_id = city["city_id"]
    lat, lon = city["lat"], city["lon"]
    tz = city.get("timezone", "Asia/Kolkata")

    # 2. Date ranges
    end_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    print(f"[Fetch] Querying Archive API for {city_name} from {start_date} to {end_date}...")
    try:
        weather_raw = fetch_historical_archive(lat, lon, start_date, end_date, timezone=tz, city_name=city_name)
        weather_df = transform_weather_daily(weather_raw)
        print(f"[Transform] Extracted {len(weather_df)} historical daily weather records.")
    except Exception as e:
        print(f"[Error] Failed to fetch archive data for {city_name}: {e}")
        return False

    # 3. Air Quality (Open-Meteo Air Quality supports past 90 days; we also fetch recent AQ)
    aq_df = None
    try:
        print(f"[Fetch] Querying Air Quality API for recent baseline...")
        aq_raw = fetch_air_quality(lat, lon, past_days=min(days, 90), timezone=tz, city_name=city_name)
        aq_df = transform_air_quality_hourly(aq_raw)
        print(f"[Transform] Extracted {len(aq_df)} daily air quality records.")
    except Exception as e:
        print(f"[Warning] Historical air quality fetch notice: {e}")

    # 4. Merge and clean
    merged_df = merge_and_clean_metrics(weather_df, aq_df)

    # 5. Upsert to SQL DB
    print(f"[Load] Upserting {len(merged_df)} records into 'raw_daily_metrics' table...")
    count = upsert_daily_metrics(city_id, merged_df)
    print(f"✅ Successfully backfilled {count} days for {city_name}.\n")
    return True

def main():
    parser = argparse.ArgumentParser(description="UrbanPulse Historical Data Backfill")
    parser.add_argument("--city", type=str, default="Hyderabad", help="City name or 'all' to backfill default set")
    parser.add_argument("--days", type=int, default=DEFAULT_BACKFILL_DAYS, help="Number of historical days (90-365)")
    args = parser.parse_args()

    if args.city.lower() == "all":
        for c in ["Hyderabad", "Bengaluru", "Delhi", "Mumbai"]:
            run_backfill(c, days=args.days)
    else:
        run_backfill(args.city, days=args.days)

if __name__ == "__main__":
    main()
