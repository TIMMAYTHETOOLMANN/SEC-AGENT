"""
JLAW EDGAR Ingest Agent
Coordinates all ingestion parsers to process raw EDGAR filings into structured JSON.

Parses: PDF, XLS/XLSX, XML (Form 4, RSS index), and existing DOCX deliverables.
Outputs: Structured JSON files organized by fiscal year in data/parsed/

Usage:
    python -m src.agents.edgar_ingest                             # Process all raw data
    python -m src.agents.edgar_ingest --year FY2024               # Single fiscal year
    python -m src.agents.edgar_ingest --type form4                # Single filing type
    python -m src.agents.edgar_ingest --deliverables              # Parse DOCX deliverables only
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from src.ingestion.pdf_parser import parse_pdf, parse_pdf_directory
from src.ingestion.xls_parser import parse_xls, parse_xls_directory
from src.ingestion.form4_parser import parse_form4_xml, parse_form4_directory
from src.ingestion.rss_parser import parse_edgar_rss, build_filing_inventory
from src.ingestion.docx_parser import parse_docx, parse_docx_directory, build_deliverable_inventory
from src.ingestion.cik_parser import parse_cik_facts, save_parsed_output as save_cik_output


# ═══════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw-edgar"
PARSED_DIR = DATA_DIR / "parsed"
DELIVERABLES_DIR = DATA_DIR / "deliverables"
LOG_DIR = Path(os.environ.get("JLAW_LOG_DIR", PROJECT_ROOT / "logs"))

# Pipeline expects fiscal year directories, but data may also be in calendar year folders
FISCAL_YEARS = ["FY2019", "FY2020", "FY2021", "FY2022", "FY2023", "FY2024", "FY2025", "Q1-CY2026"]
CALENDAR_YEARS = ["CY2019", "CY2020", "CY2021", "CY2022", "CY2023", "CY2024", "CY2025"]
ALL_YEAR_DIRS = FISCAL_YEARS + CALENDAR_YEARS


def ingest_rss_index() -> Dict:
    """Parse the EDGAR RSS/XML filing index and CIK Company Facts JSON into a structured inventory."""
    rss_dir = RAW_DIR / "rss-dump"
    ref_dir = RAW_DIR / "reference"
    results = {"status": "no_index_files_found", "filings": 0}

    # Try CIK Company Facts JSON first (most comprehensive)
    cik_json = ref_dir / "CIK0000320187.json"
    if cik_json.exists():
        print(f"  Parsing EDGAR Company Facts: {cik_json.name} ({cik_json.stat().st_size / (1024*1024):.1f} MB)...")
        parsed_cik = parse_cik_facts(cik_json)
        output_dir = PARSED_DIR / "reference"
        cik_outputs = save_cik_output(parsed_cik, output_dir)
        results = {
            "status": "cik_facts_parsed",
            "filings": len(parsed_cik.get("accession_numbers", [])),
            "filing_date_range": f"{parsed_cik['filing_dates'][0]} to {parsed_cik['filing_dates'][-1]}" if parsed_cik.get("filing_dates") else "",
            "financial_series": len(parsed_cik.get("financial_series", {})),
            "cik_outputs": cik_outputs,
        }
        print(f"    → {results['filings']} accession numbers, {results['financial_series']} financial series")
        print(f"    → Date range: {results['filing_date_range']}")

    # Also try RSS/XML files if present
    xml_files = list(rss_dir.glob("*.xml")) if rss_dir.exists() else []
    if not xml_files and results["status"] == "no_index_files_found":
        print("  ⚠ No RSS/XML or CIK JSON files found")
        return results
        return results

    all_filings = []
    for xml_file in xml_files:
        print(f"  Parsing RSS index: {xml_file.name}...")
        filings = parse_edgar_rss(xml_file)
        all_filings.extend(filings)
        print(f"    → {len(filings)} filings extracted")

    if all_filings:
        inventory_path = PARSED_DIR / "filing_inventory.json"
        inventory = build_filing_inventory(all_filings, inventory_path)
        results = {
            "status": "complete",
            "filings": len(all_filings),
            "inventory_path": str(inventory_path),
            "summary": inventory.get("summary", {}),
        }
        print(f"  ✓ Filing inventory: {len(all_filings)} filings → {inventory_path}")

    return results


def ingest_form4s(fiscal_year: str = None) -> List[Dict]:
    """Parse all Form 4 XML files."""
    results = []
    search_dirs = [RAW_DIR / "filings" / fiscal_year] if fiscal_year else [
        RAW_DIR / "filings" / fy for fy in ALL_YEAR_DIRS
    ]

    for fy_dir in search_dirs:
        form4_dir = fy_dir / "Form4"
        if not form4_dir.exists():
            # Also check for form4 in the FY directory directly
            form4_dir = fy_dir
        xml_files = list(form4_dir.rglob("*.xml"))
        if not xml_files:
            continue

        fy_name = fy_dir.name
        output_dir = PARSED_DIR / fy_name / "form4"
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"  Processing Form 4s for {fy_name}: {len(xml_files)} XML files...")
        fy_results = parse_form4_directory(form4_dir, output_dir)
        results.extend(fy_results)

        late_count = sum(1 for r in fy_results if r.get("late"))
        print(f"    → {len(fy_results)} parsed, {late_count} late filings detected")

    return results


def ingest_pdfs(fiscal_year: str = None, filing_type: str = None) -> List[Dict]:
    """Parse all PDF filings (10-K, 10-Q, DEF14A, 8-K, etc.)."""
    results = []
    search_dirs = [RAW_DIR / "filings" / fiscal_year] if fiscal_year else [
        RAW_DIR / "filings" / fy for fy in ALL_YEAR_DIRS
    ]

    for fy_dir in search_dirs:
        if not fy_dir.exists():
            continue
        fy_name = fy_dir.name

        # If specific filing type, look for that subdirectory
        if filing_type:
            pdf_dir = fy_dir / filing_type
            if pdf_dir.exists():
                output_dir = PARSED_DIR / fy_name / filing_type.lower()
                output_dir.mkdir(parents=True, exist_ok=True)
                fy_results = parse_pdf_directory(pdf_dir, output_dir, filing_type=filing_type)
                results.extend(fy_results)
        else:
            # Parse all PDF files in the FY directory tree
            pdf_files = list(fy_dir.rglob("*.pdf"))
            if not pdf_files:
                continue

            output_dir = PARSED_DIR / fy_name
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"  Processing PDFs for {fy_name}: {len(pdf_files)} files...")
            fy_results = parse_pdf_directory(fy_dir, output_dir)
            results.extend(fy_results)
            print(f"    → {len(fy_results)} parsed")

    return results


def ingest_spreadsheets(fiscal_year: str = None) -> List[Dict]:
    """Parse all XLS/XLSX files."""
    results = []
    search_dirs = [RAW_DIR / "filings" / fiscal_year] if fiscal_year else [
        RAW_DIR / "filings" / fy for fy in ALL_YEAR_DIRS
    ]

    for fy_dir in search_dirs:
        if not fy_dir.exists():
            continue
        fy_name = fy_dir.name

        xls_files = list(fy_dir.rglob("*.xls")) + list(fy_dir.rglob("*.xlsx"))
        if not xls_files:
            continue

        output_dir = PARSED_DIR / fy_name
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Processing spreadsheets for {fy_name}: {len(xls_files)} files...")
        fy_results = parse_xls_directory(fy_dir, output_dir)
        results.extend(fy_results)
        print(f"    → {len(fy_results)} parsed")

    return results


def ingest_deliverables() -> List[Dict]:
    """Parse all DOCX deliverables."""
    if not DELIVERABLES_DIR.exists():
        print("  ⚠ Deliverables directory not found. Run init_data_pipeline.py first.")
        return []

    docx_files = list(DELIVERABLES_DIR.rglob("*.docx"))
    if not docx_files:
        print("  ⚠ No DOCX deliverables found in data/deliverables/")
        return []

    output_dir = PARSED_DIR / "deliverables"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Processing deliverables: {len(docx_files)} DOCX files...")

    results = parse_docx_directory(DELIVERABLES_DIR, output_dir)

    # Build inventory
    inv_path = output_dir / "deliverable_inventory.json"
    inv = build_deliverable_inventory(results, inv_path)
    print(f"    → {inv['total_deliverables']} parsed, "
          f"{inv['total_anomaly_mentions']} anomaly mentions, "
          f"{inv['total_key_findings']} key findings")

    return results


def run_full_ingestion(fiscal_year: str = None) -> Dict:
    """
    Run the complete ingestion pipeline.

    Returns:
        Summary dict with all ingestion results
    """
    start_time = datetime.now()

    print(f"\n{'='*60}")
    print(f"  JLAW EDGAR INGEST AGENT — FULL PIPELINE")
    print(f"  Data directory: {DATA_DIR}")
    print(f"  Scope: {fiscal_year or 'ALL FISCAL YEARS'}")
    print(f"  Started: {start_time.isoformat()}")
    print(f"{'='*60}\n")

    summary = {
        "started_at": start_time.isoformat(),
        "scope": fiscal_year or "ALL",
        "phases": {},
    }

    # Phase 1: RSS Index
    print("[1/5] Parsing EDGAR RSS/XML filing index...")
    rss_result = ingest_rss_index()
    summary["phases"]["rss_index"] = rss_result

    # Phase 2: Form 4 XML
    print("\n[2/5] Parsing Form 4 XML filings...")
    form4_results = ingest_form4s(fiscal_year)
    summary["phases"]["form4"] = {
        "total": len(form4_results),
        "success": len([r for r in form4_results if "error" not in r]),
        "errors": len([r for r in form4_results if "error" in r]),
        "late_filings": len([r for r in form4_results if r.get("late")]),
    }

    # Phase 3: PDF filings
    print("\n[3/5] Parsing PDF filings (10-K, 10-Q, DEF14A, 8-K)...")
    pdf_results = ingest_pdfs(fiscal_year)
    summary["phases"]["pdf"] = {
        "total": len(pdf_results),
        "success": len([r for r in pdf_results if "error" not in r]),
        "errors": len([r for r in pdf_results if "error" in r]),
    }

    # Phase 4: Spreadsheets
    print("\n[4/5] Parsing XLS/XLSX financial data...")
    xls_results = ingest_spreadsheets(fiscal_year)
    summary["phases"]["xls"] = {
        "total": len(xls_results),
        "success": len([r for r in xls_results if "error" not in r]),
        "errors": len([r for r in xls_results if "error" in r]),
    }

    # Phase 5: Deliverables
    print("\n[5/5] Parsing DOCX deliverables...")
    docx_results = ingest_deliverables()
    summary["phases"]["deliverables"] = {
        "total": len(docx_results),
        "success": len([r for r in docx_results if "error" not in r]),
        "errors": len([r for r in docx_results if "error" in r]),
    }

    # Finalize
    end_time = datetime.now()
    summary["ended_at"] = end_time.isoformat()
    summary["duration_seconds"] = (end_time - start_time).total_seconds()

    # Save summary
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = LOG_DIR / f"ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    # Print final report
    print(f"\n{'='*60}")
    print(f"  INGESTION COMPLETE")
    print(f"  Duration: {summary['duration_seconds']:.1f}s")
    print(f"  RSS index: {rss_result.get('filings', 0)} filings cataloged")
    print(f"  Form 4s:   {summary['phases']['form4']['total']} parsed "
          f"({summary['phases']['form4']['late_filings']} late)")
    print(f"  PDFs:      {summary['phases']['pdf']['total']} parsed")
    print(f"  XLS/XLSX:  {summary['phases']['xls']['total']} parsed")
    print(f"  DOCX:      {summary['phases']['deliverables']['total']} parsed")
    print(f"  Log saved: {summary_path}")
    print(f"{'='*60}\n")

    return summary


def main():
    parser = argparse.ArgumentParser(description="JLAW EDGAR Ingest Agent")
    parser.add_argument("--year", type=str, help="Process specific fiscal year (e.g., FY2024)")
    parser.add_argument("--type", type=str, choices=["form4", "pdf", "xls", "rss", "deliverables"],
                        help="Process specific file type only")
    parser.add_argument("--deliverables", action="store_true", help="Parse DOCX deliverables only")

    args = parser.parse_args()

    if args.deliverables or args.type == "deliverables":
        ingest_deliverables()
    elif args.type == "form4":
        ingest_form4s(args.year)
    elif args.type == "pdf":
        ingest_pdfs(args.year)
    elif args.type == "xls":
        ingest_spreadsheets(args.year)
    elif args.type == "rss":
        ingest_rss_index()
    else:
        run_full_ingestion(args.year)


if __name__ == "__main__":
    main()
