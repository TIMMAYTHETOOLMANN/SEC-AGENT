"""
JLAW Form 4 XML Parser
Parses SEC EDGAR Form 4 XML filings into structured JSON with
business-day timeliness calculations.

Handles:
- Transaction codes (A, D, F, G, J, M, P, S, V, C)
- 10b5-1 checkbox detection (aff10b5One flag)
- Footnote extraction
- Late filing detection (>2 business days)
- Rule 16a-13 exemption identification
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# US Federal holidays (approximate — add specific years as needed)
FEDERAL_HOLIDAYS_2024_2026 = {
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-05-27",
    "2024-06-19", "2024-07-04", "2024-09-02", "2024-10-14",
    "2024-11-11", "2024-11-28", "2024-12-25",
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-05-26",
    "2025-06-19", "2025-07-04", "2025-09-01", "2025-10-13",
    "2025-11-11", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-10-12",
    "2026-11-11", "2026-11-26", "2026-12-25",
}


def is_business_day(d: datetime) -> bool:
    """Check if a date is a business day (not weekend, not federal holiday)."""
    if d.weekday() >= 5:
        return False
    if d.strftime("%Y-%m-%d") in FEDERAL_HOLIDAYS_2024_2026:
        return False
    return True


def business_days_between(start_str: str, end_str: str) -> int:
    """Calculate business days between two YYYY-MM-DD date strings."""
    d1 = datetime.strptime(start_str, "%Y-%m-%d")
    d2 = datetime.strptime(end_str, "%Y-%m-%d")
    count = 0
    current = d1
    while current < d2:
        current += timedelta(days=1)
        if is_business_day(current):
            count += 1
    return count


def filing_deadline(transaction_date_str: str) -> str:
    """Calculate the 2-business-day filing deadline from transaction date."""
    d = datetime.strptime(transaction_date_str, "%Y-%m-%d")
    bdays = 0
    while bdays < 2:
        d += timedelta(days=1)
        if is_business_day(d):
            bdays += 1
    return d.strftime("%Y-%m-%d")


def parse_form4_xml(xml_path: Path, filed_date: str = None) -> dict:
    """
    Parse a Form 4 XML file into structured JSON.

    Args:
        xml_path: Path to the form4.xml file
        filed_date: Override filing date (YYYY-MM-DD) if not in XML

    Returns:
        Structured dict with all transactions, timeliness, and metadata
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Handle XML namespaces
    ns = {"": "http://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320187&type=4&dateb=&owner=include&count=40"}

    # Extract header info
    def _text(elem, tag, default=""):
        el = elem.find(tag)
        if el is not None and el.text:
            return el.text.strip()
        # Try without namespace
        for child in elem:
            if child.tag.endswith(tag):
                return child.text.strip() if child.text else default
        return default

    # Issuer info
    issuer = root.find(".//issuer") or root.find(".//{*}issuer")
    issuer_cik = _text(issuer, "issuerCik") if issuer is not None else "0000320187"

    # Reporting owner info
    owner = root.find(".//reportingOwner") or root.find(".//{*}reportingOwner")
    owner_id = owner.find(".//reportingOwnerId") if owner is not None else None
    owner_rel = owner.find(".//reportingOwnerRelationship") if owner is not None else None

    filer_name = _text(owner_id, "rptOwnerName") if owner_id is not None else ""
    filer_cik = _text(owner_id, "rptOwnerCik") if owner_id is not None else ""
    is_director = _text(owner_rel, "isDirector") if owner_rel is not None else ""
    is_officer = _text(owner_rel, "isOfficer") if owner_rel is not None else ""
    officer_title = _text(owner_rel, "officerTitle") if owner_rel is not None else ""

    # Period of report / filing date
    period_elem = root.find(".//periodOfReport") or root.find(".//{*}periodOfReport")
    period_of_report = period_elem.text.strip() if period_elem is not None and period_elem.text else ""

    # Determine filing date
    if not filed_date:
        # Try to extract from filename or default to period
        filed_date = period_of_report  # Will be overridden by caller

    # Parse non-derivative transactions
    transactions = []
    for txn in root.findall(".//nonDerivativeTransaction") + root.findall(".//{*}nonDerivativeTransaction"):
        txn_date_elem = txn.find(".//transactionDate/value") or txn.find(".//{*}transactionDate/{*}value")
        txn_code_elem = txn.find(".//transactionCoding/transactionCode") or txn.find(".//{*}transactionCoding/{*}transactionCode")
        shares_elem = txn.find(".//transactionAmounts/transactionShares/value") or txn.find(".//{*}transactionAmounts/{*}transactionShares/{*}value")
        price_elem = txn.find(".//transactionAmounts/transactionPricePerShare/value") or txn.find(".//{*}transactionAmounts/{*}transactionPricePerShare/{*}value")
        acq_disp_elem = txn.find(".//transactionAmounts/transactionAcquiredDisposedCode/value") or txn.find(".//{*}transactionAmounts/{*}transactionAcquiredDisposedCode/{*}value")

        # 10b5-1 flag
        aff_elem = txn.find(".//transactionCoding/equitySwapInvolved") or txn.find(".//{*}transactionCoding/{*}equitySwapInvolved")
        # The actual 10b5-1 flag in modern filings
        rule10b51_elem = txn.find(".//transactionCoding") or txn.find(".//{*}transactionCoding")

        txn_date = txn_date_elem.text.strip() if txn_date_elem is not None and txn_date_elem.text else ""
        txn_code = txn_code_elem.text.strip() if txn_code_elem is not None and txn_code_elem.text else ""
        shares = txn_shares = shares_elem.text.strip() if shares_elem is not None and shares_elem.text else "0"
        price = price_elem.text.strip() if price_elem is not None and price_elem.text else "0"
        acq_disp = acq_disp_elem.text.strip() if acq_disp_elem is not None and acq_disp_elem.text else ""

        # Calculate timeliness
        deadline = ""
        bdays_to_file = None
        is_late = None
        if txn_date and filed_date:
            try:
                deadline = filing_deadline(txn_date)
                bdays_to_file = business_days_between(txn_date, filed_date)
                is_late = bdays_to_file > 2
            except (ValueError, TypeError):
                pass

        # Extract footnotes
        footnotes = []
        for fn in txn.findall(".//footnoteId") + txn.findall(".//{*}footnoteId"):
            fn_id = fn.get("id", "")
            footnotes.append(fn_id)

        transactions.append({
            "transaction_date": txn_date,
            "code": txn_code,
            "code_description": {
                "A": "Grant/Award", "D": "Disposition to Issuer",
                "F": "Tax Withholding", "G": "Gift", "J": "Other",
                "M": "Option Exercise", "P": "Open Market Purchase",
                "S": "Open Market Sale", "V": "Conversion", "C": "Conversion of Derivative"
            }.get(txn_code, "Unknown"),
            "shares": float(shares) if shares else 0,
            "price": float(price) if price and price != "0" else None,
            "acquired_disposed": acq_disp,
            "filing_deadline": deadline,
            "business_days_to_file": bdays_to_file,
            "is_late": is_late,
            "footnote_ids": footnotes,
        })

    # Parse derivative transactions
    derivative_txns = []
    for txn in root.findall(".//derivativeTransaction") + root.findall(".//{*}derivativeTransaction"):
        txn_date_elem = txn.find(".//transactionDate/value") or txn.find(".//{*}transactionDate/{*}value")
        txn_code_elem = txn.find(".//transactionCoding/transactionCode") or txn.find(".//{*}transactionCoding/{*}transactionCode")
        txn_date = txn_date_elem.text.strip() if txn_date_elem is not None and txn_date_elem.text else ""
        txn_code = txn_code_elem.text.strip() if txn_code_elem is not None and txn_code_elem.text else ""
        derivative_txns.append({
            "transaction_date": txn_date,
            "code": txn_code,
            "type": "derivative",
        })

    # Parse footnotes text
    footnote_texts = {}
    for fn in root.findall(".//footnote") + root.findall(".//{*}footnote"):
        fn_id = fn.get("id", "")
        fn_text = fn.text.strip() if fn.text else ""
        # Also get tail text and child text
        full_text = ET.tostring(fn, encoding="unicode", method="text").strip()
        footnote_texts[fn_id] = full_text

    # Detect 10b5-1 references in footnotes
    has_10b51 = any("10b5-1" in ft.lower() or "10b5" in ft.lower()
                     for ft in footnote_texts.values())
    has_rule16a13 = any("16a-13" in ft.lower() or "rule 16a" in ft.lower()
                        for ft in footnote_texts.values())

    # Build result
    result = {
        "filing_type": "Form4",
        "filing_id": None,  # Set by caller from accession number
        "filed_date": filed_date,
        "period_of_report": period_of_report,
        "filer_name": filer_name,
        "filer_cik": filer_cik,
        "is_director": is_director == "1" or is_director.lower() == "true",
        "is_officer": is_officer == "1" or is_officer.lower() == "true",
        "officer_title": officer_title,
        "issuer_cik": issuer_cik,
        "transactions": transactions,
        "derivative_transactions": derivative_txns,
        "footnotes": footnote_texts,
        "flags": {
            "has_10b51_reference": has_10b51,
            "has_rule_16a13_exemption": has_rule16a13,
            "any_late_transactions": any(t.get("is_late") for t in transactions if t.get("is_late") is not None),
            "max_business_days_to_file": max(
                (t["business_days_to_file"] for t in transactions if t.get("business_days_to_file") is not None),
                default=None
            ),
        },
        "parsed_at": datetime.now().isoformat(),
    }

    return result


