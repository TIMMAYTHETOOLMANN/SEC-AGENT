"""
JLAW Interactive Dashboard — Single-Page HTML with All Six Charts
Generates a self-contained HTML file with Plotly.js for interactive exploration.

Features:
  - Tab navigation across all 6 chart types
  - Anomaly detail panel with click-to-inspect
  - Pattern linkage explorer
  - Export controls (PNG snapshot per chart)
  - Dark theme matching JLAW visual identity

Usage:
    from src.visualization.dashboard import DashboardBuilder
    builder = DashboardBuilder(anomaly_db, parsed_data)
    builder.build("data/visualizations/dashboard.html")
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import plotly.io as pio

from src.visualization.chart_engine import ChartEngine, JLAW_PALETTE


class DashboardBuilder:
    """Builds a self-contained interactive HTML dashboard."""

    def __init__(self, anomaly_db: Dict, parsed_data: Dict[str, List[Dict]] = None):
        self.db = anomaly_db
        self.parsed = parsed_data or {}
        self.engine = ChartEngine(anomaly_db, parsed_data)

    def build(self, output_path: Path) -> Path:
        """Generate the complete dashboard HTML file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Render all Plotly figures
        figures = self.engine.render_all_plotly()

        # Convert each figure to embedded HTML div
        chart_divs = {}
        for name, fig in figures.items():
            if fig is not None:
                chart_divs[name] = pio.to_html(
                    fig, full_html=False, include_plotlyjs=False,
                    div_id=f"chart-{name}",
                    config={"displayModeBar": True, "toImageButtonOptions": {
                        "format": "png", "width": 1600, "height": 900,
                        "filename": f"jlaw_{name}",
                    }},
                )
            else:
                chart_divs[name] = f'<div id="chart-{name}" class="chart-placeholder">Chart unavailable</div>'

        # Build anomaly detail JSON for the explorer panel
        anomaly_json = json.dumps(self.db.get("anomalies", []), indent=2, default=str)
        pattern_json = json.dumps(self.db.get("patterns", []), indent=2, default=str)

        # Summary stats
        total_anomalies = len(self.db.get("anomalies", []))
        total_patterns = len(self.db.get("patterns", []))
        structural = sum(1 for a in self.db.get("anomalies", []) if a.get("severity") == "STRUCTURAL")
        high = sum(1 for a in self.db.get("anomalies", []) if a.get("severity") == "HIGH")

        html = self._render_html(
            chart_divs=chart_divs,
            anomaly_json=anomaly_json,
            pattern_json=pattern_json,
            total_anomalies=total_anomalies,
            total_patterns=total_patterns,
            structural=structural,
            high=high,
        )

        output_path.write_text(html, encoding="utf-8")
        return output_path

    def _render_html(self, chart_divs: Dict[str, str], anomaly_json: str,
                     pattern_json: str, total_anomalies: int, total_patterns: int,
                     structural: int, high: int) -> str:
        """Render the full HTML document."""
        now = datetime.now().strftime("%B %d, %Y %H:%M")

        tab_config = [
            ("insider_timeline",   "Insider Timeline",      "📈"),
            ("severity_heatmap",   "Severity Heatmap",      "🔥"),
            ("staleness_gauge",    "13D Staleness",         "⏱️"),
            ("timeliness_boxplot", "Filing Timeliness",     "📊"),
            ("pattern_network",    "Pattern Network",       "🕸️"),
            ("regulatory_radar",   "Regulatory Scorecard",  "🎯"),
        ]

        tabs_html = ""
        panels_html = ""
        for i, (key, label, icon) in enumerate(tab_config):
            active = " active" if i == 0 else ""
            tabs_html += f'<button class="tab-btn{active}" data-target="{key}">{icon} {label}</button>\n'
            display = "block" if i == 0 else "none"
            panels_html += f'<div class="tab-panel" id="panel-{key}" style="display:{display}">{chart_divs.get(key, "")}</div>\n'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JLAW Forensic Intelligence Dashboard — Nike Inc.</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  :root {{
    --bg:         {JLAW_PALETTE["bg"]};
    --panel:      {JLAW_PALETTE["panel"]};
    --grid:       {JLAW_PALETTE["grid"]};
    --text:       {JLAW_PALETTE["text"]};
    --text-dim:   {JLAW_PALETTE["text_dim"]};
    --accent:     {JLAW_PALETTE["accent"]};
    --accent2:    {JLAW_PALETTE["accent2"]};
    --warn:       {JLAW_PALETTE["warn"]};
    --danger:     {JLAW_PALETTE["danger"]};
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }}

  .header {{
    background: var(--panel);
    border-bottom: 1px solid var(--grid);
    padding: 16px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}

  .header h1 {{
    font-size: 20px;
    font-weight: 700;
    color: var(--accent);
  }}

  .header .subtitle {{
    font-size: 12px;
    color: var(--text-dim);
    margin-top: 2px;
  }}

  .header .classification {{
    color: var(--danger);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
  }}

  .stats-bar {{
    display: flex;
    gap: 24px;
    padding: 12px 32px;
    background: var(--panel);
    border-bottom: 1px solid var(--grid);
  }}

  .stat-card {{
    background: var(--bg);
    border: 1px solid var(--grid);
    border-radius: 8px;
    padding: 12px 20px;
    text-align: center;
    min-width: 140px;
  }}

  .stat-card .value {{
    font-size: 28px;
    font-weight: 700;
    color: var(--accent);
  }}

  .stat-card .label {{
    font-size: 11px;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
  }}

  .stat-card.danger .value {{ color: var(--danger); }}
  .stat-card.warn .value {{ color: var(--warn); }}

  .main {{
    display: grid;
    grid-template-columns: 1fr 360px;
    gap: 0;
    min-height: calc(100vh - 140px);
  }}

  .chart-area {{
    padding: 20px 24px;
    overflow-y: auto;
  }}

  .tab-bar {{
    display: flex;
    gap: 4px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }}

  .tab-btn {{
    background: var(--panel);
    border: 1px solid var(--grid);
    border-radius: 6px;
    padding: 8px 16px;
    color: var(--text-dim);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.15s;
  }}

  .tab-btn:hover {{ color: var(--text); border-color: var(--accent); }}
  .tab-btn.active {{
    background: var(--accent);
    color: #ffffff;
    border-color: var(--accent);
    font-weight: 600;
  }}

  .tab-panel {{ min-height: 400px; }}
  .chart-placeholder {{
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 400px;
    color: var(--text-dim);
    font-size: 16px;
  }}

  .explorer {{
    background: var(--panel);
    border-left: 1px solid var(--grid);
    padding: 16px;
    overflow-y: auto;
    max-height: calc(100vh - 140px);
  }}

  .explorer h3 {{
    font-size: 14px;
    color: var(--accent);
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}

  .explorer-search {{
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--grid);
    border-radius: 6px;
    padding: 8px 12px;
    color: var(--text);
    font-size: 13px;
    margin-bottom: 12px;
  }}

  .anomaly-card {{
    background: var(--bg);
    border: 1px solid var(--grid);
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: border-color 0.15s;
  }}

  .anomaly-card:hover {{ border-color: var(--accent); }}

  .anomaly-card .id {{
    font-size: 11px;
    color: var(--text-dim);
    font-family: monospace;
  }}

  .anomaly-card .title {{
    font-size: 12px;
    margin-top: 4px;
    line-height: 1.4;
  }}

  .anomaly-card .meta {{
    display: flex;
    gap: 8px;
    margin-top: 6px;
  }}

  .badge {{
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 600;
    text-transform: uppercase;
  }}

  .badge.STRUCTURAL {{ background: rgba(218,54,51,0.2); color: var(--danger); }}
  .badge.HIGH {{ background: rgba(240,136,62,0.2); color: #f0883e; }}
  .badge.MEDIUM {{ background: rgba(210,153,34,0.2); color: var(--warn); }}
  .badge.LOW {{ background: rgba(56,139,253,0.2); color: var(--accent); }}

  .detail-panel {{
    background: var(--bg);
    border: 1px solid var(--grid);
    border-radius: 8px;
    padding: 16px;
    margin-top: 12px;
    display: none;
  }}

  .detail-panel.active {{ display: block; }}

  .detail-panel h4 {{
    color: var(--accent);
    font-size: 13px;
    margin-bottom: 8px;
  }}

  .detail-panel p {{
    font-size: 12px;
    color: var(--text-dim);
    line-height: 1.5;
    margin-bottom: 8px;
  }}

  .detail-panel .evidence {{
    font-family: monospace;
    font-size: 11px;
    color: var(--text);
    background: var(--panel);
    padding: 8px;
    border-radius: 4px;
    margin-top: 8px;
  }}

  .footer {{
    text-align: center;
    padding: 8px;
    font-size: 11px;
    color: var(--text-dim);
    border-top: 1px solid var(--grid);
  }}

  @media (max-width: 1024px) {{
    .main {{ grid-template-columns: 1fr; }}
    .explorer {{ max-height: none; border-left: none; border-top: 1px solid var(--grid); }}
  }}
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>⚖️ JLAW Forensic Intelligence Dashboard</h1>
    <div class="subtitle">Nike, Inc. (CIK 0000320187) — FY2019 through Q1 CY2026 | Generated {now}</div>
  </div>
  <div class="classification">PRIVILEGED & CONFIDENTIAL</div>
</div>

<div class="stats-bar">
  <div class="stat-card">
    <div class="value">{total_anomalies}</div>
    <div class="label">Total Anomalies</div>
  </div>
  <div class="stat-card danger">
    <div class="value">{structural}</div>
    <div class="label">Structural</div>
  </div>
  <div class="stat-card warn">
    <div class="value">{high}</div>
    <div class="label">High Severity</div>
  </div>
  <div class="stat-card">
    <div class="value">{total_patterns}</div>
    <div class="label">Compounding Patterns</div>
  </div>
  <div class="stat-card">
    <div class="value">7</div>
    <div class="label">Fiscal Years</div>
  </div>
</div>

<div class="main">
  <div class="chart-area">
    <div class="tab-bar">
      {tabs_html}
    </div>
    {panels_html}
  </div>

  <div class="explorer">
    <h3>🔍 Anomaly Explorer</h3>
    <input type="text" class="explorer-search" id="anomalySearch"
           placeholder="Search anomalies..." oninput="filterAnomalies()">
    <div id="anomalyList"></div>
    <div class="detail-panel" id="detailPanel">
      <h4 id="detailTitle"></h4>
      <p id="detailDescription"></p>
      <div class="evidence" id="detailEvidence"></div>
    </div>
  </div>
</div>

<div class="footer">
  JLAW Agent Platform v5.0 — Visualization Suite v1.0 | {now}
</div>

<script>
// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
    btn.classList.add('active');
    document.getElementById('panel-' + btn.dataset.target).style.display = 'block';

    // Trigger Plotly resize for proper rendering
    const panelId = 'panel-' + btn.dataset.target;
    const plotDiv = document.querySelector('#' + panelId + ' .plotly-graph-div');
    if (plotDiv) {{ Plotly.Plots.resize(plotDiv); }}
  }});
}});

