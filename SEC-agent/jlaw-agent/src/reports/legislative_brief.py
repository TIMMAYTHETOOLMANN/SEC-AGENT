"""
JLAW Legislative Briefing Generator
Produces the Congressional briefing package.

Usage:
    python -m src.reports.legislative_brief
"""

from src.agents.report_generator import generate_legislative_brief

if __name__ == "__main__":
    output = generate_legislative_brief()
    print(f"Legislative brief generated: {output}")