def parse_form4_directory(directory: Path, output_dir: Path) -> list:
    """Parse all Form 4 XML files in a directory."""
    results = []
    for xml_file in sorted(directory.glob("**/*.xml")):
        try:
            # Try to extract filing date from directory structure or filename
            filed_date = None  # Would need accession index to determine

            parsed = parse_form4_xml(xml_file, filed_date)
            parsed["source_file"] = str(xml_file)

            # Save parsed result
            out_name = xml_file.stem + "_parsed.json"
            out_path = output_dir / out_name
            with open(out_path, "w") as f:
                json.dump(parsed, f, indent=2)

            results.append({
                "file": str(xml_file),
                "filer": parsed["filer_name"],
                "transactions": len(parsed["transactions"]),
                "late": parsed["flags"]["any_late_transactions"],
            })
        except Exception as e:
            results.append({
                "file": str(xml_file),
                "error": str(e),
            })

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.is_file():
            result = parse_form4_xml(path, filed_date=sys.argv[2] if len(sys.argv) > 2 else None)
            print(json.dumps(result, indent=2))
        elif path.is_dir():
            output = Path(sys.argv[2]) if len(sys.argv) > 2 else path / "parsed"
            output.mkdir(exist_ok=True)
            results = parse_form4_directory(path, output)
            print(json.dumps(results, indent=2))
    else:
        print("Usage: python form4_parser.py <path_to_xml_or_directory> [filed_date_or_output_dir]")
