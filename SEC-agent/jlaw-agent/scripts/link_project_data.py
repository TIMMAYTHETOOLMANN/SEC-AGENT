#!/usr/bin/env python3
"""
JLAW Data Linker — Connects investigative resources to the pipeline data directories.

This script maps the actual file locations in this project to the data/ directory
structure that the pipeline expects. Uses symlinks on supported platforms, falls
back to copying on Windows.

Usage: python scripts/link_project_data.py [--copy]
"""

import os
import sys
import shutil
import json
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = PROJECT_ROOT / "docs" / "MD RESEARCH REPORT(S)"
DATA_DIR = PROJECT_ROOT / "data"

# ═══════════════════════════════════════════════
# SOURCE → DESTINATION MAPPINGS
# ═══════════════════════════════════════════════

# The 24 DOCX deliverables
DELIVERABLES_SRC = DOCS_ROOT / "FORENSIC TIMELEINE-SEC ENFORCEMENT-ISS BRIEF"

# SEC filings organized by calendar year
FILINGS_SRC = DOCS_ROOT / "investigative resources" / "Coorperate filings list (2019-2025)"

# NITS DOC CORE — secondary filing set (inside 2025 FILINGS)
NITS_DOC_CORE_SRC = FILINGS_SRC / "2025 FILINGS" / "NITS DOC CORE"

# EDGAR Company Facts API JSON
CIK_JSON_SRC = DOCS_ROOT / "investigative resources" / "CIK0000320187.json"

# Research markdown reports (annual analyses)
MD_REPORTS = [DOCS_ROOT / f"{year}.md" for year in range(2019, 2027)]
MD_REPORTS.append(DOCS_ROOT / "LONG TERM ANALYSIS.md")

# Nike's fiscal year mapping: FY ends May 31
# Calendar year 2019 filings → mostly FY2020 (Jun 2019-May 2020) + FY2019 (Jun 2018-May 2019)
# For EDGAR downloads by calendar year, we map them to the pipeline's fiscal year structure
# Since the user's folders are by calendar year, we preserve that mapping in raw-edgar
CALENDAR_TO_RAW = {
    "2019 FILINGS": "CY2019",
    "2020 FILINGS": "CY2020",
    "2021 FILINGS": "CY2021",
    "2022 FILINGS": "CY2022",
    "2023 FILINGS": "CY2023",
    "2024 FILINGS": "CY2024",
    "2025 FILINGS": "CY2025",
}