// Anomaly explorer
const anomalies = {anomaly_json};
const patterns = {pattern_json};

function renderAnomalies(items) {{
  const list = document.getElementById('anomalyList');
  list.innerHTML = items.map((a, i) => `
    <div class="anomaly-card" onclick="showDetail(${{i}})">
      <div class="id">${{a.anomaly_id}}</div>
      <div class="title">${{a.title ? a.title.substring(0, 80) : 'N/A'}}</div>
      <div class="meta">
        <span class="badge ${{a.severity}}">${{a.severity}}</span>
        <span class="badge">${{a.fiscal_year}}</span>
      </div>
    </div>
  `).join('');
}}

function filterAnomalies() {{
  const q = document.getElementById('anomalySearch').value.toLowerCase();
  const filtered = anomalies.filter(a =>
    (a.title || '').toLowerCase().includes(q) ||
    (a.anomaly_id || '').toLowerCase().includes(q) ||
    (a.category || '').toLowerCase().includes(q) ||
    (a.fiscal_year || '').toLowerCase().includes(q)
  );
  renderAnomalies(filtered);
}}

function showDetail(idx) {{
  const a = anomalies[idx];
  if (!a) return;
  document.getElementById('detailTitle').textContent =
    a.anomaly_id + ': ' + (a.title || 'N/A');
  document.getElementById('detailDescription').textContent =
    a.description || 'No description available.';
  document.getElementById('detailEvidence').innerHTML =
    (a.evidence || []).map(e => '• ' + e).join('<br>') || 'No evidence records.';
  document.getElementById('detailPanel').classList.add('active');
}}

// Initial render
renderAnomalies(anomalies);
</script>
</body>
</html>"""
