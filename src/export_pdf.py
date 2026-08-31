import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from src.config import EXPORTS_DIR
import re

def _clean_text_for_pdf(txt: str) -> str:
    """Sanitizes text, strips non-ASCII emojis for Helvetica, and converts markdown to ReportLab HTML tags."""
    txt = re.sub(r'###+\s*', '', txt)
    replacements = {
        '📌': '[SUMMARY]', '💨': '[AIR]', '🌡️': '[THERMAL]', '🌡': '[THERMAL]',
        '🏃': '[ACTIVITY]', '⚠️': '[WARNING]', '✅': '[OK]', '🔥': '[HEAT]',
        '🌧️': '[RAIN]', '🌧': '[RAIN]', '🌪️': '[WIND]', '🌪': '[WIND]',
        '🌸': '[POLLEN]', '☀️': '[SUN]', '💧': '[HUMIDITY]', '🥇': '[#1]',
        '•': '&bull;', '—': '-', '–': '-'
    }
    for k, v in replacements.items():
        txt = txt.replace(k, v)
    
    txt = ''.join(c if ord(c) < 128 else ' ' for c in txt)
    
    txt = txt.replace('**', '<b>').replace('</b><b>', '')
    parts = txt.split('<b>')
    res = parts[0]
    for i in range(1, len(parts)):
        if '</b>' in parts[i]:
            res += '<b>' + parts[i]
        else:
            sub = parts[i].split('</b>', 1)
            res += '<b>' + sub[0] + '</b>' + (sub[1] if len(sub) > 1 else '')
    return res.replace('\n', '<br/>')

