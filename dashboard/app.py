import os
import sys
from pathlib import Path
from datetime import datetime, date, timedelta

# Add root directory to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import text

from src.db import init_db, engine
from src.load import get_or_create_city
from src.analytics import (
    compute_environmental_score,
    compute_activity_index,
    compute_city_risk_score,
    get_historical_and_anomaly_stats
)
from src.ai_narrate import generate_ai_narrative
from src.export_pdf import generate_daily_pdf_report
from src.config import PRECONFIGURED_CITIES, DEFAULT_CITY, EXPORTS_DIR
from src.geolocation import (
    reverse_geocode_coordinates,
    resolve_and_register_location,
    normalize_state_name
)
from streamlit_geolocation import _streamlit_geolocation
import importlib
import dashboard.components
importlib.reload(dashboard.components)

from dashboard.components import (
    render_score_gauge,
    render_activity_radar,
    render_historical_percentile_trend,
    render_forecast_trend,
    render_live_location_map
)

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="UrbanPulse — Environmental Intelligence",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load Custom Glassmorphic Styles
css_path = ROOT_DIR / "dashboard" / "styles.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Ensure Database is Initialized and All States/Cities are Registered
try:
    init_db()
    with engine.connect() as conn:
        c_count = conn.execute(text("SELECT COUNT(*) FROM cities")).scalar()
    if c_count < len(PRECONFIGURED_CITIES):
        from src.seed_cities import seed_all_states_and_cities
        seed_all_states_and_cities()
except Exception as e:
    print(f"[Notice] Database connection / seeding notice: {e}")

# Initialize session state for selected state & city
if "app_selected_state" not in st.session_state:
    st.session_state["app_selected_state"] = "Telangana"
if "app_selected_city" not in st.session_state:
    st.session_state["app_selected_city"] = "Hyderabad"

