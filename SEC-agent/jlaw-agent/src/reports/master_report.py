"""
JLAW Master Report Generator
Produces the capstone FY2019–FY2025 cross-analysis document.

This is a convenience wrapper that imports the master report generation
logic from the report_generator agent module.

Usage:
    python -m src.reports.master_report
"""

from src.agents.report_generator import generate_master_report

if __name__ == "__main__":
    output = generate_master_report()
    print(f"Master report generated: {output}")
