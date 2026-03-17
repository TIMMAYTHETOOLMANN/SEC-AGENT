"""
JLAW XLS/XLSX Parser
Extracts structured data from SEC EDGAR Excel filings — financial statements,
beneficial ownership tables, Form 4 transaction summaries, and vote tally sheets.

Handles:
- 10-K/10-Q financial data workbooks (XBRL viewer exports)
- Section 16(a) transaction summaries in Excel format
- Annual meeting vote tally sheets (8-K exhibits)
- Beneficial ownership tables
- Compensation summary tables

Input: XLS or XLSX file path
Output: Structured dict with sheets, tables, and extracted data

Usage:
    python -m src.ingestion.xls_parser data/raw-edgar/filings/FY2024/form4_transactions.xlsx
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import openpyxl
import pandas as pd


# ═══════════════════════════════════════════════
# SHEET TYPE DETECTION PATTERNS
# ═══════════════════════════════════════════════

SHEET_CLASSIFIERS = {
    "form4_transactions": [
        r"transaction\s*date", r"shares", r"price", r"acquired",
        r"disposed", r"direct", r"indirect", r"footnote",
    ],
    "beneficial_ownership": [
        r"beneficial\s*owner", r"percent\s*of\s*class", r"shares\s*beneficially",
        r"sole\s*voting", r"shared\s*voting",
    ],
    "compensation_summary": [
        r"salary", r"bonus", r"stock\s*award", r"option\s*award",
        r"incentive", r"total\s*compensation", r"name\s*and\s*principal",
    ],
    "vote_results": [
        r"for\b", r"against\b", r"abstain", r"broker\s*non.vote",
        r"proposal", r"director\s*nominee",
    ],
    "financial_data": [
        r"revenue", r"net\s*income", r"total\s*assets", r"operating\s*income",
        r"earnings\s*per\s*share", r"diluted",
    ],
    "insider_transactions": [
        r"insider", r"section\s*16", r"reporting\s*person",
        r"transaction\s*code", r"form\s*4",
    ],
}


def classify_sheet(df: pd.DataFrame, sheet_name: str) -> str:
    """Classify an Excel sheet based on its header content."""
    # Combine sheet name + first few rows for classification
    header_text = sheet_name.lower() + " "

    # Check column names
    for col in df.columns:
        header_text += str(col).lower() + " "

    # Check first 5 rows
    for _, row in df.head(5).iterrows():
        for val in row:
            if val is not None:
                header_text += str(val).lower() + " "

    # Match against classifiers
    best_match = "unknown"
    best_score = 0
    for sheet_type, keywords in SHEET_CLASSIFIERS.items():
        score = sum(1 for kw in keywords if re.search(kw, header_text, re.IGNORECASE))
        if score > best_score:
            best_score = score
            best_match = sheet_type

    return best_match if best_score >= 2 else "unknown"


def parse_form4_transactions(df: pd.DataFrame) -> List[Dict]:
    """Extract Form 4 transaction data from an Excel sheet."""
    transactions = []

    # Normalize column names
    col_map = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if "date" in col_lower and "transaction" in col_lower:
            col_map["transaction_date"] = col
        elif "date" in col_lower and "fil" in col_lower:
            col_map["filing_date"] = col
        elif "code" in col_lower:
            col_map["code"] = col
        elif "share" in col_lower and "amount" not in col_lower:
            col_map["shares"] = col
        elif "price" in col_lower:
            col_map["price"] = col
        elif "acquir" in col_lower or "dispos" in col_lower:
            col_map["acq_disp"] = col
        elif "name" in col_lower or "reporting" in col_lower or "owner" in col_lower:
            col_map["filer_name"] = col
        elif "direct" in col_lower and "indirect" not in col_lower:
            col_map["ownership_type"] = col

    for _, row in df.iterrows():
        txn = {}
        for field, col in col_map.items():
            val = row.get(col)
            if val is not None and str(val).strip() and str(val).lower() != "nan":
                txn[field] = str(val).strip()
        if txn.get("transaction_date") or txn.get("shares"):
            # Parse numeric fields
            if "shares" in txn:
                try:
                    txn["shares"] = float(str(txn["shares"]).replace(",", ""))
                except (ValueError, TypeError):
                    pass
            if "price" in txn:
                try:
                    txn["price"] = float(str(txn["price"]).replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    pass
            transactions.append(txn)

    return transactions


def parse_beneficial_ownership(df: pd.DataFrame) -> List[Dict]:
    """Extract beneficial ownership table data."""
    owners = []

    col_map = {}
    for col in df.columns:
        cl = str(col).lower().strip()
        if "name" in cl or "owner" in cl:
            col_map["name"] = col
        elif "share" in cl and "percent" not in cl:
            col_map["shares"] = col
        elif "percent" in cl:
            col_map["percent"] = col
        elif "sole" in cl and "vot" in cl:
            col_map["sole_voting"] = col
        elif "shared" in cl and "vot" in cl:
            col_map["shared_voting"] = col

    for _, row in df.iterrows():
        owner = {}
        for field, col in col_map.items():
            val = row.get(col)
            if val is not None and str(val).strip() and str(val).lower() != "nan":
                owner[field] = str(val).strip()
        if owner.get("name"):
            # Parse numeric fields
            for num_field in ["shares", "percent"]:
                if num_field in owner:
                    try:
                        owner[num_field] = float(
                            str(owner[num_field]).replace(",", "").replace("%", "").strip()
                        )
                    except (ValueError, TypeError):
                        pass
            owners.append(owner)

    return owners


def parse_vote_results(df: pd.DataFrame) -> List[Dict]:
    """Extract annual meeting vote tallies."""
    proposals = []

    col_map = {}
    for col in df.columns:
        cl = str(col).lower().strip()
        if "proposal" in cl or "item" in cl or "description" in cl:
            col_map["proposal"] = col
        elif cl.strip() == "for" or "votes for" in cl:
            col_map["votes_for"] = col
        elif "against" in cl:
            col_map["votes_against"] = col
        elif "abstain" in cl:
            col_map["abstain"] = col
        elif "broker" in cl or "non-vote" in cl or "bnv" in cl:
            col_map["broker_non_votes"] = col

    for _, row in df.iterrows():
        proposal = {}
        for field, col in col_map.items():
            val = row.get(col)
            if val is not None and str(val).strip() and str(val).lower() != "nan":
                proposal[field] = str(val).strip()
        if proposal.get("proposal") or proposal.get("votes_for"):
            # Parse numeric vote counts
            for vote_field in ["votes_for", "votes_against", "abstain", "broker_non_votes"]:
                if vote_field in proposal:
                    try:
                        proposal[vote_field] = int(
                            str(proposal[vote_field]).replace(",", "").strip()
                        )
                    except (ValueError, TypeError):
                        pass
            proposals.append(proposal)

    return proposals


def parse_compensation_summary(df: pd.DataFrame) -> List[Dict]:
    """Extract executive compensation summary table."""
    executives = []

    col_map = {}
    for col in df.columns:
        cl = str(col).lower().strip()
        if "name" in cl:
            col_map["name"] = col
        elif "salary" in cl:
            col_map["salary"] = col
        elif "bonus" in cl:
            col_map["bonus"] = col
        elif "stock" in cl and "award" in cl:
            col_map["stock_awards"] = col
        elif "option" in cl:
            col_map["option_awards"] = col
        elif "incentive" in cl or "non-equity" in cl:
            col_map["incentive"] = col
        elif "total" in cl:
            col_map["total"] = col
        elif "year" in cl:
            col_map["year"] = col

    for _, row in df.iterrows():
        exec_data = {}
        for field, col in col_map.items():
            val = row.get(col)
            if val is not None and str(val).strip() and str(val).lower() != "nan":
                exec_data[field] = str(val).strip()
        if exec_data.get("name"):
            # Parse monetary fields
            for money_field in ["salary", "bonus", "stock_awards", "option_awards",
                                "incentive", "total"]:
                if money_field in exec_data:
                    try:
                        exec_data[money_field] = float(
                            str(exec_data[money_field]).replace("$", "").replace(",", "").strip()
                        )
                    except (ValueError, TypeError):
                        pass
            executives.append(exec_data)

    return executives


def parse_xls(xls_path: Path, filing_type: str = None, filed_date: str = None,
              accession_number: str = None) -> Dict:
    """
    Full XLS/XLSX parsing pipeline.

    Args:
        xls_path: Path to the Excel file
        filing_type: Override filing type
        filed_date: Filing date (YYYY-MM-DD)
        accession_number: EDGAR accession number

    Returns:
        Structured dict with all extracted data
    """
    try:
        # Read all sheets
        xls = pd.ExcelFile(xls_path, engine="openpyxl")
    except Exception:
        try:
            xls = pd.ExcelFile(xls_path, engine="xlrd")
        except Exception as e:
            return {
                "error": f"Cannot read Excel file: {str(e)}",
                "source_file": str(xls_path),
                "parsed_at": datetime.now().isoformat(),
            }

    sheets = {}
    extracted_data = {}

    for sheet_name in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name)
        except Exception as e:
            sheets[sheet_name] = {"error": str(e)}
            continue

        # Classify the sheet
        sheet_type = classify_sheet(df, sheet_name)

        # Parse based on classification
        parsed_content = None
        if sheet_type == "form4_transactions":
            parsed_content = parse_form4_transactions(df)
            extracted_data.setdefault("form4_transactions", []).extend(parsed_content)
        elif sheet_type == "beneficial_ownership":
            parsed_content = parse_beneficial_ownership(df)
            extracted_data["beneficial_ownership"] = parsed_content
        elif sheet_type == "vote_results":
            parsed_content = parse_vote_results(df)
            extracted_data["vote_results"] = parsed_content
        elif sheet_type == "compensation_summary":
            parsed_content = parse_compensation_summary(df)
            extracted_data["compensation_summary"] = parsed_content
        elif sheet_type == "insider_transactions":
            parsed_content = parse_form4_transactions(df)  # Similar structure
            extracted_data.setdefault("insider_transactions", []).extend(parsed_content)

        sheets[sheet_name] = {
            "type": sheet_type,
            "rows": len(df),
            "columns": list(str(c) for c in df.columns),
            "record_count": len(parsed_content) if parsed_content else 0,
        }

    # Compute aggregate stats for Form 4 transactions
    form4_stats = {}
    if "form4_transactions" in extracted_data:
        txns = extracted_data["form4_transactions"]
        total_shares_sold = sum(
            t.get("shares", 0) for t in txns
            if isinstance(t.get("shares"), (int, float))
            and str(t.get("acq_disp", "")).upper().startswith("D")
        )
        total_shares_acquired = sum(
            t.get("shares", 0) for t in txns
            if isinstance(t.get("shares"), (int, float))
            and str(t.get("acq_disp", "")).upper().startswith("A")
        )
        form4_stats = {
            "total_transactions": len(txns),
            "total_shares_sold": total_shares_sold,
            "total_shares_acquired": total_shares_acquired,
            "unique_filers": len(set(t.get("filer_name", "") for t in txns if t.get("filer_name"))),
        }

    result = {
        "filing_type": filing_type or "EXCEL_DATA",
        "filing_id": accession_number,
        "filed_date": filed_date,
        "source_file": str(xls_path),
        "sheet_count": len(sheets),
        "sheets": sheets,
        "extracted_data": extracted_data,
        "form4_aggregate_stats": form4_stats,
        "flags": {
            "has_form4_data": "form4_transactions" in extracted_data,
            "has_ownership_data": "beneficial_ownership" in extracted_data,
            "has_vote_data": "vote_results" in extracted_data,
            "has_compensation_data": "compensation_summary" in extracted_data,
        },
        "parsed_at": datetime.now().isoformat(),
    }

    return result


def parse_xls_directory(directory: Path, output_dir: Path) -> List[Dict]:
    """Parse all XLS/XLSX files in a directory tree."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for xls_file in sorted(directory.rglob("*.xls*")):
        if xls_file.suffix.lower() not in (".xls", ".xlsx"):
            continue
        print(f"  Parsing: {xls_file.name}...")
        try:
            parsed = parse_xls(xls_file)

            out_name = xls_file.stem + "_parsed.json"
            out_path = output_dir / out_name
            with open(out_path, "w") as f:
                json.dump(parsed, f, indent=2, default=str)

            results.append({
                "file": str(xls_file),
                "sheets": parsed["sheet_count"],
                "has_form4": parsed["flags"]["has_form4_data"],
                "has_ownership": parsed["flags"]["has_ownership_data"],
                "has_votes": parsed["flags"]["has_vote_data"],
                "output": str(out_path),
            })
        except Exception as e:
            results.append({
                "file": str(xls_file),
                "error": str(e),
            })

    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.ingestion.xls_parser <xls_path_or_directory> [output_dir]")
        sys.exit(1)

    path = Path(sys.argv[1])
    if path.is_file():
        result = parse_xls(path)
        print(json.dumps(result, indent=2, default=str))
    elif path.is_dir():
        output = Path(sys.argv[2]) if len(sys.argv) > 2 else path / "parsed"
        results = parse_xls_directory(path, output)
        print(f"\nParsed {len(results)} files:")
        for r in results:
            if "error" in r:
                print(f"  ✗ {r['file']}: {r['error']}")
            else:
                print(f"  ✓ {r['file']}: {r['sheets']} sheets, "
                      f"form4={r['has_form4']}, ownership={r['has_ownership']}, votes={r['has_votes']}")
    else:
        print(f"Path not found: {path}")
        sys.exit(1)
