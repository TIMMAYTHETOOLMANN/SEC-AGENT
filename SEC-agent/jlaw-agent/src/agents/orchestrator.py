"""
JLAW Agent Platform — Orchestrator
Primary coordination agent for the forensic intelligence pipeline.

Usage:
    python -m src.agents.orchestrator                    # Interactive mode
    python -m src.agents.orchestrator --ingest            # Run EDGAR ingestion
    python -m src.agents.orchestrator --cross-ref         # Run cross-reference analysis
    python -m src.agents.orchestrator --report master     # Generate master report
    python -m src.agents.orchestrator --submit sec        # Draft SEC submission
"""

import asyncio
import argparse
import os
import sys
import json
from pathlib import Path
from datetime import datetime

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    ToolUseMessage,
    ToolResultMessage,
)

# ═══════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", PROJECT_ROOT / "data"))
LOG_DIR = Path(os.environ.get("JLAW_LOG_DIR", PROJECT_ROOT / "logs"))

SYSTEM_PROMPT = """You are the JLAW Orchestrator — the primary coordination agent for the
Justice Legal Analysis Workbench forensic intelligence platform, version 5.0.

You are managing a seven-year forensic investigation of Nike, Inc. (CIK 0000320187)
spanning FY2019 through Q1 CY2026. Your role is to:

1. COORDINATE sub-agents for EDGAR ingestion, cross-referencing, report generation,
   and regulatory submission
2. MAINTAIN investigation state across sessions
3. ENSURE no anomaly — however small — is missed or under-documented
4. ENFORCE human-in-the-loop gates for all regulatory submissions
5. PRIORITIZE findings by regulatory relevance (SEC, DOJ, legislative)

CRITICAL PRINCIPLES:
- Every filing matters. A two-day-late Form 4 is as important to document as a
  $565M cumulative insider selling pattern. Compounding patterns emerge from
  granular observations.
- The investigation already has 36 professional deliverables (18 full-corpus,
  12 proxy-focused, 3 foundation, 3 supplemental). Your job is to CROSS-REFERENCE
  them, not replace them.
- NEVER send any communication to a regulatory body without explicit human approval.
- All anomalies must be machine-ingestible: exact dates, exact accession numbers,
  exact transaction codes, exact dollar amounts.

INVESTIGATION STATE:
- Target: Nike, Inc. (NKE), CIK 0000320187
- Scope: FY2019-Q1 CY2026 (Dec 2018 - Mar 2026)
- Key findings: Exhibit 19 self-approval loophole, Swoosh 13D 9.7 years stale,
  $565M+ Parker cumulative sales, securities fraud MTD pending, 14-year SEC
  correspondence gap, Travis Knight late Form 4, buy/sell divergence,
  23 micro-forensic anomalies across 7 fiscal years
- Deliverables: 36 DOCX files across timelines, evidence bundles, ISS memos
- Status: Ready for formal compilation and regulatory submission

Available data directories:
- Raw EDGAR filings: {data_dir}/raw-edgar/
- Parsed data: {data_dir}/parsed/
- Anomaly database: {data_dir}/anomalies/
- Existing deliverables: {data_dir}/deliverables/
- Generated reports: {data_dir}/reports/
- Submission records: {data_dir}/submissions/
""".format(data_dir=DATA_DIR)


