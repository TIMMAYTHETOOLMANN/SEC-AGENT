"""JLAW Master Report — FY2019-FY2025 cross-analysis compilation."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.agents.report_generator import generate_report

if __name__ == "__main__":
    generate_report("master")
