import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    rows = conn.execute(text('SELECT city_name, latitude, longitude, timezone, country, admin1 FROM cities ORDER BY admin1, city_name')).fetchall()

print(f'Total cities exported: {len(rows)}')
with open('src/config.py', 'w', encoding='utf-8') as f:
    f.write('import os\nfrom pathlib import Path\nfrom dotenv import load_dotenv\n\n')
    f.write('BASE_DIR = Path(__file__).resolve().parent.parent\n')
    f.write('load_dotenv(BASE_DIR / ".env")\n\n')
    f.write('DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / \'urbanpulse.db\'}")\n')
    f.write('ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()\n')
    f.write('GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()\n')
    f.write('DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Hyderabad")\n')
    f.write('DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")\n')
    f.write('DEFAULT_BACKFILL_DAYS = int(os.getenv("DEFAULT_BACKFILL_DAYS", "180"))\n\n')
    f.write('# Comprehensive Registry of all 417+ Indian States, District HQs, and Populated Towns\n')
    f.write('PRECONFIGURED_CITIES = {\n')
    for r in rows:
        admin_val = r[5] if r[5] else 'National'
        f.write(f'    "{r[0]}": {{"lat": {round(r[1], 4)}, "lon": {round(r[2], 4)}, "timezone": "{r[3]}", "country": "{r[4]}", "admin1": "{admin_val}"}},\n')
    f.write('}\n')
print('src/config.py successfully updated with all Indian cities!')
