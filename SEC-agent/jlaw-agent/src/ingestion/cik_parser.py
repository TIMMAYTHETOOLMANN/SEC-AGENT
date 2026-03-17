"""
JLAW CIK Company Facts Parser
Parses the SEC EDGAR Company Facts API JSON (XBRL structured data).
Extracts financial time-series, filing metadata, and cross-reference material.

Input: CIK0000320187.json (from EDGAR Company Facts API)
Output: Structured filing inventory + financial time-series

Usage:
    python -m src.ingestion.cik_parser data/raw-edgar/reference/CIK0000320187.json
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


def parse_cik_facts(json_path: Path) -> Dict:
    """
    Parse SEC EDGAR Company Facts API JSON into structured data.

    The Company Facts API provides XBRL-tagged financial data across all filings,
    organized by taxonomy namespace (dei, us-gaap, invest) and concept.

    Returns:
        Dict with entity info, filing inventory, and financial time-series
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entity_name = data.get("entityName", "")
    cik = str(data.get("cik", ""))

    facts = data.get("facts", {})
    result = {
        "entity_name": entity_name,
        "cik": cik,
        "cik_padded": cik.zfill(10),
        "namespaces": {},
        "filing_dates": set(),
        "accession_numbers": set(),
        "financial_series": {},
        "parsed_at": datetime.now().isoformat(),
    }

    for namespace, concepts in facts.items():
        ns_summary = {"concept_count": 0, "concepts": {}}

        for concept_name, concept_data in concepts.items():
            ns_summary["concept_count"] += 1
            units_data = concept_data.get("units", {})

            for unit_type, entries in units_data.items():
                series_key = f"{namespace}:{concept_name}:{unit_type}"
                series = []

                for entry in entries:
                    # Extract filing metadata
                    filed = entry.get("filed", "")
                    accn = entry.get("accn", "")
                    form = entry.get("form", "")
                    fp = entry.get("fp", "")  # fiscal period (FY, Q1, Q2, Q3)
                    fy = entry.get("fy")  # fiscal year
                    val = entry.get("val")
                    start = entry.get("start", "")
                    end = entry.get("end", "")

                    if filed:
                        result["filing_dates"].add(filed)
                    if accn:
                        result["accession_numbers"].add(accn)

                    series.append({
                        "value": val,
                        "unit": unit_type,
                        "filed": filed,
                        "accession": accn,
                        "form": form,
                        "fiscal_period": fp,
                        "fiscal_year": fy,
                        "start": start,
                        "end": end,
                    })

                if series:
                    result["financial_series"][series_key] = series

            ns_summary["concepts"][concept_name] = {
                "units": list(units_data.keys()),
                "entry_count": sum(len(v) for v in units_data.values()),
            }

        result["namespaces"][namespace] = ns_summary

    # Convert sets to sorted lists for JSON serialization
    result["filing_dates"] = sorted(result["filing_dates"])
    result["accession_numbers"] = sorted(result["accession_numbers"])

    # Build filing inventory from accession numbers
    result["filing_inventory"] = build_filing_inventory_from_facts(result)

    return result


def build_filing_inventory_from_facts(parsed: Dict) -> Dict:
    """Build a filing inventory by cross-referencing accession numbers and forms."""
    inventory = {}

    for series_key, entries in parsed.get("financial_series", {}).items():
        for entry in entries:
            accn = entry.get("accession", "")
            if not accn:
                continue
            if accn not in inventory:
                inventory[accn] = {
                    "accession": accn,
                    "form": entry.get("form", ""),
                    "filed": entry.get("filed", ""),
                    "fiscal_year": entry.get("fiscal_year"),
                    "fiscal_period": entry.get("fiscal_period", ""),
                    "concepts_reported": set(),
                }
            inventory[accn]["concepts_reported"].add(series_key.split(":")[1])

    # Convert sets to counts for serialization
    for accn, info in inventory.items():
        info["concept_count"] = len(info["concepts_reported"])
        info["concepts_reported"] = sorted(list(info["concepts_reported"]))[:20]  # Cap for readability

    return inventory


