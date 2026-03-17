"""
JLAW PDF Parser
Extracts structured text from SEC EDGAR filing PDFs (10-K, 10-Q, DEF14A, 8-K).
Handles multi-column layouts, table extraction, and exhibit indexing.

Input: PDF file path (from data/raw-edgar/filings/{FY}/{type}/)
Output: Structured dict with extracted text, sections, tables, and metadata

Usage:
    python -m src.ingestion.pdf_parser data/raw-edgar/filings/FY2024/10-K/nike_10k.pdf
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pdfplumber


# ═══════════════════════════════════════════════
# SEC FILING SECTION PATTERNS
# ═══════════════════════════════════════════════

SECTION_PATTERNS = {
    # 10-K sections
    "business": re.compile(r"(?:ITEM|Item)\s*1[.\s]*(?:—|–|-|:)?\s*Business", re.IGNORECASE),
    "risk_factors": re.compile(r"(?:ITEM|Item)\s*1A[.\s]*(?:—|–|-|:)?\s*Risk\s*Factor", re.IGNORECASE),
    "legal_proceedings": re.compile(r"(?:ITEM|Item)\s*3[.\s]*(?:—|–|-|:)?\s*Legal\s*Proceeding", re.IGNORECASE),
    "mda": re.compile(r"(?:ITEM|Item)\s*7[.\s]*(?:—|–|-|:)?\s*Management.s\s*Discussion", re.IGNORECASE),
    "financials": re.compile(r"(?:ITEM|Item)\s*8[.\s]*(?:—|–|-|:)?\s*Financial\s*Statements", re.IGNORECASE),
    "controls": re.compile(r"(?:ITEM|Item)\s*9A[.\s]*(?:—|–|-|:)?\s*Controls?\s*and\s*Procedure", re.IGNORECASE),
    "executive_comp": re.compile(r"(?:ITEM|Item)\s*11[.\s]*(?:—|–|-|:)?\s*Executive\s*Compensation", re.IGNORECASE),
    "security_ownership": re.compile(r"(?:ITEM|Item)\s*12[.\s]*(?:—|–|-|:)?\s*Security\s*Ownership", re.IGNORECASE),
    "exhibits": re.compile(r"(?:ITEM|Item)\s*15[.\s]*(?:—|–|-|:)?\s*Exhibit", re.IGNORECASE),
    # DEF 14A / Proxy sections
    "section_16a": re.compile(r"(?:Section\s*16|Delinquent\s*Section\s*16|§\s*16)", re.IGNORECASE),
    "say_on_pay": re.compile(r"(?:Say.on.Pay|Advisory\s*Vote.*Compensation)", re.IGNORECASE),
    "director_nominees": re.compile(r"(?:Director\s*Nominees|Election\s*of\s*Directors)", re.IGNORECASE),
    "beneficial_ownership": re.compile(r"(?:Beneficial\s*Ownership|Security\s*Ownership)", re.IGNORECASE),
    "compensation_discussion": re.compile(r"Compensation\s*Discussion\s*(?:and|&)\s*Analysis", re.IGNORECASE),
    # 8-K items
    "8k_item_501": re.compile(r"Item\s*5\.01.*(?:Change|Officer)", re.IGNORECASE),
    "8k_item_502": re.compile(r"Item\s*5\.02.*(?:Departure|Appointment|Election)", re.IGNORECASE),
    "8k_item_507": re.compile(r"Item\s*5\.07.*(?:Shareholder\s*Vote|Annual\s*Meeting)", re.IGNORECASE),
    "8k_item_201": re.compile(r"Item\s*2\.01.*(?:Acquisition|Disposition)", re.IGNORECASE),
    "8k_item_202": re.compile(r"Item\s*2\.02.*(?:Results\s*of\s*Operations|Financial)", re.IGNORECASE),
}

# Key phrases to flag for forensic review
FORENSIC_KEYWORDS = [
    r"10b5-1",
    r"Rule\s*16a",
    r"Section\s*16\(a\)",
    r"pre-?clearance",
    r"blackout",
    r"insider\s*trading",
    r"beneficial\s*owner",
    r"Schedule\s*13[DG]",
    r"delinquent",
    r"late\s*fil",
    r"restatement",
    r"material\s*weakness",
    r"going\s*concern",
    r"whistleblower",
    r"SEC\s*(?:investigation|inquiry|subpoena|enforcement)",
    r"class\s*action",
    r"derivative\s*(?:action|suit|complaint)",
    r"securities\s*fraud",
    r"self-?approv",
]
FORENSIC_RE = re.compile("|".join(FORENSIC_KEYWORDS), re.IGNORECASE)

# Exhibit patterns
EXHIBIT_RE = re.compile(
    r"(?:Exhibit|EX-?)\s*(\d+(?:\.\d+)?)\s*(?:—|–|-|:|\s)\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)

# Monetary amount patterns
MONEY_RE = re.compile(r"\$[\d,]+(?:\.\d{1,2})?\s*(?:million|billion|thousand)?", re.IGNORECASE)

# Date patterns (for timeline extraction)
DATE_PATTERNS = [
    re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
]


def extract_text_from_pdf(pdf_path: Path, max_pages: int = None) -> List[Dict]:
    """
    Extract text from every page of a PDF, preserving layout structure.

    Returns a list of page dicts: {page_num, text, tables, width, height}
    """
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        limit = max_pages or len(pdf.pages)
        for i, page in enumerate(pdf.pages[:limit]):
            page_text = page.extract_text(layout=True) or ""

            # Extract tables separately for structured data
            raw_tables = page.extract_tables() or []
            tables = []
            for tbl in raw_tables:
                # Clean table cells
                cleaned = []
                for row in tbl:
                    cleaned.append([
                        (cell.strip() if cell else "") for cell in row
                    ])
                if cleaned:
                    tables.append(cleaned)

            pages.append({
                "page_num": i + 1,
                "text": page_text,
                "tables": tables,
                "width": float(page.width),
                "height": float(page.height),
                "char_count": len(page_text),
            })

    return pages


def identify_sections(pages: List[Dict]) -> Dict[str, Dict]:
    """
    Identify SEC filing sections by scanning page text for section headers.
    Returns {section_name: {start_page, end_page, header_text}}.
    """
    full_text_by_page = [(p["page_num"], p["text"]) for p in pages]
    sections = {}
    section_positions = []  # (page_num, char_offset, section_name, header_match)

    for page_num, text in full_text_by_page:
        for sec_name, pattern in SECTION_PATTERNS.items():
            match = pattern.search(text)
            if match:
                section_positions.append((page_num, match.start(), sec_name, match.group()))

    # Sort by page then position
    section_positions.sort(key=lambda x: (x[0], x[1]))

    # Build section ranges
    for i, (page, offset, name, header) in enumerate(section_positions):
        end_page = section_positions[i + 1][0] - 1 if i + 1 < len(section_positions) else pages[-1]["page_num"]
        sections[name] = {
            "start_page": page,
            "end_page": end_page,
            "header_text": header.strip(),
        }

    return sections


def extract_section_text(pages: List[Dict], section_info: Dict) -> str:
    """Extract the full text of a section given its page range."""
    start = section_info["start_page"]
    end = section_info["end_page"]
    texts = []
    for p in pages:
        if start <= p["page_num"] <= end:
            texts.append(p["text"])
    return "\n\n".join(texts)


def extract_exhibits(pages: List[Dict]) -> List[Dict]:
    """Extract exhibit index from the filing."""
    exhibits = []
    full_text = "\n".join(p["text"] for p in pages)

    for match in EXHIBIT_RE.finditer(full_text):
        exhibit_num = match.group(1)
        exhibit_title = match.group(2).strip()
        # Skip garbage matches
        if len(exhibit_title) < 3 or len(exhibit_title) > 300:
            continue
        exhibits.append({
            "number": exhibit_num,
            "title": exhibit_title,
            "status": "present",
        })

    # Deduplicate by exhibit number
    seen = set()
    unique = []
    for ex in exhibits:
        if ex["number"] not in seen:
            seen.add(ex["number"])
            unique.append(ex)

    return unique


def extract_forensic_flags(pages: List[Dict]) -> List[Dict]:
    """Scan for forensic keywords and extract surrounding context."""
    flags = []
    for page in pages:
        for match in FORENSIC_RE.finditer(page["text"]):
            # Extract 200 chars of surrounding context
            start = max(0, match.start() - 100)
            end = min(len(page["text"]), match.end() + 100)
            context = page["text"][start:end].strip()

            flags.append({
                "keyword": match.group(),
                "page": page["page_num"],
                "context": context,
                "position": match.start(),
            })

    return flags


def extract_monetary_amounts(pages: List[Dict]) -> List[Dict]:
    """Extract all monetary amounts with surrounding context."""
    amounts = []
    for page in pages:
        for match in MONEY_RE.finditer(page["text"]):
            start = max(0, match.start() - 80)
            end = min(len(page["text"]), match.end() + 80)
            context = page["text"][start:end].strip()
            amounts.append({
                "amount_raw": match.group(),
                "page": page["page_num"],
                "context": context,
            })
    return amounts


def extract_dates(pages: List[Dict]) -> List[Dict]:
    """Extract all dates for timeline construction."""
    dates = []
    seen = set()
    for page in pages:
        for pattern in DATE_PATTERNS:
            for match in pattern.finditer(page["text"]):
                date_str = match.group()
                if date_str not in seen:
                    seen.add(date_str)
                    start = max(0, match.start() - 60)
                    end = min(len(page["text"]), match.end() + 60)
                    dates.append({
                        "date_raw": date_str,
                        "page": page["page_num"],
                        "context": page["text"][start:end].strip(),
                    })
    return dates


def extract_signers(pages: List[Dict]) -> Dict[str, str]:
    """Extract CEO/CFO signers from the signature page."""
    signers = {}
    # Typically in the last 5 pages
    sig_pages = pages[-5:] if len(pages) > 5 else pages
    sig_text = "\n".join(p["text"] for p in sig_pages)

    # CEO / Principal Executive Officer
    ceo_match = re.search(
        r"(?:Chief\s*Executive\s*Officer|Principal\s*Executive\s*Officer|President\s*and\s*CEO)\s*\n\s*/?s/?\s*(.+?)(?:\n|$)",
        sig_text, re.IGNORECASE,
    )
    if ceo_match:
        signers["ceo"] = ceo_match.group(1).strip().strip("/").strip()

    # CFO / Principal Financial Officer
    cfo_match = re.search(
        r"(?:Chief\s*Financial\s*Officer|Principal\s*Financial\s*Officer|Executive\s*Vice\s*President.*Finance)\s*\n\s*/?s/?\s*(.+?)(?:\n|$)",
        sig_text, re.IGNORECASE,
    )
    if cfo_match:
        signers["cfo"] = cfo_match.group(1).strip().strip("/").strip()

    return signers


def detect_filing_type(pages: List[Dict], filename: str = "") -> str:
    """Auto-detect filing type from content and filename."""
    fn = filename.upper()
    if "10-K" in fn or "10K" in fn:
        return "10-K"
    if "10-Q" in fn or "10Q" in fn:
        return "10-Q"
    if "DEF14A" in fn or "DEF 14A" in fn or "PROXY" in fn:
        return "DEF14A"
    if "8-K" in fn or "8K" in fn:
        return "8-K"

    # Content-based detection
    first_pages_text = " ".join(p["text"][:500] for p in pages[:3]).upper()
    if "ANNUAL REPORT" in first_pages_text and "10-K" in first_pages_text:
        return "10-K"
    if "QUARTERLY REPORT" in first_pages_text:
        return "10-Q"
    if "PROXY STATEMENT" in first_pages_text or "DEF 14A" in first_pages_text:
        return "DEF14A"
    if "CURRENT REPORT" in first_pages_text and "8-K" in first_pages_text:
        return "8-K"
    if "SCHEDULE 13D" in first_pages_text:
        return "SC13D"
    if "SCHEDULE 13G" in first_pages_text:
        return "SC13G"

    return "UNKNOWN"


def parse_pdf(pdf_path: Path, filing_type: str = None, filed_date: str = None,
              accession_number: str = None) -> Dict:
    """
    Full PDF parsing pipeline: extract text, identify sections, flag forensic items.

    Args:
        pdf_path: Path to the PDF
        filing_type: Override filing type (auto-detected if None)
        filed_date: Filing date (YYYY-MM-DD)
        accession_number: EDGAR accession number

    Returns:
        Structured dict with all extracted data
    """
    pages = extract_text_from_pdf(pdf_path)

    if not pages:
        return {
            "error": "No text extracted from PDF",
            "source_file": str(pdf_path),
            "parsed_at": datetime.now().isoformat(),
        }

    # Auto-detect filing type if not provided
    if not filing_type:
        filing_type = detect_filing_type(pages, pdf_path.name)

    # Identify sections
    sections = identify_sections(pages)

    # Extract exhibits
    exhibits = extract_exhibits(pages)

    # Extract forensic flags
    forensic_flags = extract_forensic_flags(pages)

    # Extract signers
    signers = extract_signers(pages)

    # Extract monetary amounts (limited to key sections)
    amounts = extract_monetary_amounts(pages)

    # Extract dates for timeline
    dates = extract_dates(pages)

    # Build section text excerpts (first 2000 chars each)
    section_excerpts = {}
    for sec_name, sec_info in sections.items():
        text = extract_section_text(pages, sec_info)
        section_excerpts[sec_name] = {
            "start_page": sec_info["start_page"],
            "end_page": sec_info["end_page"],
            "excerpt": text[:2000],
            "full_length": len(text),
        }

    result = {
        "filing_type": filing_type,
        "filing_id": accession_number,
        "filed_date": filed_date,
        "source_file": str(pdf_path),
        "total_pages": len(pages),
        "total_chars": sum(p["char_count"] for p in pages),
        "signers": signers,
        "exhibits": exhibits,
        "sections": section_excerpts,
        "forensic_flags": forensic_flags,
        "monetary_amounts": amounts[:100],  # Cap at 100 to avoid huge output
        "timeline_dates": dates[:200],
        "flags": {
            "has_forensic_keywords": len(forensic_flags) > 0,
            "forensic_keyword_count": len(forensic_flags),
            "has_10b51_reference": any("10b5" in f["keyword"].lower() for f in forensic_flags),
            "has_section_16_reference": any("16a" in f["keyword"].lower() or "16(a)" in f["keyword"].lower()
                                            for f in forensic_flags),
            "has_insider_trading_reference": any("insider" in f["keyword"].lower() for f in forensic_flags),
            "exhibit_count": len(exhibits),
        },
        "parsed_at": datetime.now().isoformat(),
    }

    return result


def parse_pdf_directory(directory: Path, output_dir: Path,
                        filing_type: str = None) -> List[Dict]:
    """
    Parse all PDF files in a directory tree.

    Args:
        directory: Root directory to scan for PDFs
        output_dir: Where to write parsed JSON results
        filing_type: Override type for all files (auto-detect if None)

    Returns:
        List of summary dicts for each parsed file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for pdf_file in sorted(directory.rglob("*.pdf")):
        print(f"  Parsing: {pdf_file.name}...")
        try:
            parsed = parse_pdf(pdf_file, filing_type=filing_type)

            # Save parsed result
            out_name = pdf_file.stem + "_parsed.json"
            out_path = output_dir / out_name
            with open(out_path, "w") as f:
                json.dump(parsed, f, indent=2)

            results.append({
                "file": str(pdf_file),
                "filing_type": parsed["filing_type"],
                "pages": parsed["total_pages"],
                "forensic_flags": parsed["flags"]["forensic_keyword_count"],
                "exhibits": parsed["flags"]["exhibit_count"],
                "output": str(out_path),
            })
        except Exception as e:
            results.append({
                "file": str(pdf_file),
                "error": str(e),
            })

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.ingestion.pdf_parser <pdf_path_or_directory> [output_dir]")
        print("       python -m src.ingestion.pdf_parser data/raw-edgar/filings/FY2024/10-K/nike.pdf")
        print("       python -m src.ingestion.pdf_parser data/raw-edgar/filings/FY2024/ data/parsed/FY2024/")
        sys.exit(1)

    path = Path(sys.argv[1])
    if path.is_file():
        result = parse_pdf(path)
        print(json.dumps(result, indent=2))
    elif path.is_dir():
        output = Path(sys.argv[2]) if len(sys.argv) > 2 else path / "parsed"
        results = parse_pdf_directory(path, output)
        print(f"\nParsed {len(results)} files:")
        for r in results:
            if "error" in r:
                print(f"  ✗ {r['file']}: {r['error']}")
            else:
                print(f"  ✓ {r['file']}: {r['filing_type']}, {r['pages']} pages, "
                      f"{r['forensic_flags']} flags, {r['exhibits']} exhibits")
    else:
        print(f"Path not found: {path}")
        sys.exit(1)
