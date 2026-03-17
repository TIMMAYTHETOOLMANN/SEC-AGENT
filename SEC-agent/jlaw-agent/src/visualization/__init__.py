"""
JLAW Visualization Module — Phase 2.5
Generates forensic intelligence charts, interactive dashboards, and presentation decks.

Six chart types:
  1. Insider Trading Timeline     (stacked bar + cumulative line)
  2. Anomaly Severity Heatmap     (year × category matrix)
  3. 13D Staleness Gauge          (radial gauge)
  4. Filing Timeliness Box Plot   (Form 4 business-day distribution)
  5. Compounding Pattern Network  (force-directed graph)
  6. Regulatory Scorecard Radar   (SEC/DOJ/ISS/Congressional axes)

Three output formats:
  - Static PNG/SVG for DOCX embedding
  - Interactive HTML dashboard with Plotly
  - PPTX presentation deck with python-pptx
"""

__version__ = "1.0.0"
