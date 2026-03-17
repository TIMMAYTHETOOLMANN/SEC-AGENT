"""
JLAW DOJ Criminal Referral Generator
Produces the DOJ Fraud Section criminal referral package.

Usage:
    python -m src.reports.doj_referral
"""

from src.agents.report_generator import generate_doj_referral

if __name__ == "__main__":
    output = generate_doj_referral()
    print(f"DOJ referral generated: {output}")
