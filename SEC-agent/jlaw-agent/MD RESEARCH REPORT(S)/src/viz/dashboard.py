"""
JLAW Visualization — Interactive HTML Dashboard Generator
Produces a single self-contained HTML file with all 6 investigation charts.
Opens in local browser. All data embedded — no server required.

Output: data/viz/dashboard/jlaw_dashboard.html
"""

import json
import os
import base64
import webbrowser
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", "./data"))
DASH_DIR = DATA_DIR / "viz" / "dashboard"
DASH_DIR.mkdir(parents=True, exist_ok=True)
CHART_DIR = DATA_DIR / "viz" / "charts"


def embed_image(path: Path) -> str:
    """Convert image to base64 data URI."""
    if path.exists():
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{b64}"
    return ""


def generate_dashboard(open_browser: bool = True) -> Path:
    """Generate the interactive HTML dashboard."""

    # Embed chart images
    charts = {
        "parker": embed_image(CHART_DIR / "01_parker_cumulative_sales.png"),
        "swoosh": embed_image(CHART_DIR / "02_swoosh_13d_staleness.png"),
        "toggle": embed_image(CHART_DIR / "03_section16a_toggle.png"),
        "divergence": embed_image(CHART_DIR / "04_buy_sell_divergence.png"),
        "scatter": embed_image(CHART_DIR / "05_anomaly_scatter.png"),
        "litigation": embed_image(CHART_DIR / "06_litigation_timeline.png"),
    }

    # Load anomaly database if available
    anomaly_db = {"anomalies": [], "patterns": []}
    db_path = DATA_DIR / "anomalies" / "anomaly_database.json"
    if db_path.exists():
        with open(db_path) as f:
            anomaly_db = json.load(f)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JLAW v5.0 — Nike Forensic Intelligence Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Source+Sans+3:wght@300;400;600;700;900&display=swap');

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  :root {{
    --navy: #0F1B2D;
    --red: #B91C1C;
    --amber: #D97706;
    --green: #059669;
    --emerald: #047857;
    --blue: #1E40AF;
    --purple: #7C3AED;
    --grey: #6B7280;
    --light: #F8F9FA;
    --border: #E5E7EB;
    --card-bg: #FFFFFF;
    --text: #1A1A1A;
    --text-muted: #6B7280;
  }}

  body {{
    font-family: 'Source Sans 3', -apple-system, sans-serif;
    background: var(--light);
    color: var(--text);
    line-height: 1.5;
  }}

  /* ─── Header ─── */
  .header {{
    background: var(--navy);
    color: white;
    padding: 2rem 3rem;
    border-bottom: 4px solid var(--red);
  }}
  .header h1 {{
    font-size: 1.8rem;
    font-weight: 900;
    letter-spacing: -0.5px;
    margin-bottom: 0.3rem;
  }}
  .header .subtitle {{
    font-size: 0.85rem;
    color: #94A3B8;
    font-family: 'JetBrains Mono', monospace;
  }}
  .header .badge {{
    display: inline-block;
    background: var(--red);
    color: white;
    padding: 2px 10px;
    border-radius: 3px;
    font-size: 0.7rem;
    font-weight: 700;
    margin-left: 12px;
    vertical-align: middle;
  }}

  /* ─── Stats Bar ─── */
  .stats-bar {{
    display: flex;
    gap: 0;
    background: white;
    border-bottom: 1px solid var(--border);
    overflow-x: auto;
  }}
  .stat {{
    flex: 1;
    padding: 1.2rem 1.5rem;
    text-align: center;
    border-right: 1px solid var(--border);
    min-width: 140px;
  }}
  .stat:last-child {{ border-right: none; }}
  .stat .value {{
    font-size: 1.6rem;
    font-weight: 900;
    font-family: 'JetBrains Mono', monospace;
  }}
  .stat .label {{
    font-size: 0.7rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 2px;
  }}
  .stat.red .value {{ color: var(--red); }}
  .stat.purple .value {{ color: var(--purple); }}
  .stat.amber .value {{ color: var(--amber); }}
  .stat.navy .value {{ color: var(--navy); }}
  .stat.green .value {{ color: var(--green); }}

  /* ─── Navigation ─── */
  .nav {{
    display: flex;
    gap: 0;
    background: white;
    border-bottom: 2px solid var(--border);
    padding: 0 2rem;
    overflow-x: auto;
  }}
  .nav button {{
    background: none;
    border: none;
    padding: 0.9rem 1.3rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-muted);
    cursor: pointer;
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
    white-space: nowrap;
    font-family: 'Source Sans 3', sans-serif;
  }}
  .nav button:hover {{ color: var(--navy); }}
  .nav button.active {{
    color: var(--navy);
    border-bottom-color: var(--red);
  }}

  /* ─── Content ─── */
  .content {{
    max-width: 1200px;
    margin: 2rem auto;
    padding: 0 2rem;
  }}
  .panel {{
    display: none;
    animation: fadeIn 0.3s ease;
  }}
  .panel.active {{ display: block; }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}

  .card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}
  .card h2 {{
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--navy);
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--border);
  }}
  .card img {{
    width: 100%;
    max-width: 100%;
    border-radius: 4px;
  }}

  /* ─── Anomaly Explorer ─── */
  .anomaly-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
  }}
  .anomaly-table th {{
    background: var(--navy);
    color: white;
    padding: 0.6rem 0.8rem;
    text-align: left;
    font-weight: 600;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  .anomaly-table td {{
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }}
  .anomaly-table tr:hover {{ background: #F9FAFB; }}
  .severity-badge {{
    display: inline-block;
    padding: 1px 8px;
    border-radius: 3px;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
  }}
  .severity-STRUCTURAL {{ background: #FDE8E8; color: var(--red); }}
  .severity-HIGH {{ background: #FEF3C7; color: var(--amber); }}
  .severity-MEDIUM {{ background: #DBEAFE; color: var(--blue); }}
  .severity-LOW {{ background: #F3F4F6; color: var(--grey); }}

  /* ─── Thread Tracker ─── */
  .thread {{
    display: flex;
    align-items: center;
    padding: 0.8rem 1rem;
    border-bottom: 1px solid var(--border);
    gap: 1rem;
  }}
  .thread:last-child {{ border-bottom: none; }}
  .thread-status {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }}
  .thread-status.worsened {{ background: var(--red); }}
  .thread-status.pending {{ background: var(--amber); }}
  .thread-status.static {{ background: var(--grey); }}
  .thread-status.progressed {{ background: var(--green); }}
  .thread-status.new {{ background: var(--purple); }}
  .thread-title {{
    font-weight: 600;
    font-size: 0.85rem;
    flex: 1;
  }}
  .thread-assessment {{
    font-size: 0.75rem;
    color: var(--text-muted);
    font-family: 'JetBrains Mono', monospace;
  }}

  /* ─── Footer ─── */
  .footer {{
    text-align: center;
    padding: 2rem;
    font-size: 0.7rem;
    color: var(--text-muted);
    border-top: 1px solid var(--border);
    margin-top: 3rem;
    font-family: 'JetBrains Mono', monospace;
  }}

  /* ─── Print ─── */
  @media print {{
    .nav, .header .badge {{ display: none; }}
    .panel {{ display: block !important; page-break-inside: avoid; }}
    .card {{ box-shadow: none; border: 1px solid #ccc; }}
  }}
</style>
</head>
<body>

<div class="header">
  <h1>JLAW v5.0 <span class="badge">PRIVILEGED & CONFIDENTIAL</span></h1>
  <div class="subtitle">Nike Inc. (CIK 0000320187) | Forensic Intelligence Dashboard | FY2019–Q1 CY2026 | Generated: {datetime.now().strftime("%B %d, %Y %H:%M")}</div>
</div>

<div class="stats-bar">
  <div class="stat red"><div class="value">$565M+</div><div class="label">Parker Cumulative Sales</div></div>
  <div class="stat purple"><div class="value">9.7yr</div><div class="label">Swoosh 13D Staleness</div></div>
  <div class="stat amber"><div class="value">23</div><div class="label">Micro-Forensic Anomalies</div></div>
  <div class="stat navy"><div class="value">14yr</div><div class="label">SEC Correspondence Gap</div></div>
  <div class="stat green"><div class="value">36</div><div class="label">Deliverables Produced</div></div>
  <div class="stat red"><div class="value">$245M</div><div class="label">Insider Sales (Complaint)</div></div>
</div>

<div class="nav">
  <button class="active" onclick="showPanel('overview')">Overview</button>
  <button onclick="showPanel('parker')">Parker Sales</button>
  <button onclick="showPanel('swoosh')">Swoosh 13D</button>
  <button onclick="showPanel('toggle')">§16(a) Toggle</button>
  <button onclick="showPanel('divergence')">Buy/Sell</button>
  <button onclick="showPanel('scatter')">Anomaly Map</button>
  <button onclick="showPanel('litigation')">Litigation</button>
  <button onclick="showPanel('threads')">Thread Tracker</button>
</div>

<div class="content">

  <!-- OVERVIEW -->
  <div id="panel-overview" class="panel active">
    <div class="card">
      <h2>Investigation Overview — Seven-Year Arc</h2>
      <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.7;">
        This dashboard presents the complete forensic intelligence from a seven-year investigation of Nike, Inc. (CIK 0000320187) spanning FY2019 through Q1 CY2026. The investigation began with a single observation — Mark Parker exercised stock options during a quarterly blackout window on December 2, 2019 — and expanded to encompass the Swoosh LLC governance structure, the triple-insider board, five years of zero 10b5-1 disclosure, the Section 16(a) delinquency toggle, the securities fraud class action, the CEO termination, and ultimately the Exhibit 19 self-approval revelation. The arc from inference to documentation is now complete.
      </p>
    </div>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
      <div class="card">
        <h2>Parker Cumulative Sales</h2>
        <img src="{charts['parker']}" alt="Parker Cumulative Sales" />
      </div>
      <div class="card">
        <h2>Swoosh 13D Staleness</h2>
        <img src="{charts['swoosh']}" alt="Swoosh 13D Staleness" />
      </div>
      <div class="card">
        <h2>Buy/Sell Divergence (FY2025)</h2>
        <img src="{charts['divergence']}" alt="Buy/Sell Divergence" />
      </div>
      <div class="card">
        <h2>Anomaly Severity Map</h2>
        <img src="{charts['scatter']}" alt="Anomaly Scatter" />
      </div>
    </div>
  </div>

  <!-- INDIVIDUAL CHART PANELS -->
  <div id="panel-parker" class="panel">
    <div class="card">
      <h2>Mark Parker — $565M+ Cumulative Stock Sales (FY2019–FY2025)</h2>
      <img src="{charts['parker']}" alt="Parker Cumulative Sales" />
      <p style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-muted);">
        All sales executed under 10b5-1 plans pre-cleared through the Chairman/CEO self-approval pathway revealed in Exhibit 19.2 (first filed July 2024). Plan adoption dates: November 7 annually (2023, 2024 confirmed). Zero insider purchases across 7 fiscal years until FY2025. Attorney-in-fact for all filings: Kelsey A. Baldwin.
      </p>
    </div>
  </div>

  <div id="panel-swoosh" class="panel">
    <div class="card">
      <h2>Swoosh LLC — 9.7-Year 13D Staleness + Share Count Erosion</h2>
      <img src="{charts['swoosh']}" alt="Swoosh 13D Staleness" />
      <p style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-muted);">
        Last 13D/A: June 30, 2016 (Amendment #2). Reported: 257M Class A shares. Actual (Q1 2026): ~221.75M — a 35.25M-share (13.7%) unreported reduction. December 2025 mega-distribution (9.5M shares) is 75+ business days overdue for 13D/A under the SEC's 2024-effective 2-business-day rule. Swoosh board composition: UNKNOWN (2 of 3 Independent Director seats vacated FY2024).
      </p>
    </div>
  </div>

  <div id="panel-toggle" class="panel">
    <div class="card">
      <h2>Section 16(a) Delinquency Disclosure — 7-Year Toggle Pattern</h2>
      <img src="{charts['toggle']}" alt="Section 16(a) Toggle" />
      <p style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-muted);">
        Pattern: OMIT → OMIT → PRESENT → ABSENT → PRESENT → PRESENT → PRESENT. The FY2022 removal is anomalous — it occurred the year before Swan's amended Form 3 was disclosed in FY2023. The toggle's correlation with delinquency type (Knight family transactions during omission years) warrants investigation.
      </p>
    </div>
  </div>

  <div id="panel-divergence" class="panel">
    <div class="card">
      <h2>FY2025 Insider Buy/Sell Divergence</h2>
      <img src="{charts['divergence']}" alt="Buy/Sell Divergence" />
      <p style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-muted);">
        First sustained insider buying in the investigation's history. Directors Cook ($2.95M), Hill ($1M), Knudstorp ($1M), Swan ($1.23M), and Rogers ($0.19M) purchased at multi-year lows. Simultaneously, Parker continued quarterly 10b5-1 sales ($57.5M). The governance principals and the controlling-shareholder's board appointee are making diametrically opposed market bets.
      </p>
    </div>
  </div>

  <div id="panel-scatter" class="panel">
    <div class="card">
      <h2>Micro-Forensic Anomaly Map — 23 Items × 7 Years</h2>
      <img src="{charts['scatter']}" alt="Anomaly Scatter" />
      <p style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-muted);">
        Each dot represents a discrete filing-level anomaly. Size corresponds to severity (STRUCTURAL=largest). Color indicates category. FY2024 cluster reflects the Exhibit 19 revelation year. The density increase from FY2023 onward reflects new mandatory disclosure requirements making previously invisible practices detectable.
      </p>
    </div>
  </div>

  <div id="panel-litigation" class="panel">
    <div class="card">
      <h2>Securities Fraud Litigation Timeline</h2>
      <img src="{charts['litigation']}" alt="Litigation Timeline" />
      <p style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-muted);">
        In Re Nike, Inc. Securities Litigation (D. Or. 3:24-cv-00974-AN). 292-page amended complaint. 5 named defendants (Donahoe, Friend, Parker, O'Neill, Campion). 19 confidential witnesses. $245M insider sales during class period. MTD fully briefed ~6 months, unruled as of March 2026. If denied → discovery produces pre-clearance approval records.
      </p>
    </div>
  </div>

  <!-- THREAD TRACKER -->
  <div id="panel-threads" class="panel">
    <div class="card">
      <h2>Investigation Thread Tracker — As of March 2026</h2>
      <div class="thread"><div class="thread-status worsened"></div><div class="thread-title">Swoosh 13D Delinquency</div><div class="thread-assessment">WORSENED — Active Rule 13d-2 violation, 75+ days overdue</div></div>
      <div class="thread"><div class="thread-status pending"></div><div class="thread-title">Securities Fraud MTD</div><div class="thread-assessment">PENDING — Fully briefed, ~6 months under advisement</div></div>
      <div class="thread"><div class="thread-status static"></div><div class="thread-title">Exhibit 19 Self-Approval</div><div class="thread-assessment">STATIC — Policy unchanged since FY2024 (2 annual cycles)</div></div>
      <div class="thread"><div class="thread-status static"></div><div class="thread-title">Parker Sales Cadence</div><div class="thread-assessment">STATIC — $565M+ cumulative, no Q1 2026 sales (paused?)</div></div>
      <div class="thread"><div class="thread-status worsened"></div><div class="thread-title">SEC Correspondence Gap</div><div class="thread-assessment">WORSENED — 14+ years, no CORRESP despite all triggers</div></div>
      <div class="thread"><div class="thread-status progressed"></div><div class="thread-title">Travis Knight §16 Failure</div><div class="thread-assessment">CONFIRMED — ~10 business days late (Jan 5, 2026 filing)</div></div>
      <div class="thread"><div class="thread-status new"></div><div class="thread-title">Named Defendant 10b5-1 Plans</div><div class="thread-assessment">NEW — Friend + Leinwand + McCartney adopted Q2 FY2026</div></div>
      <div class="thread"><div class="thread-status new"></div><div class="thread-title">EEOC Enforcement Action</div><div class="thread-assessment">NEW — Subpoena enforcement filed Feb 4, 2026</div></div>
      <div class="thread"><div class="thread-status progressed"></div><div class="thread-title">Insider Buying Signal</div><div class="thread-assessment">PROGRESSED — $6.4M in director/CEO purchases (unprecedented)</div></div>
      <div class="thread"><div class="thread-status static"></div><div class="thread-title">Credit Downgrades</div><div class="thread-assessment">STABILIZED — A+ / A2, no further action since Nov 2025</div></div>
    </div>
  </div>

</div>

<div class="footer">
  JLAW v5.0 | Justice Legal Analysis Workbench | Nike Inc. (CIK 0000320187) | PRIVILEGED & CONFIDENTIAL | Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
</div>

<script>
function showPanel(id) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav button').forEach(b => b.classList.remove('active'));
  document.getElementById('panel-' + id).classList.add('active');
  event.target.classList.add('active');
}}
</script>
</body>
</html>"""

    output_path = DASH_DIR / "jlaw_dashboard.html"
    with open(output_path, "w") as f:
        f.write(html)

    print(f"  ✓ Dashboard: {output_path}")

    if open_browser:
        webbrowser.open(f"file://{output_path.resolve()}")
        print(f"  ✓ Opened in browser")

    return output_path


if __name__ == "__main__":
    generate_dashboard(open_browser=True)