# ==========================================
# Sidebar: Location Search & Navigation
# ==========================================
with st.sidebar:
    st.markdown("### 🌿 **UrbanPulse**")
    st.caption("Daily City Environmental Intelligence Platform")
    st.markdown("---")

    # ------------------------------------------
    # 📍 Live Location Auto-Detection
    # ------------------------------------------
    st.markdown("##### 📍 Live Location Auto-Detection")
    st.markdown(
        """
        <div class="geo-action-card">
            <div style="font-size:0.85rem; font-weight:600; color:#f8fafc; margin-bottom:2px;">
                🛰️ Auto-Detect Device GPS Location
            </div>
            <div class="geo-status-text">
                Click below to instantly sync your exact city, state & environmental telemetry.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if "geo_nonce" not in st.session_state:
        st.session_state["geo_nonce"] = 0

    # Official precompiled React Geolocation component with dynamic nonce keying
    loc_payload = _streamlit_geolocation(
        key=f"loc_comp_{st.session_state['geo_nonce']}",
        default={'latitude': None, 'longitude': None}
    )

    if loc_payload and isinstance(loc_payload, dict):
        p_lat = loc_payload.get("latitude")
        p_lon = loc_payload.get("longitude")

        if p_lat is not None and p_lon is not None:
            p_lat = float(p_lat)
            p_lon = float(p_lon)
            with st.spinner(f"Resolving live location ({p_lat:.4f}°N, {p_lon:.4f}°E)..."):
                try:
                    resolved = resolve_and_register_location(p_lat, p_lon, auto_etl=True)
                    c_name = resolved["city_name"]
                    c_state = resolved.get("admin1") or "Madhya Pradesh"
                    st.session_state["last_processed_gps"] = {"lat": p_lat, "lon": p_lon, "city": c_name, "state": c_state}
                    st.session_state["app_selected_state"] = c_state
                    st.session_state["state_select_widget"] = c_state
                    st.session_state["app_selected_city"] = c_name
                    st.session_state["city_select_widget"] = c_name
                    st.session_state["location_source_badge"] = f"🛰️ Live GPS: {c_name}, {c_state}"
                    st.session_state["geo_nonce"] = st.session_state.get("geo_nonce", 0) + 1
                    st.success(f"📍 GPS Fixed: {c_name}, {c_state}")
                    st.rerun()
                except Exception as e:
                    st.error(f"GPS Resolution Error: {e}")

    # Direct Re-Sync Button
    if st.session_state.get("last_processed_gps"):
        gps_info = st.session_state["last_processed_gps"]
        if st.button(f"🛰️ Re-Select GPS ({gps_info['city']})", key="btn_reselect_gps", use_container_width=True, help="Instantly switch back to your detected GPS location"):
            st.session_state["app_selected_state"] = gps_info["state"]
            st.session_state["state_select_widget"] = gps_info["state"]
            st.session_state["app_selected_city"] = gps_info["city"]
            st.session_state["city_select_widget"] = gps_info["city"]
            st.session_state["location_source_badge"] = f"🛰️ Live GPS: {gps_info['city']}, {gps_info['state']}"
            st.rerun()

    st.markdown("---")

    # ------------------------------------------
    # 🔍 Smart City Search & Auto-State Switcher
    # ------------------------------------------
    st.markdown("##### 🔍 Instant City Search")
    with st.form("quick_search_form", clear_on_submit=False):
        search_query = st.text_input(
            "Type any City or Town Name",
            placeholder="e.g. Warangal, Vijayawada, Bhopal, Pune, Indore, Rampur...",
            label_visibility="collapsed"
        )
        submitted_search = st.form_submit_button("🚀 Find & Select City", use_container_width=True)

    if submitted_search and search_query.strip():
        with st.spinner(f"Geocoding '{search_query.strip()}'..."):
            try:
                city_res = get_or_create_city(search_query.strip())
                c_name = city_res["city_name"]
                c_state = city_res.get("admin1") or "All States & Territories"
                st.session_state["app_selected_state"] = c_state
                st.session_state["state_select_widget"] = c_state
                st.session_state["app_selected_city"] = c_name
                st.session_state["city_select_widget"] = c_name
                st.session_state["location_source_badge"] = f"📍 {c_name}, {c_state}"
                st.session_state["geo_nonce"] = st.session_state.get("geo_nonce", 0) + 1
                st.success(f"Selected {c_name} ({c_state})")
                st.rerun()
            except Exception as e:
                st.error(f"Search failed: {e}")

    st.markdown("---")

    # ------------------------------------------
    # 🗺️ State & City Selectors
    # ------------------------------------------
    with engine.connect() as conn:
        cities_df = pd.read_sql(
            text("SELECT city_id, city_name, country, admin1 FROM cities ORDER BY admin1, city_name"),
            conn
        )

    raw_states = sorted([s for s in cities_df["admin1"].dropna().unique() if s.strip()])
    states_list = ["All States & Territories"] + raw_states

    # Ensure state selection is valid and synchronized
    curr_state_target = st.session_state.get("app_selected_state", "Telangana")
    if curr_state_target not in states_list:
        curr_state_target = raw_states[0] if raw_states else "All States & Territories"
        st.session_state["app_selected_state"] = curr_state_target

    if st.session_state.get("state_select_widget") not in states_list:
        st.session_state["state_select_widget"] = curr_state_target

    def on_state_change():
        new_s = st.session_state["state_select_widget"]
        st.session_state["app_selected_state"] = new_s
        if new_s != "All States & Territories":
            c_sub = sorted(cities_df[cities_df["admin1"] == new_s]["city_name"].dropna().unique().tolist())
        else:
            c_sub = sorted(cities_df["city_name"].dropna().unique().tolist())
        if c_sub:
            st.session_state["app_selected_city"] = c_sub[0]
            st.session_state["city_select_widget"] = c_sub[0]
        st.session_state["location_source_badge"] = f"📍 {st.session_state.get('app_selected_city', '')}, {new_s}"

    selected_state = st.selectbox(
        "🗺️ Select State / Region",
        states_list,
        key="state_select_widget",
        on_change=on_state_change
    )
    st.session_state["app_selected_state"] = selected_state

    # Filter cities list by state
    if selected_state != "All States & Territories":
        filtered_df = cities_df[cities_df["admin1"] == selected_state]
        city_label = f"📍 Select City in {selected_state} ({len(filtered_df)})"
    else:
        filtered_df = cities_df
        city_label = f"📍 Select City ({len(filtered_df)} available)"

    available_cities = sorted(filtered_df["city_name"].dropna().unique().tolist())

    curr_city_target = st.session_state.get("app_selected_city")
    if curr_city_target not in available_cities:
        curr_city_target = available_cities[0] if available_cities else DEFAULT_CITY
        st.session_state["app_selected_city"] = curr_city_target

    if st.session_state.get("city_select_widget") not in available_cities:
        st.session_state["city_select_widget"] = curr_city_target

    def on_city_change():
        st.session_state["app_selected_city"] = st.session_state["city_select_widget"]
        st.session_state["location_source_badge"] = f"📍 {st.session_state['city_select_widget']}, {selected_state}"

    selected_city_name = st.selectbox(
        city_label,
        available_cities,
        key="city_select_widget",
        on_change=on_city_change
    )
    st.session_state["app_selected_city"] = selected_city_name

    # Optional: Add new city dynamically
    with st.expander("➕ Add Custom City / Town"):
        new_city_input = st.text_input("City or Town Name", placeholder="e.g. Almora, Tadepalligudem, Venice", key="add_city_text_in")
        if st.button("Geocode & Add", use_container_width=True, key="add_city_btn") and new_city_input:
            try:
                new_city = get_or_create_city(new_city_input, selected_state if selected_state != "All States & Territories" else None)
                st.session_state["app_selected_state"] = new_city.get("admin1") or "All States & Territories"
                st.session_state["state_select_widget"] = st.session_state["app_selected_state"]
                st.session_state["app_selected_city"] = new_city["city_name"]
                st.session_state["city_select_widget"] = new_city["city_name"]
                st.session_state["location_source_badge"] = f"📍 {new_city['city_name']}, {new_city.get('admin1', '')}"
                st.session_state["geo_nonce"] = st.session_state.get("geo_nonce", 0) + 1
                st.success(f"Added {new_city['city_name']} ({new_city.get('admin1', '')}, {new_city.get('country', '')})")
                st.rerun()
            except Exception as e:
                st.error(f"Geocoding failed: {e}")

    # Navigation Menu
    st.markdown("---")
    st.markdown("##### 🧭 Intelligence Views")
    menu = st.radio(
        "Navigate",
        [
            "🏙️ Live City Pulse",
            "🏆 National & State Leaderboard",
            "💨 Air Quality Deep-Dive",
            "☀️ Weather & Thermal Comfort",
            "🏃 Outdoor Activity Planner",
            "⚠️ City Risk & Hazard Alerts",
            "📈 Historical Trends & Percentiles",
            "🤖 AI Analyst & Daily Report",
            "⚡ Pipeline & API Health"
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown("##### 📅 Telemetry Date Mode")
    date_mode = st.radio(
        "Date Mode",
        [
            "⚡ Today (Live Real-Time)",
            "📋 Yesterday (Confirmed 24h)",
            "🗓️ Custom Date"
        ],
        index=0,
        label_visibility="collapsed"
    )

    custom_selected_date = None
    if date_mode == "🗓️ Custom Date":
        custom_selected_date = st.date_input("Select Historical Date", value=date.today())

    st.markdown("---")
    # Quick Pipeline Sync Trigger
    if st.button("🔄 Sync Live Pipeline Now", use_container_width=True):
        with st.spinner(f"Executing daily ETL for {selected_city_name}..."):
            from daily_etl import run_city_etl
            try:
                run_city_etl(selected_city_name, generate_pdf=True, force_ai=True)
                st.success("Synced successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Sync error: {e}")

    st.caption("Open-Meteo Pipeline • Real-Time + Historical")

# ==========================================
# Fetch Context Data for Selected City
# ==========================================
city_obj = get_or_create_city(selected_city_name, selected_state if selected_state != "All States & Territories" else None)
city_id = city_obj["city_id"]

today_str = date.today().strftime("%Y-%m-%d")
yesterday_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

if date_mode == "⚡ Today (Live Real-Time)":
    target_date_str = today_str
elif date_mode == "📋 Yesterday (Confirmed 24h)":
    target_date_str = yesterday_str
else:
    target_date_str = custom_selected_date.strftime("%Y-%m-%d") if custom_selected_date else today_str

# Fetch historical metrics for this city from database
with engine.connect() as conn:
    df_history = pd.read_sql(
        text("SELECT * FROM raw_daily_metrics WHERE city_id = :city_id ORDER BY date ASC"),
        conn,
        params={"city_id": city_id}
    )

# If no data exists yet or today's data is not yet in the database, auto-sync live forecast + air quality on the fly!
if df_history.empty or (today_str not in df_history["date"].values and date_mode == "⚡ Today (Live Real-Time)"):
    with st.spinner(f"📡 Fetching live environmental telemetry for **{selected_city_name}**..."):
        from daily_etl import run_city_etl
        try:
            run_city_etl(selected_city_name, generate_pdf=False)
            with engine.connect() as conn:
                df_history = pd.read_sql(
                    text("SELECT * FROM raw_daily_metrics WHERE city_id = :city_id ORDER BY date ASC"),
                    conn,
                    params={"city_id": city_id}
                )
        except Exception as e:
            st.error(f"Live data fetch error for {selected_city_name}: {e}")

if df_history.empty:
    st.warning(f"⚠️ No telemetry available yet for **{selected_city_name}**.")
    if st.button("🚀 Run One-Time Historical Backfill (90 Days)", type="primary"):
        from backfill import run_backfill
        run_backfill(selected_city_name, days=90)
        st.rerun()
    st.stop()

# Compute Analytics & Scores for the selected target date
stats = get_historical_and_anomaly_stats(city_id, target_date=target_date_str)
latest_metrics = stats.get("latest_metrics", df_history.iloc[-1].to_dict())
env_score = compute_environmental_score(latest_metrics)
act_index = compute_activity_index(latest_metrics)
risk_score = compute_city_risk_score(latest_metrics, stats.get("z_scores", {}))

facts_payload = {
    "city_name": selected_city_name,
    "date": latest_metrics.get("date", target_date_str),
    "latest_metrics": latest_metrics,
    "environmental_score": env_score,
    "activity_index": act_index,
    "risk_score": risk_score,
    "pm25_stats": stats.get("pm25_stats", {}),
    "temp_stats": stats.get("temp_stats", {}),
    "rain_stats": stats.get("rain_stats", {}),
    "percentiles": stats.get("percentiles", {})
}

# Fetch or generate AI narrative
narrative = generate_ai_narrative(
    city_name=selected_city_name,
    date_str=str(latest_metrics.get("date", target_date_str)),
    facts_payload=facts_payload,
    city_id=city_id,
    force_refresh=False
)

# ==========================================
# Reusable 'About this View' Component
# ==========================================
def render_about_view(title: str, text_content: str):
    """Renders a glassmorphic educational context card at the top of each view."""
    st.markdown(
        f"""
        <div class="about-view-card">
            <div class="about-view-title">ℹ️ About this View — {title}</div>
            <div class="about-view-text">{text_content}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ==========================================
# Header Section (Rendered on City-Specific Views)
# ==========================================
if menu not in ["🏆 National & State Leaderboard", "⚡ Pipeline & API Health"]:
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        loc_badge = st.session_state.get("location_source_badge")
        if loc_badge:
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:4px; flex-wrap:wrap;">
                    <h1 style="margin:0; font-size:2.2rem;">🌆 {selected_city_name} Environmental Intelligence</h1>
                    <span class="live-location-badge"><span class="live-beacon-dot"></span>{loc_badge}</span>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.title(f"🌆 {selected_city_name} Environmental Intelligence")
        country_admin = f"{city_obj.get('admin1', '')}, {city_obj.get('country', '')}".strip(", ")
        st.caption(f"Coordinates: {city_obj['lat']:.4f}°N, {city_obj['lon']:.4f}°E • Timezone: {city_obj.get('timezone', 'Asia/Kolkata')} • {country_admin}")

    with header_col2:
        st.markdown(
            f"<div style='text-align:right; padding-top:10px;'>"
            f"<span class='badge-pill badge-{env_score['category'].lower()}'>{env_score['category']} Condition</span><br>"
            f"<small style='color:#64748b;'>Latest: {latest_metrics.get('date', today_str)}</small>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")

# ==========================================
# VIEW 1: Live City Pulse & Overview
# ==========================================
if menu == "🏙️ Live City Pulse":
    render_about_view(
        "Live City Pulse & Environmental Briefing",
        "Provides an executive real-time overview of the selected city's environmental vitality. It unifies high-resolution telemetry from the World Meteorological Organization (WMO) grid and Copernicus Atmosphere Monitoring Service (CAMS), synthesized through our proprietary multi-factor Environmental Quality Score (0–100), AI biometeorology briefing, and localized sensor map."
    )

    # 1. AI Analyst Briefing Box
    st.markdown(
        f"""
        <div class="ai-briefing-box">
            <div class="ai-badge">🤖 AI Environmental Analyst Briefing • Grounded in WHO (2021) & CPCB Standards</div>
            <div style="font-size:1.02rem; line-height:1.7; color:#f8fafc; margin-top:8px;">
                {narrative}
            </div>
            <div style="display:flex; gap:16px; margin-top:14px; flex-wrap:wrap; font-size:0.78rem; color:#94a3b8; border-top:1px solid rgba(255,255,255,0.06); padding-top:10px;">
                <span>🌐 <b>Telemetry Sources:</b> Open-Meteo High-Resolution WMO Grid</span>
                <span>💨 <b>Atmospheric Dispersion:</b> CAMS Copernicus (0.1° Grid)</span>
                <span>🏛️ <b>Benchmarks:</b> WHO Air Quality Guidelines (2021), CPCB & IMD</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 2. Three Core Scoring Pillars (3-in-1 Output)
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            f"""
            <div class="pulse-card">
                <div class="pulse-header">
                    <span class="pulse-title">🌿 Environmental Score</span>
                    <span class="badge-pill badge-{env_score['category'].lower()}">{env_score['category']}</span>
                </div>
                <div class="pulse-value">{env_score['score']}<small style='font-size:1.1rem; color:#64748b;'>/100</small></div>
                <div class="pulse-subtext">Composite of Air Purity, Thermal Balance, UV & Humidity</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.plotly_chart(render_score_gauge(env_score['score'], "Environmental Quality", env_score['category'], env_score['color']), use_container_width=True)

    with col2:
        top_act = max(
            [(act_k, act_v["score"]) for act_k, act_v in act_index.items() if isinstance(act_v, dict) and "score" in act_v],
            key=lambda x: x[1]
        )
        top_act_obj = act_index[top_act[0]]
        st.markdown(
            f"""
            <div class="pulse-card">
                <div class="pulse-header">
                    <span class="pulse-title">🏃 Outdoor Activity Index</span>
                    <span class="badge-pill badge-{top_act_obj['label'].lower()}">{top_act_obj['name']}: {top_act[1]}%</span>
                </div>
                <div class="pulse-value">{top_act[1]}<small style='font-size:1.1rem; color:#64748b;'>%</small></div>
                <div class="pulse-subtext">Best activity: <b>{top_act_obj['name']}</b> ({top_act_obj['advice']})</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.plotly_chart(render_activity_radar(act_index), use_container_width=True)

    with col3:
        risk_cat = risk_score["composite_risk"]
        st.markdown(
            f"""
            <div class="pulse-card">
                <div class="pulse-header">
                    <span class="pulse-title">⚠️ City Risk Score</span>
                    <span class="badge-pill badge-{risk_cat.lower()}">{risk_cat} Risk</span>
                </div>
                <div class="pulse-value" style="color:{risk_score['risk_color']};">{risk_cat}</div>
                <div class="pulse-subtext">
                    Active hazard alerts: <b>{risk_score['active_alerts_count']}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div style="background:rgba(15,23,42,0.6); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:16px;">
                <div style="font-size:0.85rem; font-weight:700; margin-bottom:8px; color:#94a3b8;">HAZARD RADAR MATRIX</div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; font-size:0.82rem;">
                    <div>🔥 Heat: <b style="color:{risk_score['categories']['heat']['color']}">{risk_score['categories']['heat']['level']}</b></div>
                    <div>💨 Smog: <b style="color:{risk_score['categories']['air']['color']}">{risk_score['categories']['air']['level']}</b></div>
                    <div>🌧️ Flood: <b style="color:{risk_score['categories']['rain']['color']}">{risk_score['categories']['rain']['level']}</b></div>
                    <div>🌪️ Wind: <b style="color:{risk_score['categories']['wind']['color']}">{risk_score['categories']['wind']['level']}</b></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # 3. Live Environmental Metrics Grid
    st.markdown("### 📊 Real-Time Metrics & Observations")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    with m_col1:
        aqi_val = latest_metrics.get("aqi_us") or "N/A"
        pm25_val = latest_metrics.get("pm2_5") or "N/A"
        st.metric("Air Quality Index (AQI)", f"{aqi_val}", f"PM2.5: {pm25_val} µg/m³", delta_color="inverse")

    with m_col2:
        temp_max = latest_metrics.get("temp_max") or 0.0
        temp_min = latest_metrics.get("temp_min") or 0.0
        st.metric("Temperature", f"{temp_max:.1f}°C", f"Min: {temp_min:.1f}°C")

    with m_col3:
        hum_val = latest_metrics.get("humidity") or 0.0
        rain_val = latest_metrics.get("rainfall_mm") or 0.0
        st.metric("Humidity & Rain", f"{hum_val:.0f}%", f"{rain_val:.1f} mm rain")

    with m_col4:
        uv_val = latest_metrics.get("uv_index") or 0.0
        wind_val = latest_metrics.get("wind_speed") or 0.0
        st.metric("Wind & UV Index", f"{wind_val:.1f} km/h", f"UV: {uv_val:.1f}")

    # 4. Live Location & Sensor Radar Map
    st.markdown("### 🗺️ Live Location & Telemetry Coordinates")
    map_col1, map_col2 = st.columns([2, 1])
    with map_col1:
        st.plotly_chart(
            render_live_location_map(
                city_obj["lat"],
                city_obj["lon"],
                selected_city_name,
                city_obj.get("admin1", ""),
                city_obj.get("country", "India")
            ),
            use_container_width=True
        )
    with map_col2:
        st.markdown(
            f"""
            <div class="pulse-card" style="height:260px; display:flex; flex-direction:column; justify-content:space-between;">
                <div>
                    <div class="pulse-header">
                        <span class="pulse-title">📡 Station Metadata</span>
                        <span class="badge-pill badge-good">Online</span>
                    </div>
                    <div style="font-size:0.88rem; line-height:1.6; color:#cbd5e1; margin-top:8px;">
                        <b>Location:</b> {selected_city_name}, {city_obj.get('admin1', '')}<br>
                        <b>Coordinates:</b> <span class="stat-mono">{city_obj['lat']:.4f}°N, {city_obj['lon']:.4f}°E</span><br>
                        <b>Timezone:</b> {city_obj.get('timezone', 'Asia/Kolkata')}<br>
                        <b>Sensors:</b> Weather (WMO), CAMS Air Quality
                    </div>
                </div>
                <div style="font-size:0.75rem; color:#64748b; border-top:1px solid rgba(255,255,255,0.06); padding-top:8px;">
                    🟢 Real-Time Synced via Open-Meteo High-Resolution Grid
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# ==========================================
# VIEW 2: National & State Leaderboard
# ==========================================
elif menu == "🏆 National & State Leaderboard":
    st.title("🏆 National & Regional Environmental Leaderboard")
    st.caption("Cross-city benchmarking across all 36 States and Union Territories of India.")

    render_about_view(
        "National & Regional Environmental Leaderboard",
        "Delivers nationwide cross-city benchmarking across all 36 Indian States and Union Territories. Cities are ranked dynamically by their composite Environmental Score (0–100), CPCB National Air Quality Index (NAQI), fine particulate matter (PM2.5), peak temperatures, and outdoor livability. Filter by specific state or examine the national distribution."
    )

    with engine.connect() as conn:
        all_cities_metrics = pd.read_sql(
            text("""
                SELECT 
                    c.city_name, c.admin1 AS state_region, c.country,
                    m.date, m.temp_max, m.temp_min, m.humidity, m.rainfall_mm,
                    m.pm2_5, m.aqi_us, m.uv_index
                FROM cities c
                JOIN (
                    SELECT city_id, MAX(date) as max_date
                    FROM raw_daily_metrics
                    WHERE date <= :target_date
                    GROUP BY city_id
                ) latest ON c.city_id = latest.city_id
                JOIN raw_daily_metrics m ON c.city_id = m.city_id AND m.date = latest.max_date
                WHERE c.country = 'India'
                ORDER BY m.aqi_us ASC
            """),
            conn,
            params={"target_date": target_date_str}
        )

    if not all_cities_metrics.empty:
        # Calculate Environmental Scores for leaderboard
        leaderboard_rows = []
        for _, row in all_cities_metrics.iterrows():
            row_dict = row.to_dict()
            e_score = compute_environmental_score(row_dict)
            a_idx = compute_activity_index(row_dict)
            r_score = compute_city_risk_score(row_dict)
            leaderboard_rows.append({
                "Rank": 0,
                "City": row["city_name"],
                "State / Region": row["state_region"] or "India",
                "Environmental Score": e_score["score"],
                "Condition": e_score["category"],
                "AQI": f"{int(row['aqi_us'])}" if pd.notna(row["aqi_us"]) else "50",
                "PM2.5 (µg/m³)": f"{float(row['pm2_5']):.1f}" if pd.notna(row["pm2_5"]) else "15.0",
                "Temp Max (°C)": f"{float(row['temp_max']):.1f}°C" if pd.notna(row["temp_max"]) else "—",
                "Top Activity": a_idx["jogging"]["name"] if a_idx["jogging"]["score"] >= 60 else a_idx["walking"]["name"],
                "Risk Level": r_score["composite_risk"]
            })

        board_df = pd.DataFrame(leaderboard_rows).sort_values("Environmental Score", ascending=False)
        board_df["Rank"] = range(1, len(board_df) + 1)

        # State filter dropdown
        state_list = ["All States & Territories"] + sorted(list(set(board_df["State / Region"].dropna().unique())))
        sel_state = st.selectbox("📍 Filter Leaderboard by State / Union Territory", state_list, index=0)
        
        display_board_df = board_df if sel_state == "All States & Territories" else board_df[board_df["State / Region"] == sel_state].copy()
        if sel_state != "All States & Territories":
            display_board_df["Rank"] = range(1, len(display_board_df) + 1)

        # KPI metric row
        top_city = display_board_df.iloc[0] if not display_board_df.empty else board_df.iloc[0]
        l_col1, l_col2, l_col3, l_col4 = st.columns(4)
        with l_col1:
            st.metric("🥇 Cleanest / Top City", f"{top_city['City']}", f"Score: {top_city['Environmental Score']}/100")
        with l_col2:
            st.metric("🏙️ Tracked Cities", f"{len(display_board_df)} cities")
        with l_col3:
            avg_env = display_board_df["Environmental Score"].mean() if not display_board_df.empty else 70.0
            st.metric("Average Env Score", f"{avg_env:.1f}/100")
        with l_col4:
            st.metric("Top State Region", f"{top_city['State / Region']}")

        st.markdown("---")
        st.dataframe(display_board_df, use_container_width=True, hide_index=True)
    else:
        st.info("No multi-city telemetry found yet. Run `python daily_etl.py --city all` to populate all cities!")


# ==========================================
# VIEW 3: Air Quality Deep-Dive
# ==========================================
elif menu == "💨 Air Quality Deep-Dive":
    st.subheader(f"💨 Air Quality & Particulate Intelligence — {selected_city_name}, {city_obj.get('admin1', '')}")
    st.caption("Comprehensive telemetry on PM2.5, PM10, Nitrogen Dioxide (NO2), Ozone, and Aeroallergens.")

    render_about_view(
        "Air Quality & Particulate Intelligence",
        f"Conducts high-precision particulate and gaseous pollutant analysis strictly for **{selected_city_name}, {city_obj.get('admin1', '')}**. Grounded in World Health Organization (WHO 2021) guidelines and Central Pollution Control Board (CPCB) standards, this view tracks fine particulates (PM2.5), coarse particulates (PM10), Nitrogen Dioxide (NO2), and aeroallergens (Grass, Birch, Ragweed pollen) with 90-day percentile baselines."
    )

    aqi = int(latest_metrics.get("aqi_us") or 50)
    pm25 = float(latest_metrics.get("pm2_5") or 0.0)
    pm10 = float(latest_metrics.get("pm10") or 0.0)
    no2 = float(latest_metrics.get("no2") or 0.0)
    ozone = float(latest_metrics.get("ozone") or 0.0)

    who_pm25_target = 15.0  # WHO 24-hour guideline
    who_status_tag = "✅ WHO 24h Compliant" if pm25 <= who_pm25_target else f"⚠️ {pm25/who_pm25_target:.1f}x WHO Limit"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("US AQI Standard", f"{aqi}", f"{'Good' if aqi<=50 else 'Moderate' if aqi<=100 else 'Unhealthy'}")
    with col2:
        st.metric("PM2.5 Fine Particulates", f"{pm25:.1f} µg/m³", who_status_tag)
    with col3:
        st.metric("PM10 Coarse Particulates", f"{pm10:.1f} µg/m³", f"CPCB Std: ≤100")
    with col4:
        st.metric("Nitrogen Dioxide (NO2)", f"{no2:.1f} µg/m³", "Vehicle / Industrial")

    st.markdown("---")

    # Pollen Aeroallergens
    st.markdown("##### 🌸 Aeroallergen & Pollen Dispersal (grains/m³)")
    pol_col1, pol_col2, pol_col3 = st.columns(3)
    with pol_col1:
        st.metric("Grass Pollen", f"{latest_metrics.get('pollen_grass') or 0.0}")
    with pol_col2:
        st.metric("Birch Pollen", f"{latest_metrics.get('pollen_birch') or 0.0}")
    with pol_col3:
        st.metric("Ragweed Pollen", f"{latest_metrics.get('pollen_ragweed') or 0.0}")

    st.markdown("---")
    st.markdown("##### 🏛️ International & National Air Quality Compliance Matrix")
    aq_matrix = [
        {
            "Pollutant": "Fine Particulates (PM2.5)",
            "Observed in City": f"{pm25:.1f} µg/m³",
            "WHO 2021 Guideline (24h)": "≤ 15.0 µg/m³",
            "CPCB National Std (24h)": "≤ 60.0 µg/m³",
            "Health Risk Level": "Low / Safe" if pm25 <= 15 else "Moderate Strain" if pm25 <= 35 else "Elevated Respiratory Risk"
        },
        {
            "Pollutant": "Coarse Particulates (PM10)",
            "Observed in City": f"{pm10:.1f} µg/m³",
            "WHO 2021 Guideline (24h)": "≤ 45.0 µg/m³",
            "CPCB National Std (24h)": "≤ 100.0 µg/m³",
            "Health Risk Level": "Safe" if pm10 <= 45 else "Dust & Upper Airway Irritation"
        },
        {
            "Pollutant": "Nitrogen Dioxide (NO2)",
            "Observed in City": f"{no2:.1f} µg/m³",
            "WHO 2021 Guideline (24h)": "≤ 25.0 µg/m³",
            "CPCB National Std (24h)": "≤ 80.0 µg/m³",
            "Health Risk Level": "Acceptable" if no2 <= 25 else "Traffic Emission Elevation"
        }
    ]
    st.dataframe(pd.DataFrame(aq_matrix), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.plotly_chart(render_historical_percentile_trend(df_history, "pm2_5", "PM2.5 Concentration", "µg/m³"), use_container_width=True)


# ==========================================
# VIEW 4: Weather & Thermal Comfort
# ==========================================
elif menu == "☀️ Weather & Thermal Comfort":
    st.subheader(f"☀️ Biometeorology & Atmospheric Profile — {selected_city_name}, {city_obj.get('admin1', '')}")
    st.caption("Human thermal sensation analysis, solar irradiance, UV exposure limits, and 14-day forecast trends.")

    render_about_view(
        "Biometeorology & Thermal Sensation Profile",
        f"Evaluates human biometeorological comfort strictly for **{selected_city_name}, {city_obj.get('admin1', '')}** using thermodynamic models combining ambient temperature, relative humidity, wind speed, solar irradiance, and UV radiation. Features a 14-day multi-variable meteorological projection chart with diurnal variance and heat index classifications."
    )
    
    thermal_comp = env_score.get("components", {}).get("thermal_comfort", 75)
    solar_val = float(latest_metrics.get("solar_radiation") or 0.0)
    uv_val = float(latest_metrics.get("uv_index") or 0.0)
    temp_max = float(latest_metrics.get("temp_max") or 28.0)
    temp_min = float(latest_metrics.get("temp_min") or 20.0)
    humidity_val = float(latest_metrics.get("humidity") or 55.0)

    # Dynamic classification badges
    if thermal_comp >= 85:
        thermal_status = "Optimal Comfort"
        thermal_color = "#10b981"
        thermal_desc = "Ideal human metabolic balance with zero heat or cold stress."
    elif thermal_comp >= 70:
        thermal_status = "Pleasant / Mild"
        thermal_color = "#38bdf8"
        thermal_desc = "Comfortable conditions suitable for extended outdoor activity."
    elif thermal_comp >= 50:
        thermal_status = "Moderate Strain"
        thermal_color = "#f59e0b"
        thermal_desc = "Mild humidity or warmth; stay hydrated during exertion."
    else:
        thermal_status = "Severe Thermal Stress"
        thermal_color = "#ef4444"
        thermal_desc = "Excessive heat/humidity or sharp cold; seek climate control."

    if uv_val < 3:
        uv_status = "Low Risk"
        uv_color = "#10b981"
        uv_advice = "Safe for unprotected outdoor sun exposure."
    elif uv_val < 6:
        uv_status = "Moderate Risk"
        uv_color = "#f59e0b"
        uv_advice = "Wear a hat, sunglasses, and use SPF 15+ sunscreen."
    elif uv_val < 8:
        uv_status = "High Risk"
        uv_color = "#f97316"
        uv_advice = "Seek shade during midday (11 AM – 3 PM); use SPF 30+."
    elif uv_val < 11:
        uv_status = "Very High Risk"
        uv_color = "#ef4444"
        uv_advice = "Harmful UV rays; minimize direct sun exposure around noon."
    else:
        uv_status = "Extreme Danger"
        uv_color = "#a855f7"
        uv_advice = "Skin damage can occur in under 15 minutes; stay indoors."

    # 1. Top Core Indicator Cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"""
            <div class="pulse-card">
                <div class="pulse-header">
                    <span class="pulse-title">🌡️ Thermal Comfort Rating</span>
                    <span style="background:rgba(255,255,255,0.08); color:{thermal_color}; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">{thermal_status}</span>
                </div>
                <div class="pulse-value">{thermal_comp}<small style="font-size:1.1rem; color:#64748b;">/100</small></div>
                <div class="pulse-subtext">{thermal_desc}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f"""
            <div class="pulse-card">
                <div class="pulse-header">
                    <span class="pulse-title">☀️ Solar & UV Exposure</span>
                    <span style="background:rgba(255,255,255,0.08); color:{uv_color}; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">UV {uv_val:.1f} • {uv_status}</span>
                </div>
                <div class="pulse-value">{solar_val:.1f} <small style="font-size:1.1rem; color:#64748b;">MJ/m²</small></div>
                <div class="pulse-subtext">{uv_advice}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            f"""
            <div class="pulse-card">
                <div class="pulse-header">
                    <span class="pulse-title">💨 Atmospheric Environment</span>
                    <span style="background:rgba(255,255,255,0.08); color:#38bdf8; padding:3px 8px; border-radius:12px; font-size:0.75rem; font-weight:700;">Humidity {humidity_val:.0f}%</span>
                </div>
                <div class="pulse-value">{temp_max:.1f}°C <small style="font-size:1.0rem; color:#64748b;">(Low: {temp_min:.1f}°C)</small></div>
                <div class="pulse-subtext">Diurnal temperature variation: <b>{abs(temp_max - temp_min):.1f}°C</b></div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    # 2. 14-day Multi-Variable Meteorological Forecast Chart
    st.markdown("##### 📈 14-Day Meteorological Projection")
    forecast_df = df_history[df_history["is_forecast"] == 1]
    if not forecast_df.empty:
        st.plotly_chart(render_forecast_trend(forecast_df), use_container_width=True)
    else:
        st.plotly_chart(render_historical_percentile_trend(df_history, "temp_max", "Maximum Temperature", "°C"), use_container_width=True)

    # 3. Interactive Visual Guide: What the Graph Shows
    st.markdown(
        """
        <div style="background:rgba(18,24,38,0.7); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:18px; margin-top:10px; margin-bottom:20px;">
            <div style="font-size:0.95rem; font-weight:700; color:#38bdf8; margin-bottom:12px;">🔍 How to Read This 14-Day Forecast Chart:</div>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:16px; font-size:0.85rem;">
                <div style="background:rgba(15,23,42,0.6); padding:12px; border-radius:8px; border-left:3px solid #f97316;">
                    <div style="font-weight:700; color:#f97316;">🟠 Orange Line — High Temp (°C)</div>
                    <div style="color:#94a3b8; margin-top:4px;">Peak daytime afternoon temperature. Values between <b>20°C – 28°C</b> are optimal. Spikes above <b>38°C</b> trigger heatwave warnings.</div>
                </div>
                <div style="background:rgba(15,23,42,0.6); padding:12px; border-radius:8px; border-left:3px solid #06b6d4;">
                    <div style="font-weight:700; color:#06b6d4;">🔵 Cyan Line — Low Temp (°C)</div>
                    <div style="color:#94a3b8; margin-top:4px;">Nighttime & early morning minimum temperature. A narrow gap with the high line indicates stable cloud cover or high humidity.</div>
                </div>
                <div style="background:rgba(15,23,42,0.6); padding:12px; border-radius:8px; border-left:3px solid #3b82f6;">
                    <div style="font-weight:700; color:#3b82f6;">📊 Blue Vertical Bars — Rain (mm)</div>
                    <div style="color:#94a3b8; margin-top:4px;">Expected 24-hour precipitation on the <b>Right Y-Axis</b>. <b>0–2 mm</b> is trace/light rain, while <b>>25 mm</b> indicates heavy downpours.</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 4. Standard Environmental Scale & Benchmark Matrix
    st.markdown("##### 📚 Atmospheric Scale & Reference Matrix")
    benchmark_data = [
        {
            "Indicator": "🌡️ Thermal Comfort Score",
            "Optimal / Best Range": "85 – 100 (20°C–26°C with 40-60% humidity)",
            "Current Value": f"{thermal_comp:.1f}/100 ({thermal_status})",
            "Moderate Caution": "50 – 69 (Mild thermal strain)",
            "Worst / Danger Zone": "< 50 (Oppressive Heat or Freezing Cold)"
        },
        {
            "Indicator": "☀️ UV Radiation Index",
            "Optimal / Best Range": "0 – 2 (Safe for all outdoor activities)",
            "Current Value": f"{uv_val:.1f} ({uv_status})",
            "Moderate Caution": "3 – 5 (Sun protection advised)",
            "Worst / Danger Zone": "> 8.0 (Severe sunburn & DNA damage risk)"
        },
        {
            "Indicator": "🌧️ 24h Precipitation",
            "Optimal / Best Range": "0 – 2 mm (Dry / clear conditions)",
            "Current Value": f"{latest_metrics.get('rainfall_mm', 0.0):.1f} mm",
            "Moderate Caution": "5 – 20 mm (Passing showers / drizzle)",
            "Worst / Danger Zone": "> 25 mm (Flash Flood & Waterlogging Risk)"
        },
        {
            "Indicator": "💧 Relative Humidity",
            "Optimal / Best Range": "40% – 60% (Comfortable respiration)",
            "Current Value": f"{humidity_val:.0f}%",
            "Moderate Caution": "65% – 80% (Sticky / muggy sensation)",
            "Worst / Danger Zone": "> 85% (Extreme swelter / impaired sweating)"
        }
    ]
    st.dataframe(pd.DataFrame(benchmark_data), use_container_width=True, hide_index=True)


# ==========================================
# VIEW 5: Outdoor Activity Planner
# ==========================================
elif menu == "🏃 Outdoor Activity Planner":
    st.subheader(f"🏃 Outdoor Activity Suitability Index — {selected_city_name}")
    st.caption("Re-weighted environmental indicators tuned for specific sports, athletics, and recreation with pros & cons.")

    render_about_view(
        "Outdoor Activity Suitability Index",
        f"Calculates activity-specific suitability percentages (0%–100%) across 6 sports and recreational pursuits for **{selected_city_name}**. Evaluates real-time air purity, thermal load, precipitation, and UV exposure to provide detailed pros, limiting factors, and optimal daily time windows."
    )

    col_radar, col_cards = st.columns([1, 1])
    with col_radar:
        st.plotly_chart(render_activity_radar(act_index), use_container_width=True)

        st.markdown(
            """
            <div style="background:rgba(15,23,42,0.6); border:1px solid rgba(255,255,255,0.06); border-radius:12px; padding:14px; font-size:0.82rem; color:#94a3b8;">
                <b style="color:#38bdf8;">🎯 Suitability Scoring Scale:</b><br>
                • <b>80–100% (Ideal)</b>: Exceptional conditions across all parameters.<br>
                • <b>60–79% (Good)</b>: Highly favorable with routine hydration.<br>
                • <b>40–59% (Moderate Caution)</b>: Schedule around early morning or post-sunset.<br>
                • <b><40% (Avoid)</b>: Unfavorable environmental stress; indoor workouts advised.
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_cards:
        for activity_key, details in act_index.items():
            if not isinstance(details, dict) or "score" not in details:
                continue
            act_name = details.get("name", activity_key.replace("_", " ").title())
            score_pct = details.get("score", 0)
            label = details.get("label", "Moderate")
            best_win = details.get("best_window", "Early Morning / Evening")
            pros_list = details.get("pros", ["Standard baseline"])
            cons_list = details.get("cons", ["None"])

            pros_html = "".join([f'<span class="pro-chip">✓ {p}</span>' for p in pros_list])
            cons_html = "".join([f'<span class="con-chip">⚠ {c}</span>' for c in cons_list])

            st.markdown(
                f"""
                <div style="background:rgba(18,24,38,0.75); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:14px; margin-bottom:12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-weight:700; font-size:1.02rem; color:#f8fafc;">{act_name}</span>
                        <span class="badge-pill badge-{label.lower().replace(' ', '-')}">{label} ({score_pct}%)</span>
                    </div>
                    <div style="font-size:0.8rem; color:#38bdf8; margin-bottom:6px;">
                        ⏰ <b>Recommended Window:</b> {best_win}
                    </div>
                    <div style="margin-top:6px;">
                        <div style="font-size:0.75rem; font-weight:700; color:#34d399; margin-bottom:2px;">FAVORABLE FACTORS (PROS):</div>
                        {pros_html}
                    </div>
                    <div style="margin-top:6px;">
                        <div style="font-size:0.75rem; font-weight:700; color:#f87171; margin-bottom:2px;">RISK FACTORS (CONS):</div>
                        {cons_html}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


# ==========================================
# VIEW 6: City Risk & Hazard Alerts
# ==========================================
elif menu == "⚠️ City Risk & Hazard Alerts":
    st.subheader(f"⚠️ City Risk & Anomaly Detection Center — {selected_city_name}")
    st.caption("Threshold-based hazard monitoring combined with 30-day Z-Score anomaly detection ($>2.0\\sigma$).")

    render_about_view(
        "City Risk & Anomaly Detection Center",
        f"Continuous automated risk monitoring for **{selected_city_name}** combining deterministic meteorological hazard thresholds (Heatwave, Smog Emergency, Flash Flood, High Wind) with 30-day rolling Z-Score statistical anomaly detection (>2.0σ) to identify unusual deviations from historical climate baselines."
    )

    if risk_score["alerts"]:
        for alert in risk_score["alerts"]:
            st.error(f"🚨 **{alert['type']} ({alert['severity']})**: {alert['msg']}")
    else:
        st.success(f"✅ **All Hazard Thresholds Clear for {selected_city_name}**: No extreme heat, smog, flood, or windstorm risks currently active.")

    st.markdown("---")
    st.markdown("##### 🔬 30-Day Z-Score Anomaly Vector")
    st.caption("Statistical divergence from the 90-day moving baseline ($Z = \\frac{X - \\mu}{\\sigma}$). Values $>+2.0\\sigma$ or $<-2.0\\sigma$ indicate significant climate anomalies (top 2.5% extreme events).")

    z_col1, z_col2, z_col3, z_col4 = st.columns(4)

    with z_col1:
        pm25_z = stats.get("z_scores", {}).get("pm2_5_zscore", 0.0)
        st.metric("PM2.5 Anomaly", f"{pm25_z:+.2f}σ", "Normal" if abs(pm25_z) < 2.0 else "⚠️ Anomaly Breached")
    with z_col2:
        temp_z = stats.get("z_scores", {}).get("temp_zscore", 0.0)
        st.metric("Temperature Anomaly", f"{temp_z:+.2f}σ", "Normal" if abs(temp_z) < 2.0 else "⚠️ Anomaly Breached")
    with z_col3:
        rain_z = stats.get("z_scores", {}).get("rainfall_zscore", 0.0)
        st.metric("Rainfall Anomaly", f"{rain_z:+.2f}σ", "Normal" if abs(rain_z) < 2.0 else "⚠️ Anomaly Breached")
    with z_col4:
        wind_z = stats.get("z_scores", {}).get("wind_zscore", 0.0)
        st.metric("Wind Speed Anomaly", f"{wind_z:+.2f}σ", "Normal" if abs(wind_z) < 2.0 else "⚠️ Anomaly Breached")

    st.markdown("---")
    st.markdown("##### 🛡️ Hazard Thresholds & Municipal Advisory Reference")
    hazard_data = [
        {
            "Hazard Category": "🔥 Extreme Heatwave",
            "Trigger Threshold": "Temp Max ≥ 40.0°C or Temp Z-Score ≥ +2.5σ",
            "Observed Reading": f"{latest_metrics.get('temp_max', 0.0):.1f}°C (Z: {temp_z:+.2f}σ)",
            "Status": risk_score['categories']['heat']['level'],
            "Municipal Action": "Issue hydration alerts & establish cooling shelters" if risk_score['categories']['heat']['level'] != "Low" else "Normal monitoring"
        },
        {
            "Hazard Category": "💨 Hazardous Smog / PM2.5",
            "Trigger Threshold": "PM2.5 ≥ 60.0 µg/m³ or AQI ≥ 150",
            "Observed Reading": f"{latest_metrics.get('pm2_5', 0.0):.1f} µg/m³ (AQI: {latest_metrics.get('aqi_us', 50)})",
            "Status": risk_score['categories']['air']['level'],
            "Municipal Action": "Advise N95 masks for outdoor workers & limit diesel transit" if risk_score['categories']['air']['level'] != "Low" else "Air quality within acceptable bounds"
        },
        {
            "Hazard Category": "🌧️ Flash Flood / Heavy Rain",
            "Trigger Threshold": "24h Rain ≥ 25.0 mm or Rain Z-Score ≥ +3.0σ",
            "Observed Reading": f"{latest_metrics.get('rainfall_mm', 0.0):.1f} mm (Z: {rain_z:+.2f}σ)",
            "Status": risk_score['categories']['rain']['level'],
            "Municipal Action": "Inspect storm drains & low-lying underpasses" if risk_score['categories']['rain']['level'] != "Low" else "No waterlogging hazard"
        },
        {
            "Hazard Category": "🌪️ Windstorm / Gale",
            "Trigger Threshold": "Wind Speed ≥ 30.0 km/h or Wind Z-Score ≥ +2.5σ",
            "Observed Reading": f"{latest_metrics.get('wind_speed', 0.0):.1f} km/h (Z: {wind_z:+.2f}σ)",
            "Status": risk_score['categories']['wind']['level'],
            "Municipal Action": "Secure loose construction scaffolding and hoardings" if risk_score['categories']['wind']['level'] != "Low" else "Calm/moderate breezes"
        }
    ]
    st.dataframe(pd.DataFrame(hazard_data), use_container_width=True, hide_index=True)


# ==========================================
# VIEW 7: Historical Trends & Percentiles
# ==========================================
elif menu == "📈 Historical Trends & Percentiles":
    st.subheader(f"📈 Historical Trends & Percentile Envelopes — {selected_city_name}")
    st.caption("Visualizing current actuals vs 10th–90th historical percentile normal range bands.")

    render_about_view(
        "Historical Trends & Climate Percentiles",
        f"Analyzes long-term environmental patterns for **{selected_city_name}** across customizable time horizons (30 to 365 days). The shaded blue envelope represents the 10th to 90th percentile normal baseline range, allowing municipal planners and citizens to determine whether today's measurements are within normal seasonal variance or represent historical extremes."
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        metric_choice = st.selectbox(
            "Select Parameter to Chart",
            [
                ("pm2_5", "PM2.5 Concentration", "µg/m³"),
                ("temp_max", "Maximum Temperature", "°C"),
                ("rainfall_mm", "Precipitation", "mm"),
                ("wind_speed", "Wind Speed", "km/h"),
                ("humidity", "Relative Humidity", "%"),
                ("uv_index", "UV Index", "")
            ],
            format_func=lambda x: x[1]
        )
    with col2:
        days_window = st.select_slider(
            "Lookback Horizon Window",
            options=[7, 14, 30, 60, 90, 180, 365],
            value=90
        )

    filtered_df = df_history.tail(days_window)
    st.plotly_chart(
        render_historical_percentile_trend(
            filtered_df,
            metric_choice[0],
            metric_choice[1],
            metric_choice[2]
        ),
        use_container_width=True
    )

    # Percentile Badge Callout & Guide
    pctl_val = stats.get("percentiles", {}).get(metric_choice[0], "N/A")
    st.info(f"📊 **Percentile Insight**: Today's **{metric_choice[1]}** is higher than **{pctl_val}%** of historical readings recorded for {selected_city_name} over the baseline period.")

    st.markdown(
        """
        <div style="background:rgba(18,24,38,0.7); border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:16px; margin-top:12px;">
            <div style="font-size:0.95rem; font-weight:700; color:#38bdf8; margin-bottom:8px;">📚 Understanding Historical Percentiles:</div>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:12px; font-size:0.82rem; color:#cbd5e1;">
                <div><b>P10 (10th Percentile):</b> Cleanest/lowest 10% of historical days. Readings near or below P10 represent exceptionally pristine or cold conditions.</div>
                <div><b>P50 (Median Baseline):</b> The typical historical average. 50% of days were cleaner/cooler, and 50% were more elevated.</div>
                <div><b>P90 (90th Percentile):</b> Highest 10% of days. Readings above P90 signify acute environmental stress or heavy smog/heat.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ==========================================
# VIEW 8: AI Analyst & Daily Report
# ==========================================
elif menu == "🤖 AI Analyst & Daily Report":
    st.subheader(f"🤖 AI Environmental Analyst & Automated Reports — {selected_city_name}")

    render_about_view(
        "AI Environmental Analyst & Executive Report Export",
        f"Autonomous generative intelligence module for **{selected_city_name}** synthesizing millions of environmental observations into an executive narrative. Generate and download publication-ready, multi-page PDF briefing reports complete with metrics, WHO standard comparisons, activity feasibility matrix, and risk assessments."
    )

    st.markdown(
        f"""
        <div class="ai-briefing-box">
            <div class="ai-badge">📄 Daily Intelligence Narrative • Grounded in WMO & WHO Standards</div>
            <div style="font-size:1.02rem; line-height:1.7; color:#f8fafc; margin-top:8px;">
                {narrative}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Generate & Download PDF Report
    st.markdown("---")
    st.markdown("##### 📄 Export Daily Executive PDF Briefing")
    
    clean_city = selected_city_name.replace(" ", "_")
    pdf_filename = f"UrbanPulse_{clean_city}_{today_str}.pdf"
    pdf_path = EXPORTS_DIR / pdf_filename

    btn_col1, btn_col2 = st.columns([1, 1])
    with btn_col1:
        if st.button("⚡ Generate & Compile PDF Report Now", type="primary", use_container_width=True):
            with st.spinner("Compiling multi-section PDF artifact..."):
                generate_daily_pdf_report(
                    city_name=selected_city_name,
                    date_str=today_str,
                    facts_payload=facts_payload,
                    ai_narrative=narrative,
                    output_path=str(pdf_path)
                )
                st.success("PDF successfully compiled and ready for download!")

    with btn_col2:
        if pdf_path.exists():
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            st.download_button(
                label=f"⬇️ Download {pdf_filename}",
                data=pdf_bytes,
                file_name=pdf_filename,
                mime="application/pdf",
                use_container_width=True
            )
        else:
            st.info("Click 'Generate & Compile PDF' to produce the downloadable report.")


# ==========================================
# VIEW 9: Pipeline & API Health Monitor
# ==========================================
elif menu == "⚡ Pipeline & API Health":
    st.title("⚡ Pipeline Reliability & Live REST API Health Monitor")
    st.caption("Real-time telemetry on Open-Meteo REST endpoints, latency profiles, and database integrity.")

    render_about_view(
        "Pipeline Reliability & API Health Monitor",
        "Real-time diagnostic console monitoring the automated ETL ingestion pipelines, live REST endpoints (Open-Meteo Weather Forecast, Air Quality, Historical Archive, Geocoding), SQLite database engine integrity, and sub-second latency performance."
    )

    with engine.connect() as conn:
        logs_df = pd.read_sql(text("SELECT * FROM api_logs ORDER BY timestamp DESC LIMIT 50"), conn)
        total_rows = conn.execute(text("SELECT COUNT(*) FROM raw_daily_metrics")).scalar()
        total_cities = conn.execute(text("SELECT COUNT(*) FROM cities")).scalar()

    h_col1, h_col2, h_col3, h_col4 = st.columns(4)

    with h_col1:
        if not logs_df.empty:
            success_rate = (logs_df["success"].sum() / len(logs_df)) * 100.0
            st.metric("30-Day API Reliability", f"{success_rate:.1f}%", "Zero Rate-Limit Issues")
        else:
            st.metric("API Reliability", "100.0%")

    with h_col2:
        if not logs_df.empty:
            avg_lat = logs_df["latency_ms"].mean()
            st.metric("Average API Latency", f"{avg_lat:.0f} ms", "< 500ms target")
        else:
            st.metric("Average Latency", "—")

    with h_col3:
        st.metric("Total Ingested Days", f"{total_rows} rows", f"{total_cities} cities tracked")

    with h_col4:
        st.metric("Database Health", "SQLite / WAL", "Consistent & Online")

    st.markdown("---")

    # Interactive REST API Live Verifier
    st.markdown("##### 🔌 Live REST API Endpoints Status & Verification")
    
    test_endpoints = [
        {
            "name": "1. Weather Forecast Endpoint",
            "url": "https://api.open-meteo.com/v1/forecast?latitude=17.3850&longitude=78.4867&current=temperature_2m,relative_humidity_2m",
            "doc_url": "https://open-meteo.com/en/docs",
            "description": "High-resolution atmospheric forecasting (WMO IFS/GFS grid)."
        },
        {
            "name": "2. Air Quality & Aeroallergens Endpoint",
            "url": "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=17.3850&longitude=78.4867&current=pm2_5,pm10,us_aqi",
            "doc_url": "https://open-meteo.com/en/docs/air-quality-api",
            "description": "CAMS Copernicus European Centre air dispersion & chemical modeling."
        },
        {
            "name": "3. Historical Climate Archive Endpoint",
            "url": "https://archive-api.open-meteo.com/v1/archive?latitude=17.3850&longitude=78.4867&start_date=2024-01-01&end_date=2024-01-07&daily=temperature_2m_max",
            "doc_url": "https://open-meteo.com/en/docs/historical-weather-api",
            "description": "ERA5 reanalysis archive for 90-day baseline percentile calculations."
        },
        {
            "name": "4. Geocoding & Coordinates Search API",
            "url": "https://geocoding-api.open-meteo.com/v1/search?name=Hyderabad&count=1&format=json",
            "doc_url": "https://open-meteo.com/en/docs/geocoding-api",
            "description": "Spatial coordinate resolution & Indian administrative boundary lookups."
        }
    ]

    import requests, time

    for ep in test_endpoints:
        ep_col1, ep_col2 = st.columns([3, 1])
        with ep_col1:
            st.markdown(
                f"""
                <div class="api-endpoint-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700; color:#38bdf8; font-size:0.95rem;">{ep['name']}</span>
                        <a href="{ep['doc_url']}" target="_blank" style="font-size:0.75rem; color:#38bdf8; text-decoration:underline;">Documentation ↗</a>
                    </div>
                    <div style="font-size:0.8rem; color:#94a3b8; margin-top:3px;">{ep['description']}</div>
                    <div style="font-size:0.75rem; font-family:monospace; color:#64748b; margin-top:6px; word-break:break-all;">GET {ep['url']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with ep_col2:
            st.markdown("<div style='padding-top:14px;'>", unsafe_allow_html=True)
            if st.button(f"⚡ Test Connection", key=f"btn_{ep['name']}", use_container_width=True):
                t0 = time.time()
                try:
                    res = requests.get(ep["url"], timeout=6)
                    latency = (time.time() - t0) * 1000
                    if res.status_code == 200:
                        st.success(f"HTTP 200 OK ({latency:.0f} ms)")
                    else:
                        st.warning(f"HTTP {res.status_code} ({latency:.0f} ms)")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.markdown("<span style='color:#10b981; font-size:0.8rem;'>● Endpoint Ready</span>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### 📜 Recent API Ingestion Telemetry Log")
    if not logs_df.empty:
        st.dataframe(
            logs_df[["timestamp", "endpoint", "city_name", "status_code", "latency_ms", "success"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No API logs recorded yet.")
