import sys
from pathlib import Path

# Ensure root directory in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure UTF-8 stdout encoding on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import text
from src.db import init_db, engine
from src.config import PRECONFIGURED_CITIES

def seed_all_states_and_cities():
    """
    Seed all 28 Indian States, 8 Union Territories, and Global Metropolises
    into the database cities table.
    """
    init_db()
    print("==================================================")
    print("Seeding All States & Cities into UrbanPulse Registry")
    print(f"Total Registry Size: {len(PRECONFIGURED_CITIES)} Cities & State Capitals")
    print("==================================================")

    inserted = 0
    updated = 0

    with engine.begin() as conn:
        for name, meta in PRECONFIGURED_CITIES.items():
            existing = conn.execute(
                text("SELECT city_id FROM cities WHERE LOWER(city_name) = LOWER(:name)"),
                {"name": name}
            ).fetchone()

            if existing:
                conn.execute(
                    text("""
                        UPDATE cities SET
                            latitude = :lat,
                            longitude = :lon,
                            timezone = :timezone,
                            country = :country,
                            admin1 = :admin1
                        WHERE city_id = :city_id
                    """),
                    {
                        "city_id": existing[0],
                        "lat": meta["lat"],
                        "lon": meta["lon"],
                        "timezone": meta["timezone"],
                        "country": meta.get("country", "India"),
                        "admin1": meta.get("admin1", "")
                    }
                )
                updated += 1
            else:
                conn.execute(
                    text("""
                        INSERT INTO cities (city_name, latitude, longitude, timezone, country, admin1)
                        VALUES (:name, :lat, :lon, :timezone, :country, :admin1)
                    """),
                    {
                        "name": name,
                        "lat": meta["lat"],
                        "lon": meta["lon"],
                        "timezone": meta["timezone"],
                        "country": meta.get("country", "India"),
                        "admin1": meta.get("admin1", "")
                    }
                )
                inserted += 1

    print(f"Success: Registered {inserted} new cities and verified {updated} existing cities.")
    print(f"Total active cities in DB: {inserted + updated}\n")

if __name__ == "__main__":
    seed_all_states_and_cities()
