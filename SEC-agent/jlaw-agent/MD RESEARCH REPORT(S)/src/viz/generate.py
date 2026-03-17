"""
JLAW Visualization Pipeline — Phase 2.5
Generates all visual outputs between CROSS-REFERENCE and REPORT phases.

Outputs:
  data/viz/charts/    → 6 PNG charts (300 DPI) for DOCX/PPTX embedding
  data/viz/dashboard/ → Interactive HTML dashboard (local browser)
  data/viz/deck/      → 12-slide PPTX briefing deck

Usage:
  python -m src.viz.generate          # All outputs
  python -m src.viz.generate charts   # PNGs only
  python -m src.viz.generate dash     # Dashboard only
  python -m src.viz.generate deck     # PPTX only
"""

import sys
import time
from datetime import datetime
from pathlib import Path

from src.viz.charts import generate_all_charts
from src.viz.dashboard import generate_dashboard
from src.viz.deck import generate_deck


def run_visualization_pipeline(targets: list = None):
    """Execute the full visualization pipeline."""
    if targets is None:
        targets = ["charts", "dashboard", "deck"]

    print(f"\n{'='*55}")
    print(f"  JLAW VISUALIZATION PIPELINE — Phase 2.5")
    print(f"  Targets: {', '.join(targets)}")
    print(f"  Started: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*55}\n")

    start = time.time()
    results = {}

    # Step 1: Static charts (always first — dashboard and deck depend on these)
    if "charts" in targets or "dashboard" in targets or "deck" in targets:
        print("[1/3] Generating static charts (6 × 300 DPI PNG)...")
        try:
            chart_paths = generate_all_charts()
            results["charts"] = {"status": "OK", "files": chart_paths}
        except Exception as e:
            print(f"  ✗ Chart generation failed: {e}")
            results["charts"] = {"status": "FAILED", "error": str(e)}

    # Step 2: Interactive dashboard
    if "dashboard" in targets:
        print("\n[2/3] Generating interactive HTML dashboard...")
        try:
            dash_path = generate_dashboard(open_browser=False)
            results["dashboard"] = {"status": "OK", "file": str(dash_path)}
        except Exception as e:
            print(f"  ✗ Dashboard generation failed: {e}")
            results["dashboard"] = {"status": "FAILED", "error": str(e)}

    # Step 3: PPTX briefing deck
    if "deck" in targets:
        print("\n[3/3] Generating PPTX briefing deck (12 slides)...")
        try:
            deck_path = generate_deck()
            if deck_path:
                results["deck"] = {"status": "OK", "file": str(deck_path)}
            else:
                results["deck"] = {"status": "SKIPPED", "reason": "Node.js/pptxgenjs not available"}
        except Exception as e:
            print(f"  ✗ Deck generation failed: {e}")
            results["deck"] = {"status": "FAILED", "error": str(e)}

    elapsed = time.time() - start
    print(f"\n{'='*55}")
    print(f"  VISUALIZATION PIPELINE COMPLETE ({elapsed:.1f}s)")
    for target, result in results.items():
        status = result.get("status", "UNKNOWN")
        icon = "✓" if status == "OK" else "○" if status == "SKIPPED" else "✗"
        print(f"  {icon} {target}: {status}")
    print(f"{'='*55}\n")

    return results


if __name__ == "__main__":
    targets = sys.argv[1:] if len(sys.argv) > 1 else None
    run_visualization_pipeline(targets)
