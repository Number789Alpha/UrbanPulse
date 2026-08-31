import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

# Standard Dark Plotly Layout Template
PLOT_LAYOUT_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(15, 23, 42, 0.4)",
    font=dict(family="Plus Jakarta Sans, sans-serif", color="#94a3b8"),
    margin=dict(l=30, r=30, t=40, b=30),
    hoverlabel=dict(bgcolor="#1e293b", font_size=12, font_family="Plus Jakarta Sans"),
    xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)")
)

def render_score_gauge(score: float, title: str = "Environmental Score", category: str = "Good", color: str = "#38bdf8") -> go.Figure:
    """Create a sleek circular speedometer gauge for 0-100 scores."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"<b>{title}</b><br><span style='font-size:0.8em;color:{color}'>{category}</span>", 'font': {'size': 16, 'color': '#f8fafc'}},
        number={'suffix': "/100", 'font': {'size': 32, 'color': '#f8fafc', 'family': 'Plus Jakarta Sans'}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "rgba(255,255,255,0.2)", 'tickfont': {'color': '#64748b'}},
            'bar': {'color': color, 'thickness': 0.28},
            'bgcolor': "rgba(255,255,255,0.04)",
            'borderwidth': 1,
            'bordercolor': "rgba(255,255,255,0.1)",
            'steps': [
                {'range': [0, 40], 'color': 'rgba(239, 68, 68, 0.15)'},
                {'range': [40, 70], 'color': 'rgba(245, 158, 11, 0.15)'},
                {'range': [70, 100], 'color': 'rgba(16, 185, 129, 0.15)'}
            ],
            'threshold': {
                'line': {'color': "#ffffff", 'width': 3},
                'thickness': 0.8,
                'value': score
            }
        }
    ))
    fig.update_layout(**PLOT_LAYOUT_DEFAULTS, height=240)
    return fig

def render_activity_radar(activity_dict: Dict[str, Any]) -> go.Figure:
    """Radar chart displaying the 6 Outdoor Activity sub-indices."""
    categories = [
        '🏃 Running',
        '🚴 Cycling',
        '⚽ Field Sports',
        '🚶 Walking',
        '📸 Photography',
        '☕ Open Dining'
    ]
    scores = [
        activity_dict.get('jogging', {}).get('score', 50),
        activity_dict.get('cycling', {}).get('score', 50),
        activity_dict.get('outdoor_sports', {}).get('score', 50),
        activity_dict.get('walking', {}).get('score', 50),
        activity_dict.get('photography', {}).get('score', 50),
        activity_dict.get('open_air_dining', {}).get('score', 50)
    ]
    # Close polygon
    categories_closed = categories + [categories[0]]
    scores_closed = scores + [scores[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=scores_closed,
        theta=categories_closed,
        fill='toself',
        fillcolor='rgba(16, 185, 129, 0.22)',
        line=dict(color='#10b981', width=2.5),
        name='Activity Score'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor="rgba(255,255,255,0.1)",
                linecolor="rgba(255,255,255,0.1)",
                tickfont=dict(color="#64748b", size=10)
            ),
            angularaxis=dict(
                gridcolor="rgba(255,255,255,0.1)",
                linecolor="rgba(255,255,255,0.1)",
                tickfont=dict(color="#f8fafc", size=12, family="Plus Jakarta Sans")
            ),
            bgcolor="rgba(15, 23, 42, 0.3)"
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=30, b=30),
        height=280,
        showlegend=False
    )
    return fig

def render_historical_percentile_trend(
    df: pd.DataFrame,
    metric_col: str,
    metric_name: str,
    unit: str = "",
    highlight_last: bool = True
) -> go.Figure:
    """
    Historical time-series chart with 10th-90th percentile normal range shading
    and 7-day moving average.
    """
    fig = go.Figure()
    if df.empty or metric_col not in df.columns:
        return fig

    clean_df = df.dropna(subset=["date", metric_col]).sort_values("date")
    if clean_df.empty:
        return fig

    # Calculate rolling baseline 10th and 90th percentiles for the normal range band
    rolling_10 = clean_df[metric_col].rolling(window=14, min_periods=3).quantile(0.10)
    rolling_90 = clean_df[metric_col].rolling(window=14, min_periods=3).quantile(0.90)
    rolling_7d = clean_df[metric_col].rolling(window=7, min_periods=1).mean()

    # 1. Shaded Normal Range Band (10th - 90th percentile)
    fig.add_trace(go.Scatter(
        x=clean_df["date"],
        y=rolling_90,
        mode="lines",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip"
    ))
    fig.add_trace(go.Scatter(
        x=clean_df["date"],
        y=rolling_10,
        mode="lines",
        line=dict(width=0),
        fill="tonexty",
        fillcolor="rgba(56, 189, 248, 0.12)",
        name="Historical Normal Range (10th-90th %ile)",
        hoverinfo="skip"
    ))

    # 2. Daily Recorded Actuals
    fig.add_trace(go.Scatter(
        x=clean_df["date"],
        y=clean_df[metric_col],
        mode="lines+markers",
        line=dict(color="#38bdf8", width=2),
        marker=dict(size=4, color="#38bdf8"),
        name=f"Daily {metric_name}",
        hovertemplate=f"<b>Date:</b> %{{x}}<br><b>{metric_name}:</b> %{{y:.1f}} {unit}<extra></extra>"
    ))

    # 3. 7-Day Moving Average
    fig.add_trace(go.Scatter(
        x=clean_df["date"],
        y=rolling_7d,
        mode="lines",
        line=dict(color="#f59e0b", width=2.5, dash="dash"),
        name="7-Day Moving Average",
        hovertemplate=f"<b>7d Avg:</b> %{{y:.1f}} {unit}<extra></extra>"
    ))

    # 4. Highlight latest point
    if highlight_last and len(clean_df) > 0:
        latest = clean_df.iloc[-1]
        fig.add_trace(go.Scatter(
            x=[latest["date"]],
            y=[latest[metric_col]],
            mode="markers",
            marker=dict(size=10, color="#ef4444", symbol="circle", line=dict(color="#ffffff", width=2)),
            name="Latest Observed",
            hovertemplate=f"<b>Latest:</b> %{{y:.1f}} {unit}<extra></extra>"
        ))

    fig.update_layout(
        **PLOT_LAYOUT_DEFAULTS,
        title=dict(text=f"<b>{metric_name} Trend vs Historical Normal Range</b>", font=dict(size=14, color="#f8fafc")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11)),
        height=340
    )
    return fig

def render_forecast_trend(forecast_df: pd.DataFrame) -> go.Figure:
    """14-day future environmental forecast trend chart."""
    fig = go.Figure()
    if forecast_df.empty:
        return fig

    fig.add_trace(go.Scatter(
        x=forecast_df["date"],
        y=forecast_df["temp_max"],
        mode="lines+markers",
        line=dict(color="#f97316", width=2.5),
        name="High Temp (°C)",
        hovertemplate="<b>Date:</b> %{x}<br><b>High:</b> %{y:.1f}°C<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=forecast_df["date"],
        y=forecast_df["temp_min"],
        mode="lines+markers",
        line=dict(color="#06b6d4", width=2.5),
        name="Low Temp (°C)",
        hovertemplate="<b>Date:</b> %{x}<br><b>Low:</b> %{y:.1f}°C<extra></extra>"
    ))

    # Rainfall bars on secondary y-axis if present
    if "rainfall_mm" in forecast_df.columns:
        fig.add_trace(go.Bar(
            x=forecast_df["date"],
            y=forecast_df["rainfall_mm"],
            name="Precipitation (mm)",
            marker=dict(color="rgba(59, 130, 246, 0.4)"),
            yaxis="y2",
            hovertemplate="<b>Rainfall:</b> %{y:.1f} mm<extra></extra>"
        ))

    fig.update_layout(
        **PLOT_LAYOUT_DEFAULTS,
        title=dict(text="<b>14-Day Temperature & Rain Forecast</b>", font=dict(size=14, color="#f8fafc")),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis2=dict(
            title=dict(text="Rain (mm)", font=dict(color="#3b82f6")),
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(color="#3b82f6")
        ),
        height=320
    )
    return fig

def render_live_location_map(lat: float, lon: float, city_name: str, admin1: str = "", country: str = "India") -> go.Figure:
    """Renders a sleek dark-matter map pin for the detected live location with coordinates."""
    subtitle = f"{admin1}, {country}".strip(", ")
    fig = go.Figure()
    
    # Outer radar glow ring
    fig.add_trace(go.Scattermap(
        lat=[lat],
        lon=[lon],
        mode='markers',
        marker=dict(size=28, color='rgba(16, 185, 129, 0.25)', symbol='circle'),
        hoverinfo='none',
        showlegend=False
    ))

    # Core active location marker
    fig.add_trace(go.Scattermap(
        lat=[lat],
        lon=[lon],
        mode='markers+text',
        marker=dict(size=14, color='#10b981', symbol='circle'),
        text=[f"📍 {city_name}"],
        textposition="top center",
        textfont=dict(size=13, color="#f8fafc", family="Plus Jakarta Sans"),
        hovertemplate=f"<b>{city_name}</b><br>{subtitle}<br>Lat: {lat:.4f}°N, Lon: {lon:.4f}°E<extra></extra>",
        showlegend=False
    ))

    fig.update_layout(
        map=dict(
            style="carto-darkmatter",
            center=dict(lat=lat, lon=lon),
            zoom=11
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=260
    )
    return fig