def extract_key_financials(parsed: Dict) -> Dict:
    """Extract key financial metrics for forensic analysis."""
    key_concepts = {
        "revenue": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "net_income": "us-gaap:NetIncomeLoss",
        "total_assets": "us-gaap:Assets",
        "total_equity": "us-gaap:StockholdersEquity",
        "shares_outstanding": "dei:EntityCommonStockSharesOutstanding",
        "eps_diluted": "us-gaap:EarningsPerShareDiluted",
        "operating_income": "us-gaap:OperatingIncomeLoss",
        "cash": "us-gaap:CashAndCashEquivalentsAtCarryingValue",
    }

    financials = {}
    for metric_name, concept_key in key_concepts.items():
        # Try common unit types
        for unit in ["USD", "shares", "USD/shares", "pure"]:
            series_key = f"{concept_key.replace(':', ':')}:{unit}"
            entries = parsed.get("financial_series", {}).get(series_key, [])
            if entries:
                # Get only annual (FY) entries, sorted by fiscal year
                annual = [e for e in entries if e.get("fiscal_period") == "FY"]
                annual.sort(key=lambda x: x.get("fiscal_year", 0))
                financials[metric_name] = [{
                    "fiscal_year": e.get("fiscal_year"),
                    "value": e.get("value"),
                    "filed": e.get("filed"),
                    "form": e.get("form"),
                } for e in annual]
                break

    return financials


def save_parsed_output(parsed: Dict, output_dir: Path):
    """Save parsed CIK data to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Main parsed output (without full series to keep manageable)
    summary = {
        "entity_name": parsed["entity_name"],
        "cik": parsed["cik"],
        "cik_padded": parsed["cik_padded"],
        "namespaces": parsed["namespaces"],
        "total_filing_dates": len(parsed["filing_dates"]),
        "filing_date_range": f"{parsed['filing_dates'][0]} to {parsed['filing_dates'][-1]}" if parsed["filing_dates"] else "",
        "total_accessions": len(parsed["accession_numbers"]),
        "total_series": len(parsed["financial_series"]),
        "parsed_at": parsed["parsed_at"],
    }

    with open(output_dir / "cik_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Filing inventory
    with open(output_dir / "cik_filing_inventory.json", "w") as f:
        json.dump(parsed["filing_inventory"], f, indent=2, default=list)

    # Key financials
    financials = extract_key_financials(parsed)
    with open(output_dir / "cik_key_financials.json", "w") as f:
        json.dump(financials, f, indent=2)

    # Accession number list (for cross-referencing with raw filings)
    with open(output_dir / "cik_accession_numbers.json", "w") as f:
        json.dump(sorted(parsed["accession_numbers"]), f, indent=2)

    return {
        "summary": str(output_dir / "cik_summary.json"),
        "inventory": str(output_dir / "cik_filing_inventory.json"),
        "financials": str(output_dir / "cik_key_financials.json"),
        "accessions": str(output_dir / "cik_accession_numbers.json"),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.ingestion.cik_parser <cik_json_path> [output_dir]")
        sys.exit(1)

    json_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else json_path.parent / "parsed"

    print(f"Parsing: {json_path}")
    parsed = parse_cik_facts(json_path)

    print(f"Entity: {parsed['entity_name']} (CIK {parsed['cik']})")
    print(f"Filing dates: {len(parsed['filing_dates'])} ({parsed['filing_dates'][0]} to {parsed['filing_dates'][-1]})")
    print(f"Accession numbers: {len(parsed['accession_numbers'])}")
    print(f"Financial series: {len(parsed['financial_series'])}")

    outputs = save_parsed_output(parsed, output_dir)
    print(f"\nOutput saved to {output_dir}/:")
    for name, path in outputs.items():
        print(f"  {name}: {path}")
