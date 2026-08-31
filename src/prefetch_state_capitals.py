import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure UTF-8 stdout encoding on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from daily_etl import run_city_etl
from src.config import PRECONFIGURED_CITIES

# Pick representative cities across states
KEY_CITIES = [
    # Metros & Capitals
    "Port Blair", "Amaravati", "Visakhapatnam", "Tirupati", "Itanagar", "Guwahati",
    "Dispur", "Silchar", "Patna", "Gaya", "Muzaffarpur", "Chandigarh", "Raipur",
    "Bhilai", "Daman", "Silvassa", "Delhi", "New Delhi", "Panaji", "Ahmadabad",
    "Gandhinagar", "Surat", "Rajkot", "Gurugram", "Faridabad", "Shimla", "Dharmshala",
    "Srinagar", "Jammu", "Ranchi", "Jamshedpur", "Bengaluru", "Mysuru", "Mangaluru",
    "Thiruvananthapuram", "Kochi", "Kozhikode", "Leh", "Bhopal", "Indore", "Jabalpur",
    "Gwalior", "Rewa", "Ujjain", "Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad",
    "Imphal", "Shillong", "Cherrapunji", "Aizawl", "Kohima", "Bhubaneshwar", "Cuttack",
    "Puri", "Puducherry", "Amritsar", "Ludhiana", "Jaipur", "Jodhpur", "Udaipur",
    "Bikaner", "Gangtok", "Chennai", "Coimbatore", "Madurai", "Hyderabad", "Warangal",
    "Agartala", "Lucknow", "Kanpur", "Varanasi", "Agra", "Prayagraj", "Dehra Dun",
    "Haridwar", "Nainital", "Kolkata", "Darjeeling", "Siliguri", "Howrah"
]

print(f"Pre-fetching rich telemetry for {len(KEY_CITIES)} key cities across India...")
for idx, city in enumerate(KEY_CITIES, 1):
    print(f"[{idx}/{len(KEY_CITIES)}] Fetching telemetry for {city}...")
    try:
        run_city_etl(city, generate_pdf=False)
    except Exception as e:
        print(f"  Failed on {city}: {e}")
    time.sleep(0.1)

print("\n✅ Key state capitals and regional hubs pre-fetched successfully!")
