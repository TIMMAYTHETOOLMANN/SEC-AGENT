"""
JLAW EDGAR MCP Server
Provides tools for querying parsed EDGAR filing data.

Run standalone: python -m src.mcp.edgar_mcp
Used by agents via stdio transport.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from claude_agent_sdk import tool, create_sdk_mcp_server

DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", "./data"))
PARSED_DIR = DATA_DIR / "parsed"
ANOMALY_DIR = DATA_DIR / "anomalies"


def _load_json(filepath: Path) -> dict:
    """Load a JSON file, return empty dict if not found."""
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return {}


def _find_filings(fiscal_year: str = None, filing_type: str = None) -> list:
    """Search parsed filings by year and/or type."""
    results = []
    search_dirs = [PARSED_DIR / fy for fy in os.listdir(PARSED_DIR)] if not fiscal_year \
        else [PARSED_DIR / fiscal_year]

    for fy_dir in search_dirs:
        if not fy_dir.is_dir():
            continue
        for f in fy_dir.glob("*.json"):
            data = _load_json(f)
            if filing_type and data.get("filing_type") != filing_type:
                continue
            results.append(data)

    return sorted(results, key=lambda x: x.get("filed_date", ""))


def _business_days_between(start: str, end: str) -> int:
    """Calculate business days between two date strings (YYYY-MM-DD)."""
    d1 = datetime.strptime(start, "%Y-%m-%d")
    d2 = datetime.strptime(end, "%Y-%m-%d")
    days = 0
    current = d1
    while current < d2:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Monday=0 through Friday=4
            days += 1
    return days


# ═══════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════

@tool(
    "edgar_search_filings",
    "Search parsed EDGAR filings by fiscal year and/or filing type. Returns filing metadata.",
    {
        "fiscal_year": str,  # e.g., "FY2024"
        "filing_type": str,  # e.g., "10-K", "Form4", "DEF14A"
    }
)
async def edgar_search_filings(args):
    fy = args.get("fiscal_year")
    ft = args.get("filing_type")
    results = _find_filings(fy, ft)
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "count": len(results),
                "filings": [{
                    "filing_id": r.get("filing_id"),
                    "filing_type": r.get("filing_type"),
                    "fiscal_year": r.get("fiscal_year"),
                    "filed_date": r.get("filed_date"),
                    "period_end": r.get("period_end"),
                } for r in results]
            }, indent=2)
        }]
    }


@tool(
    "edgar_get_filing",
    "Get full parsed filing data by accession number (filing_id).",
    {"filing_id": str}
)
async def edgar_get_filing(args):
    filing_id = args["filing_id"]
    # Search all parsed directories
    for fy_dir in PARSED_DIR.iterdir():
        if not fy_dir.is_dir():
            continue
        for f in fy_dir.glob("*.json"):
            data = _load_json(f)
            if data.get("filing_id") == filing_id:
                return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}
    return {"content": [{"type": "text", "text": f"Filing {filing_id} not found in parsed data."}]}


@tool(
    "edgar_get_form4_timeliness",
    "Get Form 4 filing with timeliness calculation in business days. "
    "Returns transaction date, filing date, business days elapsed, and whether it was late (>2 days).",
    {
        "filer_name": str,       # e.g., "Travis A. Knight"
        "fiscal_year": str,      # e.g., "FY2025"
    }
)
async def edgar_get_form4_timeliness(args):
    filer = args["filer_name"].lower()
    filings = _find_filings(args.get("fiscal_year"), "Form4")
    results = []
    for f in filings:
        if filer in f.get("filer_name", "").lower():
            for txn in f.get("transactions", []):
                txn_date = txn.get("transaction_date")
                file_date = f.get("filed_date")
                if txn_date and file_date:
                    bdays = _business_days_between(txn_date, file_date)
                    results.append({
                        "filer": f.get("filer_name"),
                        "transaction_date": txn_date,
                        "filed_date": file_date,
                        "business_days": bdays,
                        "late": bdays > 2,
                        "transaction_code": txn.get("code"),
                        "shares": txn.get("shares"),
                        "price": txn.get("price"),
                        "footnotes": txn.get("footnotes", []),
                    })
    return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}


@tool(
    "edgar_get_proxy_section",
    "Extract a specific section from a parsed DEF 14A proxy statement.",
    {
        "fiscal_year": str,        # e.g., "FY2024"
        "section": str,            # e.g., "section_16a", "say_on_pay", "beneficial_ownership", "compensation"
    }
)
async def edgar_get_proxy_section(args):
    filings = _find_filings(args["fiscal_year"], "DEF14A")
    if not filings:
        return {"content": [{"type": "text", "text": f"No DEF 14A found for {args['fiscal_year']}"}]}
    proxy = filings[0]
    section_data = proxy.get("sections", {}).get(args["section"])
    if section_data:
        return {"content": [{"type": "text", "text": json.dumps(section_data, indent=2)}]}
    return {"content": [{"type": "text",
            "text": f"Section '{args['section']}' not found. Available: {list(proxy.get('sections', {}).keys())}"}]}


@tool(
    "edgar_get_vote_counts",
    "Get annual meeting voting results for a fiscal year. Returns exact FOR/AGAINST/ABSTAIN/BNV counts.",
    {"fiscal_year": str}
)
async def edgar_get_vote_counts(args):
    filings = _find_filings(args["fiscal_year"], "8-K_annual_meeting")
    if not filings:
        # Fall back to searching all 8-Ks
        filings = [f for f in _find_filings(args["fiscal_year"], "8-K")
                   if "annual_meeting" in str(f.get("items", []))]
    if filings:
        return {"content": [{"type": "text", "text": json.dumps(filings[0].get("vote_results", {}), indent=2)}]}
    return {"content": [{"type": "text", "text": f"No annual meeting results found for {args['fiscal_year']}"}]}


@tool(
    "edgar_compare_exhibits",
    "Compare an exhibit across two fiscal years. Shows additions, removals, and changes.",
    {
        "exhibit_number": str,   # e.g., "19.1", "19.2"
        "year_a": str,           # e.g., "FY2024"
        "year_b": str,           # e.g., "FY2025"
    }
)
async def edgar_compare_exhibits(args):
    filings_a = _find_filings(args["year_a"], "10-K")
    filings_b = _find_filings(args["year_b"], "10-K")

    def get_exhibit(filings, num):
        for f in filings:
            for ex in f.get("exhibits", []):
                if ex.get("number") == num:
                    return ex
        return None

    ex_a = get_exhibit(filings_a, args["exhibit_number"])
    ex_b = get_exhibit(filings_b, args["exhibit_number"])

    return {"content": [{"type": "text", "text": json.dumps({
        "exhibit": args["exhibit_number"],
        "year_a": {"year": args["year_a"], "found": ex_a is not None, "data": ex_a},
        "year_b": {"year": args["year_b"], "found": ex_b is not None, "data": ex_b},
        "comparison": "IDENTICAL" if ex_a == ex_b else "DIFFERENT" if ex_a and ex_b else "MISSING_IN_ONE_YEAR"
    }, indent=2)}]}


@tool(
    "edgar_timeline_query",
    "Query events across all fiscal years within a date range. Returns chronological sequence.",
    {
        "start_date": str,  # YYYY-MM-DD
        "end_date": str,    # YYYY-MM-DD
    }
)
async def edgar_timeline_query(args):
    all_filings = _find_filings()
    filtered = [
        f for f in all_filings
        if f.get("filed_date", "9999") >= args["start_date"]
        and f.get("filed_date", "0000") <= args["end_date"]
    ]
    return {"content": [{"type": "text", "text": json.dumps({
        "date_range": f"{args['start_date']} to {args['end_date']}",
        "count": len(filtered),
        "events": [{
            "date": f.get("filed_date"),
            "type": f.get("filing_type"),
            "id": f.get("filing_id"),
            "summary": f.get("summary", ""),
        } for f in filtered]
    }, indent=2)}]}


# ═══════════════════════════════════════════════
# SERVER INITIALIZATION
# ═══════════════════════════════════════════════

server = create_sdk_mcp_server(
    name="edgar_mcp",
    version="1.0.0",
    tools=[
        edgar_search_filings,
        edgar_get_filing,
        edgar_get_form4_timeliness,
        edgar_get_proxy_section,
        edgar_get_vote_counts,
        edgar_compare_exhibits,
        edgar_timeline_query,
    ]
)

if __name__ == "__main__":
    server.run()
