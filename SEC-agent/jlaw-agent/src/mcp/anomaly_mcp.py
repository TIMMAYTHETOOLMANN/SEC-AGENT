"""
JLAW Anomaly MCP Server
Manages the anomaly database for cross-year pattern detection.

Run standalone: python -m src.mcp.anomaly_mcp
Used by cross_reference and report_generator agents via stdio transport.
"""

import json
import os
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from claude_agent_sdk import tool, create_sdk_mcp_server

DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", "./data"))
ANOMALY_DIR = DATA_DIR / "anomalies"
ANOMALY_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = ANOMALY_DIR / "anomaly_database.json"


def _load_db() -> dict:
    if DB_FILE.exists():
        with open(DB_FILE) as f:
            return json.load(f)
    return {"anomalies": [], "patterns": [], "last_updated": None}


def _save_db(db: dict):
    db["last_updated"] = datetime.now().isoformat()
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


@tool(
    "anomaly_search",
    "Search anomalies by category, severity, fiscal year, or keyword.",
    {
        "category": str,       # e.g., "insider_trading", "section_16", "swoosh_13d", "proxy", "exhibit"
        "severity": str,       # "STRUCTURAL", "HIGH", "MEDIUM", "LOW"
        "fiscal_year": str,    # e.g., "FY2024"
    }
)
async def anomaly_search(args):
    db = _load_db()
    results = db["anomalies"]
    if args.get("category"):
        results = [a for a in results if a.get("category") == args["category"]]
    if args.get("severity"):
        results = [a for a in results if a.get("severity") == args["severity"]]
    if args.get("fiscal_year"):
        results = [a for a in results if args["fiscal_year"] in a.get("compounding_years", [])]
    return {"content": [{"type": "text", "text": json.dumps({
        "count": len(results),
        "anomalies": results
    }, indent=2)}]}


@tool(
    "anomaly_create",
    "Register a new anomaly with evidence. Requires: category, severity, title, description, "
    "fiscal_year, filing_id, and evidence list. Returns anomaly_id.",
    {
        "category": str,
        "severity": str,
        "fiscal_year": str,
        "filing_id": str,
        "title": str,
        "description": str,
        "evidence": list,
        "compounding_years": list,
        "regulatory_relevance": dict,
    }
)
async def anomaly_create(args):
    db = _load_db()
    anomaly_id = f"ANO-{args['fiscal_year'].replace('FY','')}-{str(len(db['anomalies'])+1).zfill(3)}"
    anomaly = {
        "anomaly_id": anomaly_id,
        "category": args["category"],
        "severity": args["severity"],
        "fiscal_year": args["fiscal_year"],
        "filing_id": args["filing_id"],
        "title": args["title"],
        "description": args["description"],
        "evidence": args.get("evidence", []),
        "compounding_years": args.get("compounding_years", [args["fiscal_year"]]),
        "regulatory_relevance": args.get("regulatory_relevance", {}),
        "created_at": datetime.now().isoformat(),
        "linked_patterns": [],
    }
    db["anomalies"].append(anomaly)
    _save_db(db)
    return {"content": [{"type": "text", "text": json.dumps({
        "status": "CREATED",
        "anomaly_id": anomaly_id,
        "title": args["title"],
    }, indent=2)}]}


@tool(
    "anomaly_get_pattern",
    "Get a compounding pattern that spans multiple fiscal years.",
    {"pattern_id": str}
)
async def anomaly_get_pattern(args):
    db = _load_db()
    pattern = next((p for p in db["patterns"] if p["pattern_id"] == args["pattern_id"]), None)
    if pattern:
        linked = [a for a in db["anomalies"] if a["anomaly_id"] in pattern.get("anomaly_ids", [])]
        pattern["linked_anomalies"] = linked
        return {"content": [{"type": "text", "text": json.dumps(pattern, indent=2)}]}
    return {"content": [{"type": "text", "text": f"Pattern {args['pattern_id']} not found."}]}


@tool(
    "anomaly_link",
    "Link multiple anomalies into a compounding pattern.",
    {
        "pattern_title": str,
        "anomaly_ids": list,
        "description": str,
    }
)
async def anomaly_link(args):
    db = _load_db()
    pattern_id = f"PAT-{str(len(db['patterns'])+1).zfill(3)}"
    pattern = {
        "pattern_id": pattern_id,
        "title": args["pattern_title"],
        "anomaly_ids": args["anomaly_ids"],
        "description": args["description"],
        "created_at": datetime.now().isoformat(),
        "years_spanned": sorted(set(
            yr for a in db["anomalies"]
            if a["anomaly_id"] in args["anomaly_ids"]
            for yr in a.get("compounding_years", [])
        )),
    }
    db["patterns"].append(pattern)
    for a in db["anomalies"]:
        if a["anomaly_id"] in args["anomaly_ids"]:
            a.setdefault("linked_patterns", []).append(pattern_id)
    _save_db(db)
    return {"content": [{"type": "text", "text": json.dumps({
        "status": "PATTERN CREATED",
        "pattern_id": pattern_id,
        "linked_anomalies": len(args["anomaly_ids"]),
        "years_spanned": pattern["years_spanned"],
    }, indent=2)}]}


@tool(
    "anomaly_export",
    "Export all anomalies and patterns for report generation. Returns complete database.",
    {}
)
async def anomaly_export(args):
    db = _load_db()
    return {"content": [{"type": "text", "text": json.dumps(db, indent=2)}]}


@tool(
    "anomaly_get_timeline",
    "Get chronological sequence of all anomalies across the investigation.",
    {}
)
async def anomaly_get_timeline(args):
    db = _load_db()
    timeline = sorted(db["anomalies"], key=lambda a: a.get("fiscal_year", ""))
    return {"content": [{"type": "text", "text": json.dumps({
        "total": len(timeline),
        "timeline": [{
            "id": a["anomaly_id"],
            "year": a["fiscal_year"],
            "severity": a["severity"],
            "title": a["title"],
            "patterns": a.get("linked_patterns", []),
        } for a in timeline]
    }, indent=2)}]}


server = create_sdk_mcp_server(
    name="anomaly_mcp",
    version="1.0.0",
    tools=[
        anomaly_search,
        anomaly_create,
        anomaly_get_pattern,
        anomaly_link,
        anomaly_export,
        anomaly_get_timeline,
    ]
)

if __name__ == "__main__":
    server.run()
