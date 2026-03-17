"""
JLAW DOCX Deliverable Parser
Parses all 36 DOCX investigation deliverables into structured JSON.
Extracts section trees, anomaly mentions, cross-references
(accession numbers, filing types, dates), and key findings.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None
    print("WARNING: python-docx not installed. Run: pip install python-docx")


# Cross-reference extraction patterns
ACCESSION_PATTERN = re.compile(r'\b\d{10}-\d{2}-\d{6}\b')
FISCAL_YEAR_PATTERN = re.compile(r'\bFY20[12]\d\b')
DOLLAR_PATTERN = re.compile(r'\$[\d,]+(?:\.\d+)?(?:\s*(?:M|B|million|billion))?', re.IGNORECASE)
DATE_PATTERN = re.compile(
    r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
    r'|\b\d{4}-\d{2}-\d{2}\b'
)
FILING_TYPE_PATTERN = re.compile(
    r'\b(?:10-K|10-Q|8-K|DEF\s*14A|Form\s*[345]|SC\s*13[DG]|S-[38]|424B2|CORRESP)\b',
    re.IGNORECASE
)
PERSON_NAMES = [
    "Mark Parker", "Parker", "John Donahoe", "Donahoe", "Elliott Hill", "Hill",
    "Travis Knight", "Philip Knight", "Phil Knight", "Alan Graf", "Graf",
    "Robert Swan", "Swan", "Matthew Friend", "Friend", "Heidi O'Neill", "O'Neill",
    "Andrew Campion", "Campion", "Eric Sprunk", "Sprunk", "Tim Cook", "Cook",
    "Monique Matheson", "Matheson", "Johanna Nielsen", "Nielsen",
    "Robert Leinwand", "Leinwand", "Kelsey Baldwin", "Baldwin",
]

# Anomaly severity keywords
SEVERITY_KEYWORDS = {
    "STRUCTURAL": ["structural", "systemic", "architectural", "self-approval", "loophole"],
    "RED": ["anomaly", "late filing", "delinquent", "overdue", "violation", "stale"],
    "AMBER": ["irregularity", "unusual", "notable", "concern"],
    "BLACK": ["fracture", "active violation", "MNPI", "material non-public"],
}

# Deliverable type detection
DELIVERABLE_TYPES = {
    "timeline": ["Comparative", "Timeline", "Forensic Timeline"],
    "sec_bundle": ["SEC", "Enforcement", "Evidence Bundle"],
    "iss_memo": ["ISS", "Briefing", "Memo", "Swoosh"],
    "micro_forensic": ["Micro-Forensic", "Re-Audit", "Filing-Level"],
}


def detect_deliverable_type(filename: str, text_sample: str) -> str:
    """Classify the deliverable type from filename and content."""
    fn_upper = filename.upper()
    for dtype, keywords in DELIVERABLE_TYPES.items():
        if any(kw.upper() in fn_upper for kw in keywords):
            return dtype
    text_upper = text_sample[:1000].upper()
    for dtype, keywords in DELIVERABLE_TYPES.items():
        if any(kw.upper() in text_upper for kw in keywords):
            return dtype
    return "unknown"


def detect_fiscal_year(filename: str, text: str) -> str:
    """Extract the primary fiscal year from filename or content."""
    # Try filename first
    fy_match = FISCAL_YEAR_PATTERN.search(filename)
    if fy_match:
        return fy_match.group()
    # Try Q1 CY2026 pattern
    if "Q1" in filename and "2026" in filename:
        return "Q1-CY2026"
    # Try content
    fy_matches = FISCAL_YEAR_PATTERN.findall(text[:500])
    if fy_matches:
        return fy_matches[0]
    return "UNKNOWN"


def extract_section_tree(doc) -> List[Dict]:
    """Extract the document's heading/section hierarchy."""
    sections = []
    current_section = None

    for para in doc.paragraphs:
        style = para.style.name if para.style else ""
        text = para.text.strip()
        if not text:
            continue

        if "Heading" in style:
            level = 1
            try:
                level = int(style.replace("Heading", "").strip())
            except (ValueError, AttributeError):
                pass
            current_section = {
                "level": level,
                "title": text,
                "content_preview": "",
                "subsections": [],
            }
            sections.append(current_section)
        elif current_section and len(current_section.get("content_preview", "")) < 500:
            current_section["content_preview"] += text[:200] + " "

    return sections


def extract_table_data(doc) -> List[Dict]:
    """Extract data from all tables in the document."""
    tables = []
    for i, table in enumerate(doc.tables):
        rows = []
        headers = []
        for j, row in enumerate(table.rows):
            cells = [cell.text.strip() for cell in row.cells]
            if j == 0:
                headers = cells
            rows.append(cells)

        if rows:
            tables.append({
                "table_index": i,
                "headers": headers,
                "row_count": len(rows) - 1,
                "sample_rows": rows[1:6],
            })

    return tables


