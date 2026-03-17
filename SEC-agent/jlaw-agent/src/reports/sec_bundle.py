"""
JLAW SEC Enforcement Bundle Generator
Produces the SEC Division of Enforcement submission package.

Usage:
    python -m src.reports.sec_bundle
"""

from src.agents.report_generator import generate_sec_bundle

if __name__ == "__main__":
    output = generate_sec_bundle()
    print(f"SEC bundle generated: {output}")
