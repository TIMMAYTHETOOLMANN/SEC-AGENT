"""
JLAW Visualization Agent — Phase 2.5
Orchestrates chart generation, dashboard building, and deck creation.
Slots between Phase 2 (cross-reference) and Phase 3 (report generation).

This agent:
  1. Loads the anomaly database (output of Phase 2)
  2. Loads parsed filing data (output of Phase 1)
  3. Renders all 6 static charts (PNG) for DOCX embedding
  4. Builds the interactive HTML dashboard
  5. Builds the PPTX presentation deck
  6. Creates the DOCX chart appendix
  7. Outputs a visualization manifest for Phase 3 to consume

Usage:
    python -m src.agents.visualization_agent
    python -m src.agents.visualization_agent --chart insider_timeline
    python -m src.agents.visualization_agent --format dashboard
"""

import argparse
import json
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# ═══════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", PROJECT_ROOT / "data"))
ANOMALY_DIR = DATA_DIR / "anomalies"
PARSED_DIR = DATA_DIR / "parsed"
VIZ_DIR = DATA_DIR / "visualizations"
LOG_DIR = Path(os.environ.get("JLAW_LOG_DIR", PROJECT_ROOT / "logs"))

FISCAL_YEARS = ["FY2019", "FY2020", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025"]
CALENDAR_YEARS = ["CY2019", "CY2020", "CY2021", "CY2022", "CY2023", "CY2024", "CY2025"]


def load_anomaly_db() -> Dict:
    """Load the anomaly database."""
    db_path = ANOMALY_DIR / "anomaly_database.json"
    if db_path.exists():
        with open(db_path) as f:
            return json.load(f)
    return {"anomalies": [], "patterns": [], "last_updated": None}


def load_all_parsed() -> Dict[str, List[Dict]]:
    """Load all parsed JSON files organized by fiscal year."""
    data = {}
    all_dirs = FISCAL_YEARS + CALENDAR_YEARS

    for fy in all_dirs:
        fy_dir = PARSED_DIR / fy
        if not fy_dir.is_dir():
            continue
        filings = []
        for json_file in fy_dir.rglob("*.json"):
            if json_file.name == "filing_inventory.json":
                continue
            try:
                with open(json_file) as f:
                    filing = json.load(f)
                filing["_source_file"] = str(json_file)
                filings.append(filing)
            except (json.JSONDecodeError, OSError):
                continue
        data[fy] = filings

    return data


# ═══════════════════════════════════════════════
# PHASE 2.5 RUNNER
# ═══════════════════════════════════════════════

def run_visualization(
    charts: Optional[List[str]] = None,
    formats: Optional[List[str]] = None,
) -> Dict:
    """
    Execute Phase 2.5: Visualization generation.

    Args:
        charts: Specific chart types to render (None = all 6).
                Options: insider_timeline, severity_heatmap, staleness_gauge,
                         timeliness_boxplot, pattern_network, regulatory_radar
        formats: Output formats to generate (None = all).
                 Options: static, dashboard, deck, appendix

    Returns:
        Summary dict with paths to all generated outputs.
    """
    start_time = time.time()
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*60}")
    print(f"  JLAW VISUALIZATION AGENT — PHASE 2.5")
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Load data
    print("[1/5] Loading anomaly database...")
    db = load_anomaly_db()
    print(f"  → {len(db.get('anomalies', []))} anomalies, "
          f"{len(db.get('patterns', []))} patterns")

    print("\n[2/5] Loading parsed filing data...")
    parsed = load_all_parsed()
    total_filings = sum(len(v) for v in parsed.values())
    print(f"  → {total_filings} filings across {len(parsed)} year directories")

    # Import visualization modules
    from src.visualization.chart_engine import ChartEngine
    from src.visualization.dashboard import DashboardBuilder
    from src.visualization.deck_builder import DeckBuilder
    from src.visualization.docx_embedder import DocxEmbedder

    engine = ChartEngine(db, parsed)

    # Determine what to generate
    if formats is None:
        formats = ["static", "dashboard", "deck", "appendix"]

    results = {
        "static_charts": {},
        "dashboard": None,
        "deck": None,
        "appendix": None,
        "manifest_path": None,
    }

    # ── Static Charts (PNG) ──────────────────────
    if "static" in formats:
        print("\n[3/5] Rendering static charts (PNG)...")
        charts_dir = VIZ_DIR / "charts"
        charts_dir.mkdir(parents=True, exist_ok=True)

        if charts:
            # Render specific charts
            all_chart_methods = {
                "insider_timeline":   engine.insider_timeline_static,
                "severity_heatmap":   engine.severity_heatmap_static,
                "staleness_gauge":    engine.staleness_gauge_static,
                "timeliness_boxplot": engine.timeliness_boxplot_static,
                "pattern_network":    engine.pattern_network_static,
                "regulatory_radar":   engine.regulatory_radar_static,
            }
            for chart_key in charts:
                method = all_chart_methods.get(chart_key)
                if method:
                    path = charts_dir / f"{chart_key}.png"
                    try:
                        method(path)
                        results["static_charts"][chart_key] = str(path)
                        print(f"  ✓ {chart_key}.png")
                    except Exception as e:
                        print(f"  ✗ {chart_key}.png — {e}")
        else:
            chart_paths = engine.render_all_static(charts_dir)
            for key, path in chart_paths.items():
                if path:
                    results["static_charts"][key] = str(path)
    else:
        print("\n[3/5] Skipping static charts (not requested)")

    # ── Interactive Dashboard (HTML) ─────────────
    if "dashboard" in formats:
        print("\n[4/5] Building interactive dashboard...")
        dashboard_path = VIZ_DIR / "dashboard.html"
        try:
            builder = DashboardBuilder(db, parsed)
            builder.build(dashboard_path)
            results["dashboard"] = str(dashboard_path)
            print(f"  ✓ dashboard.html ({dashboard_path.stat().st_size / 1024:.0f} KB)")
        except Exception as e:
            print(f"  ✗ dashboard.html — {e}")
    else:
        print("\n[4/5] Skipping dashboard (not requested)")

    # ── PPTX Deck + DOCX Appendix ────────────────
    if "deck" in formats or "appendix" in formats:
        print("\n[5/5] Building presentation deck and chart appendix...")

        # Convert string paths back to Path objects for builders
        chart_image_paths = {k: Path(v) for k, v in results["static_charts"].items()}

        if "deck" in formats:
            deck_path = VIZ_DIR / f"JLAW_Forensic_Deck_{now_str}.pptx"
            try:
                deck = DeckBuilder(db, chart_image_paths)
                deck.build(deck_path)
                results["deck"] = str(deck_path)
                print(f"  ✓ {deck_path.name} ({deck_path.stat().st_size / 1024:.0f} KB)")
            except Exception as e:
                print(f"  ✗ PPTX deck — {e}")

        if "appendix" in formats:
            appendix_path = VIZ_DIR / f"Chart_Appendix_{now_str}.docx"
            try:
                embedder = DocxEmbedder(chart_image_paths)
                embedder.create_chart_appendix(appendix_path)
                results["appendix"] = str(appendix_path)
                print(f"  ✓ {appendix_path.name} ({appendix_path.stat().st_size / 1024:.0f} KB)")
            except Exception as e:
                print(f"  ✗ DOCX appendix — {e}")
    else:
        print("\n[5/5] Skipping deck/appendix (not requested)")

    # ── Save Manifest ────────────────────────────
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "anomalies_count": len(db.get("anomalies", [])),
        "patterns_count": len(db.get("patterns", [])),
        "filings_analyzed": total_filings,
        "outputs": results,
        "chart_keys": list(results["static_charts"].keys()),
        "elapsed_seconds": round(time.time() - start_time, 2),
    }

    manifest_path = VIZ_DIR / "visualization_manifest.json"
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    results["manifest_path"] = str(manifest_path)

    # ── Log ──────────────────────────────────────
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"visualization_{now_str}.json"
    with open(log_path, "w") as f:
        json.dump(manifest, f, indent=2)

    elapsed = time.time() - start_time

    print(f"\n{'='*60}")
    print(f"  VISUALIZATION COMPLETE — Phase 2.5")
    print(f"  Static charts: {len(results['static_charts'])}")
    print(f"  Dashboard:     {'✓' if results['dashboard'] else '✗'}")
    print(f"  PPTX deck:     {'✓' if results['deck'] else '✗'}")
    print(f"  DOCX appendix: {'✓' if results['appendix'] else '✗'}")
    print(f"  Manifest:      {manifest_path}")
    print(f"  Log:           {log_path}")
    print(f"  Elapsed:       {elapsed:.1f}s")
    print(f"{'='*60}\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="JLAW Visualization Agent — Phase 2.5")
    parser.add_argument(
        "--chart", type=str, nargs="*",
        choices=["insider_timeline", "severity_heatmap", "staleness_gauge",
                 "timeliness_boxplot", "pattern_network", "regulatory_radar"],
        help="Specific chart(s) to render (default: all)",
    )
    parser.add_argument(
        "--format", type=str, nargs="*",
        choices=["static", "dashboard", "deck", "appendix"],
        help="Output format(s) to generate (default: all)",
    )

    args = parser.parse_args()
    run_visualization(charts=args.chart, formats=args.format)


if __name__ == "__main__":
    main()