def extract_cross_references(text: str) -> Dict:
    """Extract all cross-references to SEC filings, dates, amounts, etc."""
    return {
        "accession_numbers": sorted(set(ACCESSION_PATTERN.findall(text))),
        "fiscal_years": sorted(set(FISCAL_YEAR_PATTERN.findall(text))),
        "filing_types": sorted(set(
            m.group().upper().replace("  ", " ")
            for m in FILING_TYPE_PATTERN.finditer(text)
        )),
        "dollar_amounts": sorted(set(DOLLAR_PATTERN.findall(text)))[:30],
        "dates": sorted(set(DATE_PATTERN.findall(text)))[:50],
        "persons_mentioned": sorted(set(
            name for name in PERSON_NAMES
            if name in text
        )),
    }


def extract_anomaly_mentions(text: str) -> List[Dict]:
    """Find and categorize anomaly mentions in the text."""
    anomalies = []

    for severity, keywords in SEVERITY_KEYWORDS.items():
        for kw in keywords:
            for match in re.finditer(re.escape(kw), text, re.IGNORECASE):
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                context = text[start:end].strip().replace("\n", " ")
                anomalies.append({
                    "severity": severity,
                    "keyword": kw,
                    "context": context,
                    "position": match.start(),
                })

    # Deduplicate by position proximity
    deduped = []
    last_pos = -200
    for a in sorted(anomalies, key=lambda x: x["position"]):
        if a["position"] - last_pos > 100:
            deduped.append(a)
            last_pos = a["position"]

    return deduped


def extract_key_findings(text: str) -> List[str]:
    """Extract key finding statements (sentences with strong assertion patterns)."""
    findings = []
    patterns = [
        r'(?:FINDING|FRACTURE|ANOMALY|PATTERN|CONVERGENCE)\s*\d*\s*[-–—:]\s*(.+?)(?:\.|$)',
        r'(?:PRIORITY|ACTION|RECOMMENDATION)\s*\d*\s*[-–—:]\s*(.+?)(?:\.|$)',
        r'(?:CONFIRMED|WORSENED|NEW|STATIC|PENDING)[-–—:]\s*(.+?)(?:\.|$)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            finding = match.group(1).strip()
            if len(finding) > 20:
                findings.append(finding[:300])

    return findings[:30]


def parse_docx(docx_path: Path) -> Dict:
    """Parse a single DOCX deliverable into structured JSON."""
    if DocxDocument is None:
        return {"error": "python-docx not installed", "source": str(docx_path)}

    doc = DocxDocument(str(docx_path))

    # Extract full text
    full_text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())

    # Metadata
    core = doc.core_properties
    filename = docx_path.name

    result = {
        "source_file": str(docx_path),
        "filename": filename,
        "deliverable_type": detect_deliverable_type(filename, full_text),
        "fiscal_year": detect_fiscal_year(filename, full_text),
        "metadata": {
            "author": core.author or "",
            "created": str(core.created) if core.created else "",
            "modified": str(core.modified) if core.modified else "",
            "title": core.title or "",
        },
        "statistics": {
            "paragraph_count": len(doc.paragraphs),
            "table_count": len(doc.tables),
            "character_count": len(full_text),
            "word_count": len(full_text.split()),
        },
        "section_tree": extract_section_tree(doc),
        "tables": extract_table_data(doc),
        "cross_references": extract_cross_references(full_text),
        "anomaly_mentions": extract_anomaly_mentions(full_text),
        "key_findings": extract_key_findings(full_text),
        "parsed_at": datetime.now().isoformat(),
    }

    return result


def parse_deliverable_directory(directory: Path, output_dir: Path) -> List[Dict]:
    """Parse all DOCX deliverables in a directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for docx_file in sorted(directory.rglob("*.docx")):
        if docx_file.name.startswith("~"):
            continue
        try:
            parsed = parse_docx(docx_file)
            out_name = docx_file.stem + "_parsed.json"
            out_path = output_dir / out_name
            with open(out_path, "w") as f:
                json.dump(parsed, f, indent=2, default=str)
            results.append({
                "file": docx_file.name,
                "type": parsed.get("deliverable_type"),
                "fiscal_year": parsed.get("fiscal_year"),
                "sections": len(parsed.get("section_tree", [])),
                "tables": parsed["statistics"]["table_count"],
                "accessions": len(parsed["cross_references"]["accession_numbers"]),
                "anomalies": len(parsed["anomaly_mentions"]),
                "findings": len(parsed["key_findings"]),
                "status": "OK",
            })
        except Exception as e:
            results.append({"file": docx_file.name, "status": "ERROR", "error": str(e)})

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.ingestion.docx_parser <file_or_directory> [output_dir]")
        sys.exit(1)

    path = Path(sys.argv[1])
    if path.is_file():
        result = parse_docx(path)
        print(json.dumps(result, indent=2, default=str))
    elif path.is_dir():
        out = Path(sys.argv[2]) if len(sys.argv) > 2 else path / "parsed"
        results = parse_deliverable_directory(path, out)
        print(f"\nParsed {len(results)} deliverables:")
        for r in results:
            if r["status"] == "OK":
                print(f"  [OK] {r['file']} — {r['type']}/{r['fiscal_year']} | "
                      f"{r['accessions']} accessions, {r['anomalies']} anomaly mentions, "
                      f"{r['findings']} findings")
            else:
                print(f"  [ERR] {r['file']} — {r.get('error', 'unknown')}")
