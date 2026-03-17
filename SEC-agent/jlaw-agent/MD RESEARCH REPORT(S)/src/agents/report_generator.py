"""
JLAW Report Generator Agent
Generates formal investigation reports from the anomaly database and
parsed filing data. Produces 4 report types:
1. Master cross-analysis (FY2019-FY2025)
2. SEC enforcement bundle
3. DOJ criminal referral
4. Legislative briefing

Usage:
    python -m src.agents.report_generator --type master
    python -m src.agents.report_generator --type sec
    python -m src.agents.report_generator --type doj
    python -m src.agents.report_generator --type legislative
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List


DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", "./data"))


def load_anomaly_database() -> Dict:
    """Load the anomaly database."""
    db_file = DATA_DIR / "anomalies" / "anomaly_database.json"
    if db_file.exists():
        with open(db_file) as f:
            return json.load(f)
    return {"anomalies": [], "patterns": []}


def load_cross_reference_results() -> Dict:
    """Load cross-reference analysis results."""
    cr_file = DATA_DIR / "anomalies" / "cross_reference_results.json"
    if cr_file.exists():
        with open(cr_file) as f:
            return json.load(f)
    return {}


def load_deliverable_summaries() -> List[Dict]:
    """Load parsed deliverable summaries."""
    parsed_dir = DATA_DIR / "parsed" / "deliverables"
    summaries = []
    if parsed_dir.exists():
        for f in sorted(parsed_dir.glob("*_parsed.json")):
            with open(f) as fh:
                summaries.append(json.load(fh))
    return summaries


def generate_report(report_type: str) -> Dict:
    """Generate a report of the specified type."""
    print(f"\n{'='*60}")
    print(f"  JLAW REPORT GENERATOR — {report_type.upper()}")
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Load data
    print("  Loading anomaly database...")
    db = load_anomaly_database()
    print(f"    → {len(db['anomalies'])} anomalies, {len(db['patterns'])} patterns")

    print("  Loading cross-reference results...")
    cr = load_cross_reference_results()

    print("  Loading deliverable summaries...")
    deliverables = load_deliverable_summaries()
    print(f"    → {len(deliverables)} deliverables loaded")

    # Generate based on type
    reports_dir = DATA_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")

    if report_type == "master":
        output = _generate_master(db, cr, deliverables)
        filename = f"JLAW_Master_Cross_Analysis_FY2019-FY2025_{timestamp}.json"
    elif report_type == "sec":
        output = _generate_sec_bundle(db, cr, deliverables)
        filename = f"JLAW_SEC_Enforcement_Bundle_{timestamp}.json"
    elif report_type == "doj":
        output = _generate_doj_referral(db, cr, deliverables)
        filename = f"JLAW_DOJ_Criminal_Referral_{timestamp}.json"
    elif report_type == "legislative":
        output = _generate_legislative_brief(db, cr, deliverables)
        filename = f"JLAW_Legislative_Briefing_{timestamp}.json"
    else:
        print(f"  Unknown report type: {report_type}")
        return {"error": f"Unknown type: {report_type}"}

    # Save report data (JSON for now — DOCX generation via Agent SDK)
    output_path = reports_dir / filename
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Report data saved: {output_path}")
    print(f"  Sections: {len(output.get('sections', []))}")
    print(f"  Evidence items: {output.get('evidence_count', 0)}")
    print(f"\n  NOTE: Run the orchestrator with --report {report_type} to generate")
    print(f"  the final DOCX using the Claude Agent SDK for formatting.\n")

    return output


def _generate_master(db: Dict, cr: Dict, deliverables: List) -> Dict:
    """Generate the master cross-analysis report structure."""
    return {
        "report_type": "master_cross_analysis",
        "title": "JLAW Master Cross-Analysis Report: Nike Inc. FY2019-FY2025",
        "subtitle": "Seven-Year Full-Corpus EDGAR Forensic Investigation",
        "generated_at": datetime.now().isoformat(),
        "target": {"company": "Nike, Inc.", "cik": "0000320187", "ticker": "NKE"},
        "scope": "FY2019 through Q1 CY2026 (December 2018 - March 2026)",
        "sections": [
            {
                "id": "executive_summary",
                "title": "Executive Summary",
                "content_directive": "Synthesize the 7-year investigation arc from Parker's Dec 2019 blackout trade through the Mar 2026 real-time audit. Key metrics: $565M+ cumulative Parker sales, 9.7-year stale 13D, 14-year SEC correspondence gap, 5 compounding patterns, 23 micro-forensic anomalies, securities fraud MTD pending.",
            },
            {
                "id": "methodology",
                "title": "Methodology: 12-Category Full-Corpus EDGAR Audit",
                "content_directive": "Document the 12 filing categories audited per fiscal year and the 8 systematic cross-referencing checks applied consistently across all 7 years.",
            },
            {
                "id": "year_by_year",
                "title": "Year-by-Year Findings Catalog",
                "subsections": [f"FY{yr}" for yr in range(2019, 2026)] + ["Q1-CY2026"],
                "content_directive": "For each fiscal year, catalog ALL anomalies identified — not just structural findings but individual late filings, exhibit changes, vote count discrepancies, and proxy section toggles.",
            },
            {
                "id": "compounding_patterns",
                "title": "Compounding Patterns (Cross-Year)",
                "patterns": db.get("patterns", []),
                "content_directive": "Present the 5 identified compounding patterns with evidence from each year they appear.",
            },
            {
                "id": "evidence_index",
                "title": "Complete Evidence Index",
                "content_directive": "Catalog every accession number, filing date, and transaction referenced across all 36 deliverables.",
            },
            {
                "id": "regulatory_recommendations",
                "title": "Regulatory Recommendation Matrix",
                "content_directive": "Prioritized enforcement actions for SEC, DOJ, and legislative targets.",
            },
        ],
        "anomaly_count": len(db.get("anomalies", [])),
        "pattern_count": len(db.get("patterns", [])),
        "deliverable_count": len(deliverables),
        "evidence_count": sum(
            len(d.get("cross_references", {}).get("accession_numbers", []))
            for d in deliverables
        ),
    }


def _generate_sec_bundle(db: Dict, cr: Dict, deliverables: List) -> Dict:
    """Generate SEC enforcement bundle structure."""
    return {
        "report_type": "sec_enforcement_bundle",
        "title": "SEC Division of Enforcement Evidence Bundle",
        "subtitle": "Nike Inc. (CIK 0000320187) — Seven-Year Investigation Summary",
        "generated_at": datetime.now().isoformat(),
        "sections": [
            {"id": "cover_letter", "title": "Form TCR Cover Letter"},
            {"id": "violations_summary", "title": "Violations Summary by Category",
             "categories": ["13D Amendment Failure", "Section 16(a) Timeliness",
                          "Insider Trading Pre-Clearance", "Risk Factor Omissions"]},
            {"id": "evidence_index", "title": "Evidence Index with Accession Numbers"},
            {"id": "exhibit_19_analysis", "title": "Exhibit 19 Self-Approval Analysis"},
            {"id": "swoosh_13d", "title": "Swoosh 13D Delinquency Documentation"},
            {"id": "form4_timeliness", "title": "Section 16 Timeliness Audit Results"},
            {"id": "recommended_actions", "title": "Recommended Enforcement Actions"},
        ],
        "evidence_count": len(db.get("anomalies", [])),
        "patterns": db.get("patterns", []),
    }


def _generate_doj_referral(db: Dict, cr: Dict, deliverables: List) -> Dict:
    """Generate DOJ criminal referral structure."""
    return {
        "report_type": "doj_criminal_referral",
        "title": "DOJ Fraud Section Criminal Referral",
        "subtitle": "Nike Inc. — Insider Trading and Securities Fraud Pattern",
        "generated_at": datetime.now().isoformat(),
        "sections": [
            {"id": "referral_letter", "title": "Criminal Referral Cover Letter"},
            {"id": "securities_fraud", "title": "Securities Fraud Pattern Summary"},
            {"id": "insider_trading", "title": "Insider Trading Analysis ($565M+ Parker)"},
            {"id": "pre_clearance", "title": "Pre-Clearance Self-Approval Documentation"},
            {"id": "mnpi_timeline", "title": "Timeline Correlation with MNPI Events"},
            {"id": "witness_identification", "title": "Potential Witness Identification"},
        ],
        "evidence_count": len(db.get("anomalies", [])),
    }


def _generate_legislative_brief(db: Dict, cr: Dict, deliverables: List) -> Dict:
    """Generate legislative briefing structure."""
    return {
        "report_type": "legislative_briefing",
        "title": "Congressional Briefing: Dual-Class Governance Case Study",
        "subtitle": "Nike Inc. — Structural Governance Failures Under Dual-Class Architecture",
        "generated_at": datetime.now().isoformat(),
        "sections": [
            {"id": "one_pager", "title": "One-Page Executive Summary"},
            {"id": "dual_class_case", "title": "Dual-Class Governance Case Study"},
            {"id": "exhibit_19_comparison", "title": "Exhibit 19 Peer Comparison (Nike vs Dow 30)"},
            {"id": "regulatory_gaps", "title": "Regulatory Gap Analysis (14-Year SEC Silence)"},
            {"id": "legislative_reforms", "title": "Recommended Legislative Reforms"},
        ],
        "evidence_count": len(db.get("anomalies", [])),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JLAW Report Generator")
    parser.add_argument("--type", type=str, required=True,
                       choices=["master", "sec", "doj", "legislative"],
                       help="Report type to generate")
    args = parser.parse_args()
    generate_report(args.type)
