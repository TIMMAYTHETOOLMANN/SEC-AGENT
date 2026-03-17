"""
JLAW EDGAR RSS/XML Index Parser
Parses the SEC EDGAR full-text filing index (RSS-style XML) into a
structured filing inventory with accession numbers, dates, and types.

Input: The EDGAR company filing index XML (from the EDGAR full-index
       or company search RSS feed)
Output: Structured JSON inventory of all Nike filings

Usage:
    python -m src.ingestion.rss_parser data/raw-edgar/rss-dump/nike_full_index.xml
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import List, Dict


NIKE_CIK = "0000320187"

# Fiscal year mapping for Nike (FY ends May 31)
def fiscal_year_for_date(date_str: str) -> str:
    """Determine Nike fiscal year from a filing date string."""
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return "UNKNOWN"
    # Nike FY ends May 31. FY2024 = Jun 2023 - May 2024
    if d.month <= 5:
        return f"FY{d.year}"
    else:
        return f"FY{d.year + 1}"


def normalize_filing_type(raw_type: str) -> str:
    """Normalize filing type strings to standard categories."""
    t = raw_type.strip().upper()
    mapping = {
        "10-K": "10-K",
        "10-K/A": "10-K/A",
        "10-Q": "10-Q",
        "10-Q/A": "10-Q/A",
        "8-K": "8-K",
        "8-K/A": "8-K/A",
        "DEF 14A": "DEF14A",
        "DEFA14A": "DEF14A",
        "4": "Form4",
        "4/A": "Form4/A",
        "3": "Form3",
        "3/A": "Form3/A",
        "5": "Form5",
        "SC 13D": "SC13D",
        "SC 13D/A": "SC13D/A",
        "SC 13G": "SC13G",
        "SC 13G/A": "SC13G/A",
        "S-8": "S-8",
        "S-3": "S-3",
        "S-3ASR": "S-3ASR",
        "424B2": "424B2",
        "CORRESP": "CORRESP",
        "UPLOAD": "CORRESP",
        "144": "Form144",
    }
    for key, val in mapping.items():
        if t == key or t.startswith(key):
            return val
    return t


def parse_edgar_rss(xml_path: Path) -> List[Dict]:
    """
    Parse an EDGAR RSS/XML index file into structured filing records.

    Handles multiple XML formats:
    1. EDGAR full-index format (company.idx converted to XML)
    2. RSS feed format from EDGAR company search
    3. XBRL filing index format
    """
    filings = []

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError:
        # Try parsing as a text index file
        return parse_text_index(xml_path)

    # Detect format and parse accordingly
    # Format 1: RSS feed (<rss><channel><item>...)
    for item in root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        filing = _parse_rss_item(item)
        if filing:
            filings.append(filing)

    # Format 2: EDGAR filing index (<filing>...)
    for elem in root.findall(".//filing") + root.findall(".//{*}filing"):
        filing = _parse_filing_elem(elem)
        if filing:
            filings.append(filing)

    # Format 3: Generic document listing
    if not filings:
        for elem in root.iter():
            if "accession" in elem.tag.lower() or "filing" in elem.tag.lower():
                filing = _parse_generic_elem(elem, root)
                if filing:
                    filings.append(filing)

    # Deduplicate by accession number
    seen = set()
    unique = []
    for f in filings:
        acc = f.get("accession_number", "")
        if acc and acc not in seen:
            seen.add(acc)
            unique.append(f)

    # Sort by filing date
    unique.sort(key=lambda x: x.get("filing_date", "0000-00-00"))

    return unique


def _parse_rss_item(item) -> Dict:
    """Parse an RSS <item> element."""
    def _text(tag):
        for child in item:
            clean_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if clean_tag.lower() == tag.lower():
                return child.text.strip() if child.text else ""
        return ""

    title = _text("title") or _text("description")
    link = _text("link") or _text("id")
    pub_date = _text("pubDate") or _text("updated") or _text("date")
    filing_type = _text("type") or _text("formType")

    # Extract accession number from link
    accession = ""
    if link:
        parts = link.split("/")
        for p in parts:
            if "-" in p and len(p) > 15:
                accession = p.replace("-", "").strip()
                break

    if not filing_type and title:
        # Try to extract from title
        for ft in ["10-K", "10-Q", "8-K", "DEF 14A", "SC 13D", "S-8", "4", "3", "5"]:
            if ft in title:
                filing_type = ft
                break

    # Parse date
    filing_date = ""
    if pub_date:
        for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"]:
            try:
                filing_date = datetime.strptime(pub_date[:25].strip(), fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    if not filing_type:
        return None

    return {
        "accession_number": accession,
        "filing_type": normalize_filing_type(filing_type),
        "filing_date": filing_date,
        "fiscal_year": fiscal_year_for_date(filing_date),
        "title": title[:200],
        "url": link,
        "cik": NIKE_CIK,
    }


def _parse_filing_elem(elem) -> Dict:
    """Parse an EDGAR <filing> element."""
    def _text(tag):
        child = elem.find(tag) or elem.find(f"{{*}}{tag}")
        return child.text.strip() if child is not None and child.text else ""

    return {
        "accession_number": _text("accessionNumber") or _text("accession-number"),
        "filing_type": normalize_filing_type(_text("type") or _text("formType") or _text("form-type")),
        "filing_date": _text("dateFiled") or _text("date-filed") or _text("filingDate"),
        "fiscal_year": fiscal_year_for_date(_text("dateFiled") or _text("filingDate") or ""),
        "title": _text("title") or _text("description"),
        "url": _text("filingHref") or _text("url") or "",
        "cik": _text("cik") or NIKE_CIK,
    }


def _parse_generic_elem(elem, root) -> Dict:
    """Fallback parser for unrecognized XML structures."""
    text = elem.text.strip() if elem.text else ""
    if not text:
        return None
    return {
        "accession_number": text if "-" in text and len(text) > 15 else "",
        "filing_type": "UNKNOWN",
        "filing_date": "",
        "fiscal_year": "UNKNOWN",
        "title": text[:200],
        "url": "",
        "cik": NIKE_CIK,
    }


def parse_text_index(path: Path) -> List[Dict]:
    """Parse a plain-text EDGAR index file (company.idx format)."""
    filings = []
    with open(path, "r", errors="replace") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) >= 4:
                filing_type = parts[0].strip()
                date_filed = parts[3].strip() if len(parts) > 3 else ""
                accession = parts[4].strip() if len(parts) > 4 else ""
                if filing_type and date_filed:
                    filings.append({
                        "accession_number": accession,
                        "filing_type": normalize_filing_type(filing_type),
                        "filing_date": date_filed,
                        "fiscal_year": fiscal_year_for_date(date_filed),
                        "title": "",
                        "url": "",
                        "cik": NIKE_CIK,
                    })
    return filings


def build_filing_inventory(filings: List[Dict], output_path: Path):
    """Build a comprehensive filing inventory organized by fiscal year."""
    inventory = {
        "generated_at": datetime.now().isoformat(),
        "total_filings": len(filings),
        "cik": NIKE_CIK,
        "company": "Nike, Inc.",
        "by_fiscal_year": {},
        "by_type": {},
    }

    for f in filings:
        fy = f.get("fiscal_year", "UNKNOWN")
        ft = f.get("filing_type", "UNKNOWN")

        inventory["by_fiscal_year"].setdefault(fy, []).append(f)
        inventory["by_type"].setdefault(ft, []).append(f)

    # Summary stats
    inventory["summary"] = {
        fy: {
            "total": len(items),
            "types": dict(sorted(
                {ft: len([i for i in items if i["filing_type"] == ft])
                 for ft in set(i["filing_type"] for i in items)}.items()
            ))
        }
        for fy, items in sorted(inventory["by_fiscal_year"].items())
    }

    with open(output_path, "w") as f:
        json.dump(inventory, f, indent=2)

    return inventory


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.ingestion.rss_parser <xml_path> [output_path]")
        sys.exit(1)

    xml_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else xml_path.parent / "filing_inventory.json"

    print(f"Parsing: {xml_path}")
    filings = parse_edgar_rss(xml_path)
    print(f"Found {len(filings)} filings")

    inventory = build_filing_inventory(filings, output_path)
    print(f"Inventory saved to: {output_path}")

    # Print summary
    for fy, stats in sorted(inventory["summary"].items()):
        print(f"  {fy}: {stats['total']} filings — {stats['types']}")
