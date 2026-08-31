# 🌿 UrbanPulse — Daily City Environmental Intelligence Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/dashboard-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![PostgreSQL & SQLite](https://img.shields.io/badge/database-SQL-336791.svg)](https://www.sqlite.org/)
[![Open-Meteo](https://img.shields.io/badge/data%20source-Open--Meteo-10b981.svg)](https://open-meteo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **UrbanPulse** is a self-updating environmental intelligence platform that ingests daily weather, air quality, solar, and UV data, stores it in a structured SQL database, and computes **three distinct analytical products from one single automated pipeline**:
> 1. **🌿 Environmental Score (0–100)**: Holistic environmental wellness index.
> 2. **🏃 Outdoor Activity Index**: Re-weighted suitability scores for Jogging, Cycling, Photography, and General Comfort.
> 3. **⚠️ City Risk Score**: Multi-hazard risk evaluation with 30-day Z-Score anomaly detection ($> 2.0\sigma$).
> 
> *On top sits an **AI Analyst Layer** that reads computed facts (never raw data) and drafts an executive daily briefing, accompanied by interactive Streamlit dashboards and automated PDF reports.*

---

## 🏗️ Architecture & Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    DAILY SCHEDULED JOB (00:00 IST)          │
│  Triggered by: GitHub Actions / cron / APScheduler          │
└───────────────────────────┬─────────────────────────────────┘
                             │
                 ┌───────────┴────────────┐
                 │   1. FETCH LAYER        │
                 │  (Python + requests)    │
                 └───────────┬────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                     │
   Forecast API         Air Quality API       (Archive API —
   (weather, UV,        (PM2.5, PM10,          one-time only,
   solar, rain)         NO2, O3, pollen)       at first setup)
        │                    │                     │
        └────────────────────┼────────────────────┘
                             │
                 ┌───────────┴────────────┐
                 │   2. TRANSFORM LAYER    │
                 │  (Python / Pandas)      │
                 │  - clean, validate      │
                 │  - unit normalization   │
                 │  - dedupe by date+city  │
                 └───────────┬────────────┘
                             │
                 ┌───────────┴────────────┐
                 │   3. LOAD LAYER         │
                 │  (SQL — Postgres/SQLite)│
                 │  raw_daily_metrics table│
                 └───────────┬────────────┘
                             │
                 ┌───────────┴────────────┐
                 │  4. SQL ANALYTICS LAYER │
                 │  - rolling 7/30-day avg │
                 │  - percentile ranks     │
                 │  - z-score anomalies    │
                 │  - 3 scoring formulas   │
                 │    (Env / Activity /Risk)│
                 └───────────┬────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │               │
        ┌─────┴────┐   ┌─────┴─────┐   ┌─────┴──────┐
        │ 5. AI     │   │ 6. STREAMLIT│  │ 7. Export  │
        │ NARRATION │   │  DASHBOARD  │  │ (PDF Report│
        │ (LLM call)│   │  (8 Views)  │  │ auto-gen)  │
        └───────────┘   └─────────────┘  └────────────┘
```

---

## 📦 Project Structure

```
UrbanPulse/
├── .github/
│   └── workflows/
│       └── daily_etl.yml         # GitHub Actions automated daily run (18:30 UTC / 00:00 IST)
├── sql/
│   ├── schema.sql                # Table definitions (cities, raw_daily_metrics, api_logs, ai_narratives)
│   └── views.sql                 # SQL analytical views (rolling 7/30d avg, z-scores, percentiles)
├── src/
│   ├── config.py                 # App settings, DB connections, default cities, thresholds
│   ├── db.py                     # Database engine helper (SQLite WAL / PostgreSQL abstraction)
│   ├── fetch.py                  # Open-Meteo REST client with telemetry logger
│   ├── transform.py              # Pandas cleaning, unit normalization, AQI EPA breakpoints
│   ├── load.py                   # Safe SQL upsert logic ON CONFLICT(city_id, date)
│   ├── analytics.py              # 3 Scoring models + 30-day Z-Score anomaly engine
│   ├── ai_narrate.py             # LLM narration (Claude / Gemini / deterministic fallback)
│   ├── export_pdf.py             # ReportLab automated PDF daily report generator
│   └── scheduler.py              # APScheduler background runner for standalone deployments
├── dashboard/
│   ├── app.py                    # Streamlit main entrypoint & 8-view dashboard
│   ├── components.py             # Reusable Plotly charts (Gauges, Radars, Percentile bands)
│   └── styles.css                # Premium modern glassmorphic dark theme
├── backfill.py                   # One-time historical backfill script (90-365 days)
├── daily_etl.py                  # Scheduled orchestrator script (Fetch -> Clean -> Load -> Score -> AI -> PDF)
├── requirements.txt              # Project dependencies
├── .env.example                  # Environment configuration template
└── README.md                     # Complete project documentation
```

---

## ⚡ Quickstart Guide

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/your-username/UrbanPulse.git
cd UrbanPulse

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env` if you wish to configure an API key for Claude or Gemini:
```bash
cp .env.example .env
```
*(Note: UrbanPulse runs 100% locally out-of-the-box with zero API keys required thanks to Open-Meteo's keyless tier and our built-in deterministic factual analyst fallback!)*

### 3. Run One-Time Historical Backfill
Populate 180 days of historical baseline data so rolling averages, percentiles, and Z-scores are active on Day 1:
```bash
# Backfill default city (Hyderabad)
python backfill.py --city Hyderabad --days 180

# Or backfill multiple major cities
python backfill.py --city all --days 180
```

### 4. Execute the Daily Pipeline Manually
```bash
# Run for single city
python daily_etl.py --city Hyderabad

# Run for all registered cities with PDF generation
python daily_etl.py --city all
```

### 5. Launch the Streamlit Intelligence Dashboard
```bash
streamlit run dashboard/app.py
```
Open your browser at `http://localhost:8501`.

---

## 📊 Three Core Analytical Products

| Product | Focus Area | Underlying Metrics & Methodology |
| :--- | :--- | :--- |
| **🌿 Environmental Score (0-100)** | General Environmental Health | Weighted balance: Air Quality (35%), Thermal Comfort (25%), Humidity Balance (15%), UV Safety (15%), Precipitation Stability (10%). |
| **🏃 Outdoor Activity Index** | Recreational Planning | Re-weighted suitability models for **Jogging**, **Cycling**, **Photography**, and **General Comfort**. |
| **⚠️ City Risk Score** | Disaster & Hazard Mitigation | Multi-hazard alerts across **Heatwaves**, **Smog/AQI**, **Flash Floods**, and **High Wind**, combined with $Z > 2.0\sigma$ anomaly triggers. |

---

## ⏰ Scheduling Options

- **Option A: GitHub Actions (Recommended for Portfolios)**:
  Runs automatically at `00:00 IST` (18:30 UTC) every night via `.github/workflows/daily_etl.yml`. Zero server costs.
- **Option B: APScheduler (Always-on Python Process)**:
  `python src/scheduler.py`
- **Option C: OS-level Cron (Linux/WSL)**:
  ```cron
  0 0 * * * /usr/bin/python3 /path/to/UrbanPulse/daily_etl.py --city all >> /path/to/logs.log 2>&1
  ```

---

## 🛡️ Telemetry & API Reliability Monitoring
UrbanPulse treats data infrastructure as a **Monitored Data Product**:
- Every outbound REST call logs endpoint, status code, latency (ms), timestamp, and error traces into `api_logs`.
- Real-time SLA dashboard surfaces 30-day success rates, average response latency, and database health.

---

## 📄 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
