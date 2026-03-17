"""
JLAW DOCX Deliverable Parser
Parses the 36 investigation deliverables (DOCX format) into structured JSON
for cross-referencing, anomaly extraction, and master report compilation.

Handles:
- Comparative Forensic Timelines (7 per fiscal year)
- SEC Enforcement Evidence Bundles (7 per fiscal year)
- ISS Briefing Memos (7 per fiscal year)
- Q1 CY2026 Supplemental set (3 documents)
- Micro-forensic re-audit report (1 document)

Each deliverable is parsed into:
1. Document metadata (title, date, category, fiscal year)
2. Section structure (headings → text blocks)
3. Anomaly mentions (with accession numbers, dates, dollar amounts)
4. Cross-reference citations (references to other deliverables/filings)
5. Key finding summaries

Input: DOCX file path (from data/deliverables/)
Output: Structured dict with full document content

Usage:
    python -m src.ingestion.docx_parser data/deliverables/timelines/
    python -m src.ingestion.docx_parser data/deliverables/Nike_FY2024_FULL-CORPUS_Comparative_Forensic_Timeline.docx
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH


# ═══════════════════════════════════════════════
# DELIVERABLE CLASSIFICATION
# ═══════════════════════════════════════════════

DELIVERABLE_PATTERNS = {
    "comparative_forensic_timeline": re.compile(
        r"(?:Comparative|Forensic)\s*(?:_)?Timeline", re.IGNORECASE
    ),
    "sec_enforcement_bundle": re.compile(
        r"SEC\s*(?:_)?Enforcement\s*(?:_)?Evidence\s*(?:_)?Bundle", re.IGNORECASE
    ),
    "iss_briefing_memo": re.compile(
        r"ISS\s*(?:_)?Briefing\s*(?:_)?Memo", re.IGNORECASE
    ),
    "supplemental": re.compile(
        r"Supplemental", re.IGNORECASE
    ),
    "micro_forensic": re.compile(
        r"(?:Micro|Re).?(?:Forensic|Audit)", re.IGNORECASE
    ),
}

FISCAL_YEAR_RE = re.compile(r"FY\s*(\d{4})", re.IGNORECASE)
CY_PERIOD_RE = re.compile(r"(?:CY|Q\d)\s*[-_]?\s*(?:CY)?\s*(\d{4})", re.IGNORECASE)

# Extraction patterns for forensic content
ACCESSION_RE = re.compile(r"\d{10}-\d{2}-\d{6}")
FILING_TYPE_RE = re.compile(
    r"\b(?:10-K|10-Q|8-K|DEF\s*14A|Form\s*[345]|SC\s*13[DG]|S-[38]|424B2)\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(r"\$[\d,]+(?:\.\d{1,2})?\s*(?:million|billion|thousand|M|B|K)?", re.IGNORECASE)
DATE_RE = re.compile(
    r"\b(?:(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b"
)
ANOMALY_KEYWORDS = re.compile(
    r"(?:anomal|discrepanc|irregularit|delinquen|late\s*fil|overdue|"
    r"non-?complian|violation|breach|self-?approv|loophole|stale|"
    r"omission|misstatement|material\s*weakness|restatement)",
    re.IGNORECASE,
)
SECTION_16_RE = re.compile(r"(?:Section\s*16|Rule\s*16a|§\s*16)", re.IGNORECASE)
RULE_10B51_RE = re.compile(r"10b5-1|Rule\s*10b-?5", re.IGNORECASE)
SWOOSH_RE = re.compile(r"Swoosh", re.IGNORECASE)


def classify_deliverable(filename: str, first_heading: str = "") -> Dict:
    """Classify a deliverable by its filename and first heading."""
    text = filename + " " + first_heading

    # Determine category
    category = "unknown"
    for cat_name, pattern in DELIVERABLE_PATTERNS.items():
        if pattern.search(text):
            category = cat_name
            break

    # Determine fiscal year
    fiscal_year = "UNKNOWN"
    fy_match = FISCAL_YEAR_RE.search(text)
    if fy_match:
        fiscal_year = f"FY{fy_match.group(1)}"
    else:
        cy_match = CY_PERIOD_RE.search(text)
        if cy_match:
            fiscal_year = f"Q1-CY{cy_match.group(1)}"

    # Determine corpus type
    corpus_type = "unknown"
    if "FULL-CORPUS" in text.upper() or "FULL_CORPUS" in text.upper():
        corpus_type = "full_corpus"
    elif "PROXY" in text.upper():
        corpus_type = "proxy_focused"
    elif "SUPPLEMENTAL" in text.upper():
        corpus_type = "supplemental"
    elif "FY2019" in text.upper() and "FY2020" in text.upper():
        corpus_type = "foundation"

    return {
        "category": category,
        "fiscal_year": fiscal_year,
        "corpus_type": corpus_type,
    }


def extract_paragraphs(doc: Document) -> List[Dict]:
    """
    Extract all paragraphs with style information.
    Returns list of {text, style, is_heading, heading_level, alignment}.
    """
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = para.style.name if para.style else ""
        is_heading = style_name.startswith("Heading")
        heading_level = 0
        if is_heading:
            try:
                heading_level = int(style_name.replace("Heading", "").strip())
            except ValueError:
                heading_level = 1

        # Check for bold-formatted pseudo-headings
        if not is_heading and para.runs:
            all_bold = all(run.bold for run in para.runs if run.text.strip())
            if all_bold and len(text) < 200:
                is_heading = True
                heading_level = 3  # Treat as sub-heading

        alignment = "left"
        if para.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            alignment = "center"
        elif para.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
            alignment = "right"

        paragraphs.append({
            "text": text,
            "style": style_name,
            "is_heading": is_heading,
            "heading_level": heading_level,
            "alignment": alignment,
        })

    return paragraphs


def extract_tables(doc: Document) -> List[Dict]:
    """Extract all tables from the document."""
    tables = []
    for i, table in enumerate(doc.tables):
        rows_data = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows_data.append(cells)

        if rows_data:
            # Use first row as headers if it looks like a header row
            headers = rows_data[0] if rows_data else []
            tables.append({
                "table_index": i,
                "headers": headers,
                "rows": rows_data[1:] if len(rows_data) > 1 else [],
                "total_rows": len(rows_data),
                "total_cols": len(headers),
            })

    return tables


def build_section_tree(paragraphs: List[Dict]) -> List[Dict]:
    """
    Build a hierarchical section tree from paragraph data.
    Returns list of sections: {heading, level, content, subsections, anomalies}.
    """
    sections = []
    current_section = None
    current_content = []

    for para in paragraphs:
        if para["is_heading"]:
            # Save previous section
            if current_section is not None:
                current_section["content"] = "\n".join(current_content)
                sections.append(current_section)
            current_section = {
                "heading": para["text"],
                "level": para["heading_level"],
                "content": "",
            }
            current_content = []
        else:
            current_content.append(para["text"])

    # Save last section
    if current_section is not None:
        current_section["content"] = "\n".join(current_content)
        sections.append(current_section)
    elif current_content:
        sections.append({
            "heading": "(Document Body)",
            "level": 0,
            "content": "\n".join(current_content),
        })

    return sections


def extract_anomaly_mentions(text: str) -> List[Dict]:
    """Extract mentions of anomalies, discrepancies, and compliance issues."""
    mentions = []
    for match in ANOMALY_KEYWORDS.finditer(text):
        start = max(0, match.start() - 150)
        end = min(len(text), match.end() + 150)
        context = text[start:end].strip()

        # Extract associated accession numbers
        accessions = ACCESSION_RE.findall(context)
        # Extract associated amounts
        amounts = MONEY_RE.findall(context)
        # Extract associated dates
        dates = DATE_RE.findall(context)

        mentions.append({
            "keyword": match.group(),
            "context": context,
            "accession_numbers": accessions,
            "monetary_amounts": amounts,
            "dates": dates,
            "involves_section_16": bool(SECTION_16_RE.search(context)),
            "involves_10b51": bool(RULE_10B51_RE.search(context)),
            "involves_swoosh": bool(SWOOSH_RE.search(context)),
        })

    return mentions


def extract_cross_references(text: str) -> Dict:
    """Extract cross-references to other filings, deliverables, and entities."""
    return {
        "accession_numbers": list(set(ACCESSION_RE.findall(text))),
        "filing_types_mentioned": list(set(
            m.group().upper() for m in FILING_TYPE_RE.finditer(text)
        )),
        "fiscal_years_mentioned": list(set(
            f"FY{m.group(1)}" for m in FISCAL_YEAR_RE.finditer(text)
        )),
        "monetary_amounts": list(set(MONEY_RE.findall(text)))[:50],  # Cap at 50
        "dates_mentioned": list(set(DATE_RE.findall(text)))[:100],
        "section_16_references": len(SECTION_16_RE.findall(text)),
        "rule_10b51_references": len(RULE_10B51_RE.findall(text)),
        "swoosh_references": len(SWOOSH_RE.findall(text)),
    }


def extract_key_findings(sections: List[Dict]) -> List[Dict]:
    """Extract key findings from section headings and content."""
    findings = []

    # Look for sections that typically contain findings
    finding_patterns = re.compile(
        r"(?:finding|conclusion|recommendation|summary|key\s*observation|"
        r"discrepanc|anomal|violation|evidence|pattern)",
        re.IGNORECASE,
    )

    for section in sections:
        if finding_patterns.search(section["heading"]):
            # Extract numbered or bulleted items from the content
            content = section["content"]
            # Look for numbered items (1. xxx, 2. xxx, etc.)
            items = re.findall(r"(?:^|\n)\s*(?:\d+[.)]\s*|[•●◦▪-]\s*)(.+?)(?=\n\s*(?:\d+[.)]\s*|[•●◦▪-]\s*)|\Z)",
                               content, re.DOTALL)
            if items:
                for item in items:
                    findings.append({
                        "section": section["heading"],
                        "finding": item.strip()[:500],
                    })
            else:
                # Take first 500 chars of the section content as a finding summary
                findings.append({
                    "section": section["heading"],
                    "finding": content[:500].strip(),
                })

    return findings


def parse_docx(docx_path: Path) -> Dict:
    """
    Full DOCX deliverable parsing pipeline.

    Args:
        docx_path: Path to the DOCX file

    Returns:
        Structured dict with all extracted data
    """
    try:
        doc = Document(docx_path)
    except Exception as e:
        return {
            "error": f"Cannot read DOCX file: {str(e)}",
            "source_file": str(docx_path),
            "parsed_at": datetime.now().isoformat(),
        }

    # Extract raw paragraphs
    paragraphs = extract_paragraphs(doc)

    # Classify the deliverable
    first_heading = next(
        (p["text"] for p in paragraphs if p["is_heading"]),
        paragraphs[0]["text"] if paragraphs else "",
    )
    classification = classify_deliverable(docx_path.name, first_heading)

    # Build section tree
    sections = build_section_tree(paragraphs)

    # Extract tables
    tables = extract_tables(doc)

    # Full text for cross-referencing
    full_text = "\n".join(p["text"] for p in paragraphs)

    # Extract anomaly mentions
    anomaly_mentions = extract_anomaly_mentions(full_text)

    # Extract cross-references
    cross_refs = extract_cross_references(full_text)

    # Extract key findings
    key_findings = extract_key_findings(sections)

    # Count document properties
    core_props = doc.core_properties
    doc_metadata = {
        "title": core_props.title or "",
        "author": core_props.author or "",
        "created": core_props.created.isoformat() if core_props.created else "",
        "modified": core_props.modified.isoformat() if core_props.modified else "",
        "revision": core_props.revision,
    }

    result = {
        "deliverable_type": classification["category"],
        "fiscal_year": classification["fiscal_year"],
        "corpus_type": classification["corpus_type"],
        "source_file": str(docx_path),
        "filename": docx_path.name,
        "document_metadata": doc_metadata,
        "total_paragraphs": len(paragraphs),
        "total_sections": len(sections),
        "total_tables": len(tables),
        "total_chars": len(full_text),
        "sections": [{
            "heading": s["heading"],
            "level": s["level"],
            "content_length": len(s["content"]),
            "content_excerpt": s["content"][:1000],
        } for s in sections],
        "tables": tables,
        "anomaly_mentions": anomaly_mentions,
        "cross_references": cross_refs,
        "key_findings": key_findings,
        "flags": {
            "anomaly_mention_count": len(anomaly_mentions),
            "accession_numbers_cited": len(cross_refs["accession_numbers"]),
            "filing_types_cited": len(cross_refs["filing_types_mentioned"]),
            "has_section_16_content": cross_refs["section_16_references"] > 0,
            "has_10b51_content": cross_refs["rule_10b51_references"] > 0,
            "has_swoosh_content": cross_refs["swoosh_references"] > 0,
            "table_count": len(tables),
            "key_finding_count": len(key_findings),
        },
        "parsed_at": datetime.now().isoformat(),
    }

    return result


def parse_docx_directory(directory: Path, output_dir: Path) -> List[Dict]:
    """Parse all DOCX files in a directory tree."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for docx_file in sorted(directory.rglob("*.docx")):
        # Skip temp files
        if docx_file.name.startswith("~$"):
            continue
        print(f"  Parsing: {docx_file.name}...")
        try:
            parsed = parse_docx(docx_file)

            out_name = docx_file.stem + "_parsed.json"
            out_path = output_dir / out_name
            with open(out_path, "w") as f:
                json.dump(parsed, f, indent=2, default=str)

            results.append({
                "file": str(docx_file),
                "type": parsed["deliverable_type"],
                "fiscal_year": parsed["fiscal_year"],
                "corpus": parsed["corpus_type"],
                "anomalies": parsed["flags"]["anomaly_mention_count"],
                "findings": parsed["flags"]["key_finding_count"],
                "output": str(out_path),
            })
        except Exception as e:
            results.append({
                "file": str(docx_file),
                "error": str(e),
            })

    return results