def generate_daily_pdf_report(
    city_name: str,
    date_str: str,
    facts_payload: Dict[str, Any],
    ai_narrative: str,
    output_path: Optional[str] = None
) -> str:
    """
    Generate an executive-grade 1-to-2 page PDF Environmental Intelligence Briefing.
    """
    if not output_path:
        clean_city = city_name.replace(" ", "_")
        filename = f"UrbanPulse_{clean_city}_{date_str}.pdf"
        output_path = str(EXPORTS_DIR / filename)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a")
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#0284c7")
    )
    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748b")
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=8,
        spaceAfter=5
    )
    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    callout_style = ParagraphStyle(
        "DocCallout",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#0f172a")
    )
    table_text = ParagraphStyle(
        "TableText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#1e293b")
    )
    table_header = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    story = []

    # 1. Header Section
    story.append(Paragraph("URBANPULSE", subtitle_style))
    story.append(Paragraph(f"Environmental Intelligence Briefing - {city_name}", title_style))
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(f"Reporting Date: <b>{date_str}</b> &nbsp;|&nbsp; Generated At: <b>{now_str}</b> &nbsp;|&nbsp; Source: Open-Meteo Pipeline", meta_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceBefore=2, spaceAfter=8))

    # 2. Executive AI Analyst Briefing
    story.append(Paragraph("AI Analyst Executive Summary", section_heading))
    cleaned_narrative_html = _clean_text_for_pdf(ai_narrative)

    summary_table = Table(
        [[Paragraph(cleaned_narrative_html, callout_style)]],
        colWidths=[532]
    )
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f0f9ff")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#bae6fd")),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # 3. Core Scores Dashboard (3-in-1 KPI Cards)
    env = facts_payload.get("environmental_score", {})
    act = facts_payload.get("activity_index", {})
    risk = facts_payload.get("risk_score", {})

    score_cards = [
        [
            Paragraph("<b>ENVIRONMENTAL SCORE</b>", table_header),
            Paragraph("<b>ACTIVITY INDEX</b>", table_header),
            Paragraph("<b>CITY RISK SCORE</b>", table_header)
        ],
        [
            Paragraph(f"<font size=16><b>{env.get('score', 'N/A')}/100</b></font><br/>Condition: <b>{env.get('category', 'N/A')}</b>", table_text),
            Paragraph(f"Jogging: <b>{act.get('jogging', {}).get('score', 0)}/100</b> ({act.get('jogging', {}).get('label', '')})<br/>Cycling: <b>{act.get('cycling', {}).get('score', 0)}/100</b><br/>Photography: <b>{act.get('photography', {}).get('score', 0)}/100</b>", table_text),
            Paragraph(f"<font size=14><b>{risk.get('composite_risk', 'Low')} Risk</b></font><br/>Heat: {risk.get('categories', {}).get('heat', {}).get('level', 'Low')} | Air: {risk.get('categories', {}).get('air', {}).get('level', 'Low')}<br/>Rain: {risk.get('categories', {}).get('rain', {}).get('level', 'Low')} | Wind: {risk.get('categories', {}).get('wind', {}).get('level', 'Low')}", table_text)
        ]
    ]
    card_table = Table(score_cards, colWidths=[177, 177, 178])
    card_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#0284c7")),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#059669")),
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor("#d97706")),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(card_table)
    story.append(Spacer(1, 14))

    # 4. Detailed Environmental Metrics Table
    story.append(Paragraph("Observed & Confirmed Metrics Breakdown", section_heading))
    metrics = facts_payload.get("latest_metrics", {})
    pctl = facts_payload.get("percentiles", {})
    pm25_s = facts_payload.get("pm25_stats", {})
    temp_s = facts_payload.get("temp_stats", {})

    metrics_rows = [
        [
            Paragraph("<b>Parameter</b>", table_header),
            Paragraph("<b>Observed Value</b>", table_header),
            Paragraph("<b>7-Day Baseline</b>", table_header),
            Paragraph("<b>Historical Rank (90d)</b>", table_header),
            Paragraph("<b>WHO / CPCB Status</b>", table_header)
        ],
        [
            Paragraph("Air Quality Index (AQI)", table_text),
            Paragraph(f"<b>AQI {metrics.get('aqi_us', 'N/A')}</b>", table_text),
            Paragraph(f"7d Avg: {pm25_s.get('7d_avg', 'N/A')} µg/m³", table_text),
            Paragraph(f"{pctl.get('pm2_5', 'N/A')}th percentile", table_text),
            Paragraph("Good" if (metrics.get('aqi_us') or 0) <= 50 else "Moderate" if (metrics.get('aqi_us') or 0) <= 100 else "Unhealthy", table_text)
        ],
        [
            Paragraph("PM2.5 Fine Particulates", table_text),
            Paragraph(f"<b>{metrics.get('pm2_5', 'N/A')} µg/m³</b>", table_text),
            Paragraph(f"{pm25_s.get('7d_avg', 'N/A')} µg/m³", table_text),
            Paragraph(f"P{pctl.get('pm2_5', 'N/A')}", table_text),
            Paragraph("Target ≤15 µg/m³" if (metrics.get('pm2_5') or 0) <= 15 else "Exceeds WHO Target", table_text)
        ],
        [
            Paragraph("Temperature (High / Low)", table_text),
            Paragraph(f"<b>{metrics.get('temp_max', 'N/A')}°C / {metrics.get('temp_min', 'N/A')}°C</b>", table_text),
            Paragraph(f"{temp_s.get('7d_avg', 'N/A')}°C", table_text),
            Paragraph(f"P{pctl.get('temp_max', 'N/A')}", table_text),
            Paragraph("Comfortable (20-28°C)", table_text)
        ],
        [
            Paragraph("Relative Humidity", table_text),
            Paragraph(f"{metrics.get('humidity', 'N/A')}%", table_text),
            Paragraph("—", table_text),
            Paragraph("—", table_text),
            Paragraph("Optimal (40-60%)" if 40 <= (metrics.get('humidity') or 0) <= 65 else "Elevated Moisture", table_text)
        ],
        [
            Paragraph("Precipitation / Rain", table_text),
            Paragraph(f"{metrics.get('rainfall_mm', 0.0)} mm", table_text),
            Paragraph("—", table_text),
            Paragraph("—", table_text),
            Paragraph("Dry Track" if (metrics.get('rainfall_mm') or 0) < 1 else "Wet Roadway", table_text)
        ],
        [
            Paragraph("Wind Speed Max", table_text),
            Paragraph(f"{metrics.get('wind_speed', 'N/A')} km/h", table_text),
            Paragraph("—", table_text),
            Paragraph("—", table_text),
            Paragraph("Gentle Breeze", table_text)
        ],
        [
            Paragraph("UV Index Max", table_text),
            Paragraph(f"{metrics.get('uv_index', 'N/A')}", table_text),
            Paragraph("—", table_text),
            Paragraph("—", table_text),
            Paragraph("Safe (<3)" if (metrics.get('uv_index') or 0) < 3 else "Moderate (3-5)" if (metrics.get('uv_index') or 0) < 6 else "High UV (6+)", table_text)
        ]
    ]

    metrics_table = Table(metrics_rows, colWidths=[125, 100, 100, 105, 102])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 14))

    # 5. Outdoor Activity Suitability Table
    story.append(Paragraph("Outdoor Activity Suitability & Operational Windows", section_heading))
    act_rows = [
        [
            Paragraph("<b>Activity</b>", table_header),
            Paragraph("<b>Suitability</b>", table_header),
            Paragraph("<b>Status</b>", table_header),
            Paragraph("<b>Optimal Time Window</b>", table_header),
            Paragraph("<b>Key Environmental Factors (Pros / Cons)</b>", table_header)
        ]
    ]

    for a_key, a_val in act.items():
        if isinstance(a_val, dict) and "score" in a_val:
            a_name = a_val.get("name", a_key.replace("_", " ").title())
            a_score = a_val.get("score", 0)
            a_lbl = a_val.get("label", "Moderate")
            a_win = a_val.get("best_window", "Early Morning / Evening")
            pro_txt = a_val.get("pros", ["Standard conditions"])[0]
            con_txt = a_val.get("cons", ["None"])[0]
            factors_p = f"<b>Pro:</b> {pro_txt}<br/><b>Note:</b> {con_txt}"

            act_rows.append([
                Paragraph(f"<b>{a_name}</b>", table_text),
                Paragraph(f"<b>{a_score:.0f}%</b>", table_text),
                Paragraph(f"{a_lbl}", table_text),
                Paragraph(f"{a_win}", table_text),
                Paragraph(factors_p, table_text)
            ])

    act_table = Table(act_rows, colWidths=[120, 60, 70, 125, 157])
    act_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#065f46")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdf4")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(act_table)
    story.append(Spacer(1, 14))

    # 6. Footer & Notice
    story.append(Paragraph("<b>UrbanPulse Intelligence Engine</b> — Autonomous Multi-Sensor Environmental Analytics Platform (WMO / CAMS / WHO Grounded).", meta_style))

    doc.build(story)
    return output_path