async def run_orchestrator(mode: str = "interactive", target: str = None):
    """Main orchestrator entry point."""

    # Ensure directories exist
    for subdir in ["raw-edgar", "parsed", "anomalies", "deliverables",
                   "reports", "submissions"]:
        (DATA_DIR / subdir).mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Build prompt based on mode
    if mode == "interactive":
        prompt = (
            "Initialize the JLAW investigation state. Check what data is available "
            "in the data directories, report what deliverables are present, and "
            "await my instructions for the next action."
        )
    elif mode == "ingest":
        prompt = (
            "Run the EDGAR ingestion pipeline. Parse all raw filings in "
            f"{DATA_DIR}/raw-edgar/ into structured JSON in {DATA_DIR}/parsed/. "
            "For each filing, extract: accession number, filing type, fiscal year, "
            "period end date, signers, exhibit index, and any Section 16/proxy sections. "
            "For Form 4s, calculate timeliness in business days."
        )
    elif mode == "cross-ref":
        prompt = (
            "Run the cross-reference analysis across all parsed filings. "
            "Compare against the 23 micro-forensic anomalies identified in the "
            "re-audit. Identify any NEW compounding patterns not previously documented. "
            "Output results to the anomaly database."
        )
    elif mode == "report":
        prompt = (
            f"Generate the {target} report using all available parsed data, "
            "anomaly database, and existing deliverables as source material. "
            "Ensure every finding is supported by exact accession numbers and dates."
        )
    elif mode == "submit":
        prompt = (
            f"Prepare a submission draft for {target}. Pull from the latest "
            "generated reports and the anomaly database. Format according to the "
            "target agency's submission requirements. Present the draft for my "
            "review — DO NOT SEND without my explicit approval."
        )
    else:
        prompt = f"Execute command: {mode}"

    # Configure agent options
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        model="claude-sonnet-4-20250514",
        cwd=str(PROJECT_ROOT),
    )

    # Log session start
    session_log = {
        "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "mode": mode,
        "target": target,
        "started_at": datetime.now().isoformat(),
        "messages": [],
    }

    print(f"\n{'='*60}")
    print(f"  JLAW ORCHESTRATOR v5.0 — {mode.upper()} MODE")
    print(f"  Target: Nike, Inc. (CIK 0000320187)")
    print(f"  Session: {session_log['session_id']}")
    print(f"{'='*60}\n")

    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                print(f"\n[JLAW] {message.content}")
                session_log["messages"].append({
                    "type": "assistant",
                    "content": str(message.content),
                    "timestamp": datetime.now().isoformat(),
                })
            elif isinstance(message, ResultMessage):
                print(f"\n[RESULT] {message.result}")
                session_log["messages"].append({
                    "type": "result",
                    "content": str(message.result),
                    "timestamp": datetime.now().isoformat(),
                })
            elif isinstance(message, ToolUseMessage):
                print(f"\n[TOOL] {message.tool_name}: {str(message.input)[:200]}")
                session_log["messages"].append({
                    "type": "tool_use",
                    "tool": message.tool_name,
                    "input": str(message.input)[:500],
                    "timestamp": datetime.now().isoformat(),
                })

    except KeyboardInterrupt:
        print("\n\n[JLAW] Session interrupted by user.")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        session_log["error"] = str(e)
    finally:
        # Save session log
        session_log["ended_at"] = datetime.now().isoformat()
        log_file = LOG_DIR / f"session_{session_log['session_id']}.json"
        with open(log_file, "w") as f:
            json.dump(session_log, f, indent=2)
        print(f"\n[JLAW] Session log saved: {log_file}")


def main():
    parser = argparse.ArgumentParser(description="JLAW Agent Platform Orchestrator")
    parser.add_argument("--ingest", action="store_true", help="Run EDGAR ingestion")
    parser.add_argument("--cross-ref", action="store_true", help="Run cross-reference")
    parser.add_argument("--report", type=str, help="Generate report (master|sec|doj|legislative)")
    parser.add_argument("--submit", type=str, help="Draft submission (sec|doj|congress)")
    parser.add_argument("--command", type=str, help="Custom command")

    args = parser.parse_args()

    if args.ingest:
        asyncio.run(run_orchestrator("ingest"))
    elif args.cross_ref:
        asyncio.run(run_orchestrator("cross-ref"))
    elif args.report:
        asyncio.run(run_orchestrator("report", args.report))
    elif args.submit:
        asyncio.run(run_orchestrator("submit", args.submit))
    elif args.command:
        asyncio.run(run_orchestrator(args.command))
    else:
        asyncio.run(run_orchestrator("interactive"))


if __name__ == "__main__":
    main()
