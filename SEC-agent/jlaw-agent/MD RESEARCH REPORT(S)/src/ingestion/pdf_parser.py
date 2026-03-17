"""
JLAW PDF Filing Parser
Extracts text, sections, exhibits, forensic keywords, monetary amounts,
and dates from SEC PDF filings (10-K, 10-Q, DEF14A, 8-K).

Auto-detects filing type from content. Produces structured JSON for
cross-reference analysis.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
    print("WARNING: pdfplumber not installed. Run: pip install pdfplumber")


# Filing type detection patterns
FILING_SIGNATURES = {
    "10-K": [r"FORM\s+10-K", r"ANNUAL\s+REPORT", r"Item\s+1A\.\s+Risk\s+Factors"],
    "10-Q": [r"FORM\s+10-Q", r"QUARTERLY\s+REPORT", r"Item\s+1\.\s+Financial\s+Statements"],
    "DEF14A": [r"DEF\s*14A", r"PROXY\s+STATEMENT", r"NOTICE\s+OF\s+ANNUAL\s+MEETING",
               r"Say-on-Pay", r"Executive\s+Compensation"],
    "8-K": [r"FORM\s+8-K", r"CURRENT\s+REPORT", r"Item\s+[1-9]\.\d+"],
}

# Forensic keyword categories
FORENSIC_KEYWORDS = {
    "insider_trading": [
        "10b5-1", "pre-clearance", "blackout", "trading window",
        "insider trading policy", "Rule 10b5-1", "trading plan",
        "Exhibit 19", "pre-clear",
    ],
    "section_16": [
        "Section 16", "16(a)", "delinquent", "late filing",
        "Form 4", "Form 3", "Form 5", "beneficial ownership",
    ],
    "swoosh_governance": [
        "Swoosh", "Class A", "Class B", "dual-class", "super-voting",
        "Philip Knight", "Travis Knight", "Schedule 13D",
        "controlling shareholder", "voting power",
    ],
    "litigation": [
        "securities litigation", "class action", "complaint",
        "motion to dismiss", "plaintiff", "defendant",
        "fraud", "misrepresentation", "scienter",
    ],
    "compensation": [
        "say-on-pay", "PSU", "RSU", "stock option", "clawback",
        "severance", "separation agreement", "golden parachute",
        "change of control", "performance-based",
    ],
    "regulatory": [
        "SEC", "Division of Enforcement", "PCAOB", "EEOC",
        "comment letter", "correspondence", "staff review",
        "risk factor", "material weakness",
    ],
}

# Monetary pattern: matches $1,234.56M or $1.2 billion etc
MONEY_PATTERN = re.compile(
    r'\$[\d,]+(?:\.\d+)?\s*(?:million|billion|M|B|thousand|K)?',
    re.IGNORECASE
)

# Date patterns
DATE_PATTERNS = [
    re.compile(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'),
    re.compile(r'\b\d{1,2}/\d{1,2}/\d{4}\b'),
    re.compile(r'\b\d{4}-\d{2}-\d{2}\b'),
]

# Accession number pattern
ACCESSION_PATTERN = re.compile(r'\b\d{10}-\d{2}-\d{6}\b')


def detect_filing_type(text: str) -> str:
    """Auto-detect SEC filing type from PDF text content."""
    text_upper = text[:5000].upper()
    scores = {}
    for ftype, patterns in FILING_SIGNATURES.items():
        score = sum(1 for p in patterns if re.search(p, text_upper))
        if score > 0:
            scores[ftype] = score
    if scores:
        return max(scores, key=scores.get)
    return "UNKNOWN"


def extract_sections(text: str, filing_type: str) -> Dict[str, str]:
    """Extract major sections based on filing type."""
    sections = {}

    if filing_type == "10-K":
        section_headers = [
            (r"Item\s+1A\.\s*Risk\s+Factors", "risk_factors"),
            (r"Item\s+1B\.\s*Unresolved\s+Staff\s+Comments", "staff_comments"),
            (r"Item\s+3\.\s*Legal\s+Proceedings", "legal_proceedings"),
            (r"Item\s+5\.\s*Market", "market_info"),
            (r"Item\s+7\.\s*Management", "md_and_a"),
            (r"Item\s+9B\.\s*Other\s+Information", "other_info"),
            (r"Item\s+10\.\s*Directors", "directors_officers"),
            (r"Item\s+15\.\s*Exhibits", "exhibit_index"),
        ]
    elif filing_type == "DEF14A":
        section_headers = [
            (r"Executive\s+Compensation", "executive_compensation"),
            (r"Security\s+Ownership", "security_ownership"),
            (r"Section\s+16\(a\)", "section_16a"),
            (r"Delinquent\s+Section\s+16", "section_16a"),
            (r"Say-on-Pay", "say_on_pay"),
            (r"Proposal\s+\d", "proposals"),
            (r"Director\s+Compensation", "director_compensation"),
            (r"Related\s+Person\s+Transactions", "related_party"),
            (r"Insider\s+Trading", "insider_trading_policy"),
        ]
    elif filing_type == "10-Q":
        section_headers = [
            (r"Item\s+1\.\s*Financial\s+Statements", "financial_statements"),
            (r"Item\s+2\.\s*Management", "md_and_a"),
            (r"Item\s+1\.\s*Legal\s+Proceedings", "legal_proceedings"),
            (r"Item\s+1A\.\s*Risk\s+Factors", "risk_factors"),
            (r"Item\s+5\.\s*Other\s+Information", "other_info"),
        ]
    else:
        section_headers = [
            (r"Item\s+\d+\.\d+", "items"),
        ]

    for pattern, name in section_headers:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = match.start()
            # Extract ~2000 chars after the header
            section_text = text[start:start + 2000].strip()
            sections[name] = section_text

    return sections


def extract_exhibits(text: str) -> List[Dict]:
    """Extract exhibit references from the filing."""
    exhibits = []
    # Pattern: Exhibit XX.X or EX-XX.X
    exhibit_pattern = re.compile(
        r'(?:Exhibit|EX[- ]?)(\d+(?:\.\d+)?)\s*[-–—]\s*(.+?)(?:\n|$)',
        re.IGNORECASE
    )
    for match in exhibit_pattern.finditer(text):
        exhibits.append({
            "number": match.group(1),
            "description": match.group(2).strip()[:200],
        })
    return exhibits


def extract_monetary_amounts(text: str) -> List[Dict]:
    """Extract all monetary amounts with surrounding context."""
    amounts = []
    for match in MONEY_PATTERN.finditer(text):
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        context = text[start:end].strip()
        amounts.append({
            "amount": match.group(),
            "context": context,
            "position": match.start(),
        })
    return amounts


def extract_dates(text: str) -> List[str]:
    """Extract all date references."""
    dates = set()
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            dates.add(match.group())
    return sorted(dates)


def extract_accession_numbers(text: str) -> List[str]:
    """Extract SEC accession numbers."""
    return sorted(set(ACCESSION_PATTERN.findall(text)))


def scan_forensic_keywords(text: str) -> Dict[str, List[Dict]]:
    """Scan for forensic keywords with context."""
    results = {}
    text_lower = text.lower()
    for category, keywords in FORENSIC_KEYWORDS.items():
        hits = []
        for kw in keywords:
            kw_lower = kw.lower()
            idx = 0
            while True:
                pos = text_lower.find(kw_lower, idx)
                if pos == -1:
                    break
                start = max(0, pos - 80)
                end = min(len(text), pos + len(kw) + 80)
                context = text[start:end].strip().replace("\n", " ")
                hits.append({
                    "keyword": kw,
                    "position": pos,
                    "context": context,
                })
                idx = pos + len(kw)
        if hits:
            results[category] = hits
    return results


def parse_pdf(pdf_path: Path) -> Dict:
    """
    Parse a single SEC PDF filing into structured JSON.

    Returns a dict with: filing_type, full_text, sections, exhibits,
    monetary_amounts, dates, accession_numbers, forensic_keywords, metadata.
    """
    if pdfplumber is None:
        return {"error": "pdfplumber not installed", "source": str(pdf_path)}

    pages = []
    full_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            pages.append({
                "page_number": i + 1,
                "char_count": len(page_text),
            })
            full_text += page_text + "\n"

    # Auto-detect filing type
    filing_type = detect_filing_type(full_text)

    # Extract structured data
    sections = extract_sections(full_text, filing_type)
    exhibits = extract_exhibits(full_text)
    monetary = extract_monetary_amounts(full_text)
    dates = extract_dates(full_text)
    accessions = extract_accession_numbers(full_text)
    keywords = scan_forensic_keywords(full_text)

    # Build keyword density summary
    keyword_density = {
        cat: len(hits) for cat, hits in keywords.items()
    }

    result = {
        "source_file": str(pdf_path),
        "filing_type": filing_type,
        "total_pages": total_pages,
        "total_characters": len(full_text),
        "sections": sections,
        "exhibits": exhibits,
        "monetary_amounts_count": len(monetary),
        "monetary_amounts_sample": monetary[:20],
        "dates_referenced": dates[:50],
        "accession_numbers": accessions,
        "forensic_keyword_density": keyword_density,
        "forensic_keyword_hits": keywords,
        "pages": pages,
        "parsed_at": datetime.now().isoformat(),
    }

    return result


def parse_pdf_directory(directory: Path, output_dir: Path) -> List[Dict]:
    """Parse all PDFs in a directory tree."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for pdf_file in sorted(directory.rglob("*.pdf")):
        try:
            parsed = parse_pdf(pdf_file)
            out_name = pdf_file.stem + "_parsed.json"
            out_path = output_dir / out_name
            with open(out_path, "w") as f:
                json.dump(parsed, f, indent=2)
            results.append({
                "file": str(pdf_file),
                "type": parsed.get("filing_type"),
                "pages": parsed.get("total_pages"),
                "keywords": parsed.get("forensic_keyword_density", {}),
                "status": "OK",
            })
        except Exception as e:
            results.append({
                "file": str(pdf_file),
                "status": "ERROR",
                "error": str(e),
            })

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.ingestion.pdf_parser <pdf_or_directory> [output_dir]")
        sys.exit(1)

    path = Path(sys.argv[1])
    if path.is_file():
        result = parse_pdf(path)
        print(json.dumps(result, indent=2, default=str))
    elif path.is_dir():
        out = Path(sys.argv[2]) if len(sys.argv) > 2 else path / "parsed"
        results = parse_pdf_directory(path, out)
        for r in results:
            status = r["status"]
            print(f"  [{status}] {r['file']} — {r.get('type', 'N/A')} ({r.get('pages', '?')} pages)")
