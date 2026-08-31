-- =========================================================
-- UrbanPulse Database Schema
-- Compatible with SQLite (local) and PostgreSQL (production)
-- =========================================================

-- 1. Cities Registry Table
CREATE TABLE IF NOT EXISTS cities (
    city_id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_name TEXT NOT NULL UNIQUE,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    country TEXT,
    admin1 TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Raw Daily Environmental Metrics Table
CREATE TABLE IF NOT EXISTS raw_daily_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id INTEGER NOT NULL REFERENCES cities(city_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    temp_max REAL,
    temp_min REAL,
    temp_mean REAL,
    humidity REAL,
    rainfall_mm REAL,
    wind_speed REAL,
    uv_index REAL,
    solar_radiation REAL,
    pm2_5 REAL,
    pm10 REAL,
    no2 REAL,
    ozone REAL,
    pollen_grass REAL,
    pollen_birch REAL,
    pollen_ragweed REAL,
    aqi_us INTEGER,
    is_forecast INTEGER DEFAULT 0,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(city_id, date)
);

CREATE INDEX IF NOT EXISTS idx_metrics_city_date ON raw_daily_metrics(city_id, date);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON raw_daily_metrics(date);

-- 3. API Execution & Health Logs (Monitored Data Product)
CREATE TABLE IF NOT EXISTS api_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL,
    city_name TEXT,
    status_code INTEGER,
    latency_ms REAL,
    success INTEGER NOT NULL,
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_logs_time ON api_logs(timestamp);

-- 4. AI Daily Narratives & Briefings
CREATE TABLE IF NOT EXISTS ai_narratives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id INTEGER NOT NULL REFERENCES cities(city_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    narrative_summary TEXT NOT NULL,
    provider TEXT DEFAULT 'RuleEngine',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(city_id, date)
);

CREATE INDEX IF NOT EXISTS idx_ai_narratives_city_date ON ai_narratives(city_id, date);
