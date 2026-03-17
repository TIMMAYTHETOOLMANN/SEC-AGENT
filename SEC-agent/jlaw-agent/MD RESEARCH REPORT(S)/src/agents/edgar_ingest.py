"""
JLAW EDGAR Ingest Agent
Coordinates all parsers (RSS, Form 4 XML, PDF, XLS, DOCX) into a
unified ingestion pipeline with per-fiscal-year output.

Usage:
    python -m src.agents.edgar_ingest [--data-dir ./data]
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from ..ingestion.rss_parser import parse_edgar_rss, build_filing_inventory
from ..ingestion.form4_parser import parse_form4_directory
from ..ingestion.pdf_parser import parse_pdf_directory
from ..ingestion.xls_parser import parse_spreadsheet_directory
from ..ingestion.docx_parser import parse_deliverable_directory


DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", "./data"))


def run_ingestion(data_dir: Path = None) -> Dict:
    """Run the complete EDGAR ingestion pipeline."""
    data_dir = data_dir or DATA_DIR
    raw_dir = data_dir / "raw-edgar"
    parsed_dir = data_dir / "parsed"
    parsed_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "started_at": datetime.now().isoformat(),
        "data_dir": str(data_dir),
        "phases": {},
    }

    print(f"\n{'='*60}")
    print(f"  JLAW EDGAR INGESTION PIPELINE")
    print(f"  Data: {data_dir}")
    print(f"  Started: {report['started_at']}")
    print(f"{'='*60}\n")

    # Phase 1: RSS/XML Index
    print("[1/5] Parsing EDGAR RSS/XML filing index...")
    rss_dir = raw_dir / "rss-dump"
    rss_results = []
    if rss_dir.exists():
        for xml_file in sorted(rss_dir.glob("*.xml")):
            filings = parse_edgar_rss(xml_file)
            inventory = build_filing_inventory(filings, parsed_dir / "filing_inventory.json")
            rss_results.append({
                "source": str(xml_file),
                "filings_found": len(filings),
                "fiscal_years": list(inventory.get("summary", {}).keys()),
            })
            print(f"  → {xml_file.name}: {len(filings)} filings")
    else:
        print(f"  ⚠ No RSS dump found at {rss_dir}")
    report["phases"]["rss_index"] = rss_results

    # Phase 2: Form 4 XML Parsing
    print("\n[2/5] Parsing Form 4 XML filings...")
    form4_results = []
    for fy_dir in sorted((raw_dir / "filings").iterdir()) if (raw_dir / "filings").exists() else []:
        form4_dir = fy_dir / "Form4"
        if form4_dir.exists():
            out_dir = parsed_dir / fy_dir.name / "Form4"
            out_dir.mkdir(parents=True, exist_ok=True)
            results = parse_form4_directory(form4_dir, out_dir)
            late_count = sum(1 for r in results if r.get("late"))
            form4_results.append({
                "fiscal_year": fy_dir.name,
                "total": len(results),
                "late_filings": late_count,
                "errors": sum(1 for r in results if "error" in r),
            })
            print(f"  → {fy_dir.name}: {len(results)} Form 4s ({late_count} late)")
    report["phases"]["form4_xml"] = form4_results

    # Phase 3: PDF Parsing
    print("\n[3/5] Parsing PDF filings...")
    pdf_results = []
    for fy_dir in sorted((raw_dir / "filings").iterdir()) if (raw_dir / "filings").exists() else []:
        pdf_count = len(list(fy_dir.rglob("*.pdf")))
        if pdf_count > 0:
            out_dir = parsed_dir / fy_dir.name / "pdf"
            out_dir.mkdir(parents=True, exist_ok=True)
            results = parse_pdf_directory(fy_dir, out_dir)
            pdf_results.append({
                "fiscal_year": fy_dir.name,
                "total": len(results),
                "by_type": {},
                "errors": sum(1 for r in results if r.get("status") == "ERROR"),
            })
            for r in results:
                if r.get("status") == "OK":
                    ft = r.get("type", "UNKNOWN")
                    pdf_results[-1]["by_type"][ft] = pdf_results[-1]["by_type"].get(ft, 0) + 1
            print(f"  → {fy_dir.name}: {len(results)} PDFs — {pdf_results[-1]['by_type']}")
    report["phases"]["pdf_filings"] = pdf_results

    # Phase 4: XLS/XLSX Parsing
    print("\n[4/5] Parsing XLS/XLSX spreadsheets...")
    xls_results = []
    for fy_dir in sorted((raw_dir / "filings").iterdir()) if (raw_dir / "filings").exists() else []:
        xls_count = len(list(fy_dir.rglob("*.xls*")))
        if xls_count > 0:
            out_dir = parsed_dir / fy_dir.name / "xls"
            out_dir.mkdir(parents=True, exist_ok=True)
            results = parse_spreadsheet_directory(fy_dir, out_dir)
            xls_results.append({
                "fiscal_year": fy_dir.name,
                "total": len(results),
                "errors": sum(1 for r in results if r.get("status") == "ERROR"),
            })
            print(f"  → {fy_dir.name}: {len(results)} spreadsheets")
    report["phases"]["xls_spreadsheets"] = xls_results

    # Phase 5: DOCX Deliverable Parsing
    print("\n[5/5] Parsing DOCX deliverables...")
    deliverables_dir = data_dir / "deliverables"
    docx_results = []
    if deliverables_dir.exists():
        out_dir = parsed_dir / "deliverables"
        out_dir.mkdir(parents=True, exist_ok=True)
        results = parse_deliverable_directory(deliverables_dir, out_dir)
        for r in results:
            docx_results.append(r)
        total_ok = sum(1 for r in results if r.get("status") == "OK")
        total_err = sum(1 for r in results if r.get("status") == "ERROR")
        print(f"  → {total_ok} deliverables parsed, {total_err} errors")
        total_accessions = sum(r.get("accessions", 0) for r in results if r.get("status") == "OK")
        total_anomalies = sum(r.get("anomalies", 0) for r in results if r.get("status") == "OK")
        total_findings = sum(r.get("findings", 0) for r in results if r.get("status") == "OK")
        print(f"  → {total_accessions} accession refs, {total_anomalies} anomaly mentions, {total_findings} findings")
    else:
        print(f"  ⚠ No deliverables directory at {deliverables_dir}")
    report["phases"]["docx_deliverables"] = docx_results

    # Save report
    report["completed_at"] = datetime.now().isoformat()
    report_file = parsed_dir / "ingestion_report.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Summary
    print(f"\n{'='*60}")
    print(f"  INGESTION COMPLETE")
    print(f"  RSS filings indexed: {sum(r.get('filings_found', 0) for r in rss_results)}")
    print(f"  Form 4s parsed: {sum(r.get('total', 0) for r in form4_results)}")
    print(f"  PDFs parsed: {sum(r.get('total', 0) for r in pdf_results)}")
    print(f"  Spreadsheets parsed: {sum(r.get('total', 0) for r in xls_results)}")
    print(f"  Deliverables parsed: {sum(1 for r in docx_results if r.get('status') == 'OK')}")
    print(f"  Report: {report_file}")
    print(f"{'='*60}\n")

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JLAW EDGAR Ingestion Pipeline")
    parser.add_argument("--data-dir", type=str, default=None)
    args = parser.parse_args()
    run_ingestion(Path(args.data_dir) if args.data_dir else None)
