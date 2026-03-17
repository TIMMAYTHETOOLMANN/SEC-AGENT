#!/usr/bin/env python3
"""
JLAW Data Pipeline Initializer
Sets up directory structure and validates deliverable inventory.

Usage: python scripts/init_data_pipeline.py [--data-dir /path/to/data]
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Expected deliverables from the 7-year investigation
EXPECTED_DELIVERABLES = {
    "full_corpus": {
        "description": "Full-corpus EDGAR audit deliverables (3 per fiscal year × 6 years = 18)",
        "files": [
            # FY2020
            "Nike_FY2020_FULL-CORPUS_Comparative_Forensic_Timeline.docx",
            "Nike_FY2020_FULL-CORPUS_SEC_Enforcement_Evidence_Bundle.docx",
            "Nike_FY2020_FULL-CORPUS_ISS_Briefing_Memo_Swoosh.docx",
            # FY2021
            "Nike_FY2021_FULL-CORPUS_Comparative_Forensic_Timeline.docx",
            "Nike_FY2021_FULL-CORPUS_SEC_Enforcement_Evidence_Bundle.docx",
            "Nike_FY2021_FULL-CORPUS_ISS_Briefing_Memo_Swoosh.docx",
            # FY2022
            "Nike_FY2022_FULL-CORPUS_Comparative_Forensic_Timeline.docx",
            "Nike_FY2022_FULL-CORPUS_SEC_Enforcement_Evidence_Bundle.docx",
            "Nike_FY2022_FULL-CORPUS_ISS_Briefing_Memo_Swoosh.docx",
            # FY2023
            "Nike_FY2023_FULL-CORPUS_Comparative_Forensic_Timeline.docx",
            "Nike_FY2023_FULL-CORPUS_SEC_Enforcement_Evidence_Bundle.docx",
            "Nike_FY2023_FULL-CORPUS_ISS_Briefing_Memo_Swoosh.docx",
            # FY2024
            "Nike_FY2024_FULL-CORPUS_Comparative_Forensic_Timeline.docx",
            "Nike_FY2024_FULL-CORPUS_SEC_Enforcement_Evidence_Bundle.docx",
            "Nike_FY2024_FULL-CORPUS_ISS_Briefing_Memo_Swoosh.docx",
            # FY2025
            "Nike_FY2025_FULL-CORPUS_Comparative_Forensic_Timeline.docx",
            "Nike_FY2025_FULL-CORPUS_SEC_Enforcement_Evidence_Bundle.docx",
            "Nike_FY2025_FULL-CORPUS_ISS_Briefing_Memo_Swoosh.docx",
        ]
    },
    "supplemental": {
        "description": "Q1 CY2026 supplemental deliverables (3)",
        "files": [
            "Nike_Q1-CY2026_Supplemental_Comparative_Forensic_Timeline.docx",
            "Nike_Q1-CY2026_Supplemental_SEC_Enforcement_Evidence_Bundle.docx",
            "Nike_Q1-CY2026_Supplemental_ISS_Briefing_Memo_Swoosh.docx",
        ]
    },
    "proxy_focused": {
        "description": "Proxy-focused deliverables (FY2019-FY2021, 12 total)",
        "files": [
            # FY2019 foundation
            "Nike_Comparative_Forensic_Timeline_FY2019-2020.docx",
            "SEC_Enforcement_Evidence_Bundle_Nike_Section16a.docx",
            "ISS_Briefing_Memo_Swoosh_Cross-Directorships.docx",
            # FY2020 proxy-focused
            "Nike_FY2020_Comparative_Forensic_Timeline.docx",
            "Nike_FY2020_SEC_Enforcement_Evidence_Bundle.docx",
            "Nike_FY2020_ISS_Briefing_Memo_Swoosh_Triple-Insider.docx",
            # FY2021 proxy-focused
            "Nike_FY2021_Comparative_Forensic_Timeline_Three-Year_Cross-Reference.docx",
            "Nike_FY2021_SEC_Enforcement_Evidence_Bundle_Three-Year_Pattern.docx",
            "Nike_FY2021_ISS_Briefing_Memo_Swoosh_Three-Year_Trajectory.docx",
        ]
    }
}

DIRECTORY_STRUCTURE = [
    "raw-edgar/filings/FY2019",
    "raw-edgar/filings/FY2020",
    "raw-edgar/filings/FY2021",
    "raw-edgar/filings/FY2022",
    "raw-edgar/filings/FY2023",
    "raw-edgar/filings/FY2024",
    "raw-edgar/filings/FY2025",
    "raw-edgar/filings/Q1-CY2026",
    "raw-edgar/rss-dump",
    "raw-edgar/reference",
    "parsed/FY2019",
    "parsed/FY2020",
    "parsed/FY2021",
    "parsed/FY2022",
    "parsed/FY2023",
    "parsed/FY2024",
    "parsed/FY2025",
    "parsed/Q1-CY2026",
    "anomalies",
    "deliverables/timelines",
    "deliverables/sec-bundles",
    "deliverables/iss-memos",
    "deliverables/supplemental",
    "deliverables/proxy-focused",
    "deliverables/foundation",
    "deliverables/micro-forensic",
    "reports",
    "submissions",
]


def init_pipeline(data_dir: Path):
    """Initialize the data pipeline directory structure."""
    print(f"\n{'='*60}")
    print(f"  JLAW Data Pipeline Initializer")
    print(f"  Data directory: {data_dir}")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # Create directories
    print("[1/3] Creating directory structure...")
    created = 0
    for subdir in DIRECTORY_STRUCTURE:
        dirpath = data_dir / subdir
        if not dirpath.exists():
            dirpath.mkdir(parents=True, exist_ok=True)
            created += 1
            print(f"  + Created: {subdir}")
    print(f"  → {created} new directories created ({len(DIRECTORY_STRUCTURE)} total)\n")

    # Check for deliverables
    print("[2/3] Scanning for existing deliverables...")
    total_expected = 0
    total_found = 0
    missing = []

    for category, info in EXPECTED_DELIVERABLES.items():
        print(f"\n  {info['description']}:")
        found_in_category = 0
        for filename in info["files"]:
            total_expected += 1
            # Search in deliverables directory and root data directory
            found = False
            for search_dir in [data_dir / "deliverables", data_dir]:
                for p in search_dir.rglob(filename):
                    found = True
                    found_in_category += 1
                    total_found += 1
                    break
                if found:
                    break
            if not found:
                missing.append(filename)

        status = "✓ COMPLETE" if found_in_category == len(info["files"]) else f"⚠ {found_in_category}/{len(info['files'])}"
        print(f"    {status}")

    print(f"\n  → {total_found}/{total_expected} deliverables found")
    if missing:
        print(f"  → {len(missing)} missing (copy these from your local machine):")
        for m in missing[:10]:
            print(f"      - {m}")
        if len(missing) > 10:
            print(f"      ... and {len(missing) - 10} more")

    # Check for raw EDGAR data
    print("\n[3/3] Scanning for raw EDGAR data...")
    raw_dir = data_dir / "raw-edgar"
    rss_files = list(raw_dir.rglob("*.xml"))
    pdf_files = list(raw_dir.rglob("*.pdf"))
    xls_files = list(raw_dir.rglob("*.xls*"))

    print(f"  RSS/XML files: {len(rss_files)}")
    print(f"  PDF files:     {len(pdf_files)}")
    print(f"  XLS/XLSX files: {len(xls_files)}")

    if not any([rss_files, pdf_files, xls_files]):
        print("\n  ⚠ No raw EDGAR data found. Copy your local EDGAR downloads to:")
        print(f"    {raw_dir / 'filings'}/  (organized by fiscal year)")
        print(f"    {raw_dir / 'rss-dump'}/  (SEC RSS/XML filing index)")

    # Summary
    print(f"\n{'='*60}")
    print(f"  INITIALIZATION COMPLETE")
    print(f"  Next steps:")
    if total_found < total_expected:
        print(f"  1. Copy {total_expected - total_found} missing deliverables to {data_dir / 'deliverables'}/")
    if not any([rss_files, pdf_files, xls_files]):
        print(f"  2. Copy raw EDGAR data to {raw_dir}/")
    print(f"  3. Run: python -m src.agents.orchestrator --ingest")
    print(f"  4. Run: python -m src.agents.orchestrator --cross-ref")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Initialize JLAW data pipeline")
    parser.add_argument("--data-dir", type=str, default="./data",
                       help="Path to data directory (default: ./data)")
    args = parser.parse_args()
    init_pipeline(Path(args.data_dir))


if __name__ == "__main__":
    main()