def ensure_dirs():
    """Create all pipeline data directories."""
    dirs = [
        DATA_DIR / "raw-edgar" / "filings",
        DATA_DIR / "raw-edgar" / "rss-dump",
        DATA_DIR / "raw-edgar" / "reference",
        DATA_DIR / "raw-edgar" / "nits-doc-core",
        DATA_DIR / "deliverables",
        DATA_DIR / "parsed",
        DATA_DIR / "anomalies",
        DATA_DIR / "reports",
        DATA_DIR / "submissions",
        DATA_DIR / "research-markdown",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def link_or_copy(src: Path, dst: Path, use_copy: bool = False):
    """Create a symlink or copy a file/directory."""
    if dst.exists() or dst.is_symlink():
        return "exists"

    if use_copy:
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return "copied"
    else:
        try:
            if src.is_dir():
                dst.symlink_to(src, target_is_directory=True)
            else:
                dst.symlink_to(src)
            return "linked"
        except OSError:
            # Windows may require admin privileges for symlinks — fall back to copy
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            return "copied (symlink failed)"


def link_deliverables(use_copy: bool):
    """Link/copy the 24 DOCX deliverables into data/deliverables/."""
    print("\n[1/5] Linking DOCX deliverables...")
    if not DELIVERABLES_SRC.exists():
        print(f"  ✗ Source not found: {DELIVERABLES_SRC}")
        return 0

    count = 0
    for docx_file in sorted(DELIVERABLES_SRC.glob("*.docx")):
        dst = DATA_DIR / "deliverables" / docx_file.name
        status = link_or_copy(docx_file, dst, use_copy)
        if status != "exists":
            count += 1
            print(f"  + {docx_file.name} ({status})")
        else:
            print(f"  ✓ {docx_file.name} (already present)")

    print(f"  → {count} new deliverables linked")
    return count


def link_filings(use_copy: bool):
    """Link/copy SEC filing folders into data/raw-edgar/filings/."""
    print("\n[2/5] Linking SEC filing folders...")
    if not FILINGS_SRC.exists():
        print(f"  ✗ Source not found: {FILINGS_SRC}")
        return 0

    count = 0
    for year_dir in sorted(FILINGS_SRC.iterdir()):
        if not year_dir.is_dir():
            continue
        dir_name = year_dir.name
        # Map to pipeline directory name
        dst_name = CALENDAR_TO_RAW.get(dir_name, dir_name)
        dst = DATA_DIR / "raw-edgar" / "filings" / dst_name

        # Skip the NITS DOC CORE subdirectory (handled separately)
        if dir_name == "2025 FILINGS":
            # Link only the actual filing files, not the NITS subfolder
            dst.mkdir(parents=True, exist_ok=True)
            file_count = 0
            for f in year_dir.iterdir():
                if f.is_file():
                    f_dst = dst / f.name
                    status = link_or_copy(f, f_dst, use_copy)
                    if status != "exists":
                        file_count += 1
            pdf_count = len(list(dst.glob("*.pdf")))
            xls_count = len(list(dst.glob("*.xls")))
            print(f"  + {dir_name} → {dst_name}: {file_count} new files ({pdf_count} PDF, {xls_count} XLS)")
            count += 1
        else:
            status = link_or_copy(year_dir, dst, use_copy)
            # Count files for reporting
            pdf_count = len(list(year_dir.rglob("*.pdf")))
            xls_count = len(list(year_dir.rglob("*.xls")))
            print(f"  + {dir_name} → {dst_name}: {pdf_count} PDF, {xls_count} XLS ({status})")
            count += 1

    return count


def link_nits_doc_core(use_copy: bool):
    """Link/copy NITS DOC CORE secondary filing set."""
    print("\n[3/5] Linking NITS DOC CORE filings...")
    if not NITS_DOC_CORE_SRC.exists():
        print(f"  ✗ Source not found: {NITS_DOC_CORE_SRC}")
        return 0

    count = 0
    for year_dir in sorted(NITS_DOC_CORE_SRC.iterdir()):
        if not year_dir.is_dir():
            continue
        dir_name = year_dir.name
        dst_name = CALENDAR_TO_RAW.get(dir_name, dir_name)
        dst = DATA_DIR / "raw-edgar" / "nits-doc-core" / dst_name
        status = link_or_copy(year_dir, dst, use_copy)
        pdf_count = len(list(year_dir.rglob("*.pdf")))
        xls_count = len(list(year_dir.rglob("*.xls")))
        print(f"  + {dir_name} → nits-doc-core/{dst_name}: {pdf_count} PDF, {xls_count} XLS ({status})")
        count += 1

    return count


def link_cik_json(use_copy: bool):
    """Link/copy the EDGAR Company Facts API JSON."""
    print("\n[4/5] Linking EDGAR Company Facts JSON...")
    if not CIK_JSON_SRC.exists():
        print(f"  ✗ Source not found: {CIK_JSON_SRC}")
        return 0

    dst = DATA_DIR / "raw-edgar" / "reference" / "CIK0000320187.json"
    status = link_or_copy(CIK_JSON_SRC, dst, use_copy)
    size_mb = CIK_JSON_SRC.stat().st_size / (1024 * 1024)
    print(f"  + CIK0000320187.json ({size_mb:.2f} MB) → raw-edgar/reference/ ({status})")
    return 1


def link_research_markdown(use_copy: bool):
    """Link/copy the annual research markdown reports."""
    print("\n[5/5] Linking research markdown reports...")
    count = 0
    for md_file in MD_REPORTS:
        if not md_file.exists():
            continue
        dst = DATA_DIR / "research-markdown" / md_file.name
        status = link_or_copy(md_file, dst, use_copy)
        if status != "exists":
            count += 1
            print(f"  + {md_file.name} ({status})")
        else:
            print(f"  ✓ {md_file.name} (already present)")

    return count


def generate_manifest():
    """Generate a manifest of all linked data for auditing."""
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "data_dir": str(DATA_DIR),
        "sources": {},
    }

    # Count deliverables
    deliverables = list((DATA_DIR / "deliverables").glob("*.docx"))
    manifest["sources"]["deliverables"] = {
        "path": str(DATA_DIR / "deliverables"),
        "count": len(deliverables),
        "files": [f.name for f in sorted(deliverables)],
    }

    # Count raw EDGAR filings
    filings_dir = DATA_DIR / "raw-edgar" / "filings"
    for year_dir in sorted(filings_dir.iterdir()) if filings_dir.exists() else []:
        if year_dir.is_dir():
            pdfs = len(list(year_dir.rglob("*.pdf")))
            xls = len(list(year_dir.rglob("*.xls")))
            manifest["sources"][f"raw-edgar/{year_dir.name}"] = {
                "path": str(year_dir),
                "pdf_count": pdfs,
                "xls_count": xls,
                "total": pdfs + xls,
            }

    # Count NITS DOC CORE
    nits_dir = DATA_DIR / "raw-edgar" / "nits-doc-core"
    for year_dir in sorted(nits_dir.iterdir()) if nits_dir.exists() else []:
        if year_dir.is_dir():
            pdfs = len(list(year_dir.rglob("*.pdf")))
            xls = len(list(year_dir.rglob("*.xls")))
            manifest["sources"][f"nits-doc-core/{year_dir.name}"] = {
                "path": str(year_dir),
                "pdf_count": pdfs,
                "xls_count": xls,
                "total": pdfs + xls,
            }

    # CIK JSON
    cik_path = DATA_DIR / "raw-edgar" / "reference" / "CIK0000320187.json"
    manifest["sources"]["cik_company_facts"] = {
        "path": str(cik_path),
        "exists": cik_path.exists(),
        "size_mb": round(cik_path.stat().st_size / (1024 * 1024), 2) if cik_path.exists() else 0,
    }

    # Research markdown
    md_dir = DATA_DIR / "research-markdown"
    mds = list(md_dir.glob("*.md")) if md_dir.exists() else []
    manifest["sources"]["research_markdown"] = {
        "path": str(md_dir),
        "count": len(mds),
        "files": [f.name for f in sorted(mds)],
    }

    # Totals
    total_filings = sum(
        v.get("total", 0) for k, v in manifest["sources"].items()
        if k.startswith("raw-edgar/") or k.startswith("nits-doc-core/")
    )
    manifest["totals"] = {
        "deliverables": manifest["sources"]["deliverables"]["count"],
        "raw_filing_files": total_filings,
        "research_reports": manifest["sources"]["research_markdown"]["count"],
        "cik_facts_available": manifest["sources"]["cik_company_facts"]["exists"],
    }

    manifest_path = DATA_DIR / "data_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Link project investigative resources to pipeline data directories")
    parser.add_argument("--copy", action="store_true",
                        help="Copy files instead of creating symlinks (uses more disk space but avoids symlink permissions)")
    args = parser.parse_args()

    # Windows often needs --copy unless running as admin
    use_copy = args.copy or (os.name == "nt")

    print(f"\n{'='*60}")
    print(f"  JLAW Data Linker")
    print(f"  Project root: {PROJECT_ROOT}")
    print(f"  Data directory: {DATA_DIR}")
    print(f"  Mode: {'copy' if use_copy else 'symlink'}")
    print(f"  Timestamp: {datetime.now().isoformat()}")
    print(f"{'='*60}")

    ensure_dirs()

    total = 0
    total += link_deliverables(use_copy)
    total += link_filings(use_copy)
    total += link_nits_doc_core(use_copy)
    total += link_cik_json(use_copy)
    total += link_research_markdown(use_copy)

    # Generate manifest
    print("\n  Generating data manifest...")
    manifest = generate_manifest()

    print(f"\n{'='*60}")
    print(f"  DATA LINK COMPLETE")
    print(f"  Deliverables:      {manifest['totals']['deliverables']}")
    print(f"  Raw filing files:  {manifest['totals']['raw_filing_files']}")
    print(f"  Research reports:  {manifest['totals']['research_reports']}")
    print(f"  CIK facts:        {'✓' if manifest['totals']['cik_facts_available'] else '✗'}")
    print(f"  Manifest saved:    {DATA_DIR / 'data_manifest.json'}")
    print(f"{'='*60}")
    print(f"\n  Next: python run.py status")
    print(f"  Then: python run.py pipeline")
    print()


if __name__ == "__main__":
    main()