def build_deliverable_inventory(results: List[Dict], output_path: Path) -> Dict:
    """Build a master inventory of all parsed deliverables."""
    inventory = {
        "generated_at": datetime.now().isoformat(),
        "total_deliverables": len([r for r in results if "error" not in r]),
        "errors": len([r for r in results if "error" in r]),
        "by_category": {},
        "by_fiscal_year": {},
        "by_corpus_type": {},
        "total_anomaly_mentions": sum(r.get("anomalies", 0) for r in results),
        "total_key_findings": sum(r.get("findings", 0) for r in results),
    }

    for r in results:
        if "error" in r:
            continue
        cat = r.get("type", "unknown")
        fy = r.get("fiscal_year", "UNKNOWN")
        corpus = r.get("corpus", "unknown")

        inventory["by_category"].setdefault(cat, []).append(r)
        inventory["by_fiscal_year"].setdefault(fy, []).append(r)
        inventory["by_corpus_type"].setdefault(corpus, []).append(r)

    with open(output_path, "w") as f:
        json.dump(inventory, f, indent=2, default=str)

    return inventory


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.ingestion.docx_parser <docx_path_or_directory> [output_dir]")
        print("       python -m src.ingestion.docx_parser data/deliverables/")
        sys.exit(1)

    path = Path(sys.argv[1])
    if path.is_file():
        result = parse_docx(path)
        print(json.dumps(result, indent=2, default=str))
    elif path.is_dir():
        output = Path(sys.argv[2]) if len(sys.argv) > 2 else path / "parsed"
        results = parse_docx_directory(path, output)
        print(f"\nParsed {len(results)} deliverables:")
        for r in results:
            if "error" in r:
                print(f"  ✗ {r['file']}: {r['error']}")
            else:
                print(f"  ✓ {r['file']}: {r['type']}, {r['fiscal_year']}, "
                      f"{r['anomalies']} anomalies, {r['findings']} findings")

        # Build inventory
        inv_path = output / "deliverable_inventory.json"
        inv = build_deliverable_inventory(results, inv_path)
        print(f"\nInventory saved to: {inv_path}")
        print(f"  Total: {inv['total_deliverables']} deliverables, "
              f"{inv['total_anomaly_mentions']} anomaly mentions, "
              f"{inv['total_key_findings']} key findings")
    else:
        print(f"Path not found: {path}")
        sys.exit(1)
