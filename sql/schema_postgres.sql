-- =========================================================
-- UrbanPulse PostgreSQL Schema (Production Cloud Database)
-- =========================================================

-- 1. Cities Registry Table
CREATE TABLE IF NOT EXISTS cities (
    city_id SERIAL PRIMARY KEY,
    city_name TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    country TEXT DEFAULT 'India',
    admin1 TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_city_name_admin UNIQUE (city_name, admin1)
);

CREATE INDEX IF NOT EXISTS idx_cities_name ON cities(city_name);
CREATE INDEX IF NOT EXISTS idx_cities_admin1 ON cities(admin1);

-- 2. Raw Daily Environmental Metrics Table
CREATE TABLE IF NOT EXISTS raw_daily_metrics (
    id SERIAL PRIMARY KEY,
    city_id INTEGER NOT NULL REFERENCES cities(city_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    temp_max DOUBLE PRECISION,
    temp_min DOUBLE PRECISION,
    temp_mean DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    rainfall_mm DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    uv_index DOUBLE PRECISION,
    solar_radiation DOUBLE PRECISION,
    pm2_5 DOUBLE PRECISION,
    pm10 DOUBLE PRECISION,
    no2 DOUBLE PRECISION,
    ozone DOUBLE PRECISION,
    pollen_grass DOUBLE PRECISION,
    pollen_birch DOUBLE PRECISION,
    pollen_ragweed DOUBLE PRECISION,
    aqi_us INTEGER,
    is_forecast INTEGER DEFAULT 0,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_metrics_city_date UNIQUE(city_id, date)
);

CREATE INDEX IF NOT EXISTS idx_metrics_city_date ON raw_daily_metrics(city_id, date);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON raw_daily_metrics(date);

-- 3. API Execution & Health Logs
CREATE TABLE IF NOT EXISTS api_logs (
    id SERIAL PRIMARY KEY,
    endpoint TEXT NOT NULL,
    city_name TEXT,
    status_code INTEGER,
    latency_ms DOUBLE PRECISION,
    success INTEGER NOT NULL,
    error_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_logs_time ON api_logs(timestamp);

-- 4. AI Daily Narratives & Briefings
CREATE TABLE IF NOT EXISTS ai_narratives (
    id SERIAL PRIMARY KEY,
    city_id INTEGER NOT NULL REFERENCES cities(city_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    narrative_summary TEXT NOT NULL,
    provider TEXT DEFAULT 'RuleEngine',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_narratives_city_date UNIQUE(city_id, date)
);

CREATE INDEX IF NOT EXISTS idx_ai_narratives_city_date ON ai_narratives(city_id, date);
