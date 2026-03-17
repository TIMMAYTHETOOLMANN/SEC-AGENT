#!/usr/bin/env python3
"""
JLAW Agent Platform v5.0 — Primary CLI Entry Point

Full pipeline: python run.py pipeline
Individual phases: python run.py ingest | crossref | report | submit
Interactive mode: python run.py interactive

Local machine deployment. CLI-first interface.
Supports both Claude Agent SDK (remote agent) and direct module execution (local).
"""

import asyncio
import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# ═══════════════════════════════════════════════
# PATHS & ENVIRONMENT
# ═══════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "config" / ".env.template")

DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", PROJECT_ROOT / "data"))
LOG_DIR = Path(os.environ.get("JLAW_LOG_DIR", PROJECT_ROOT / "logs"))

# Detect whether the Claude Agent SDK is available
AGENT_SDK_AVAILABLE = False
try:
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage
    AGENT_SDK_AVAILABLE = True
except ImportError:
    pass

# ═══════════════════════════════════════════════
# BANNER
# ═══════════════════════════════════════════════

BANNER = r"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║      ██╗██╗      █████╗ ██╗    ██╗    ██╗   ██╗███████╗         ║
║      ██║██║     ██╔══██╗██║    ██║    ██║   ██║██╔════╝         ║
║      ██║██║     ███████║██║ █╗ ██║    ██║   ██║███████╗         ║
║ ██   ██║██║     ██╔══██║██║███╗██║    ╚██╗ ██╔╝╚════██║         ║
║ ╚█████╔╝███████╗██║  ██║╚███╔███╔╝     ╚████╔╝ ███████║         ║
║  ╚════╝ ╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝      ╚═══╝  ╚══════╝         ║
║                                                                  ║
║  Justice Legal Analysis Workbench — Agent Platform v5.0          ║
║  Nike Inc. (CIK 0000320187) | FY2019–Q1 CY2026                  ║
║  36 Deliverables | 23 Anomalies | 5 Compounding Patterns         ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""


def timestamp():
    return datetime.now().strftime("%H:%M:%S")


def log(phase, msg, level="INFO"):
    colors = {
        "INFO": "\033[37m", "OK": "\033[32m", "WARN": "\033[33m",
        "ERROR": "\033[31m", "GATE": "\033[35m", "PHASE": "\033[36m",
    }
    reset = "\033[0m"
    c = colors.get(level, colors["INFO"])
    print(f"  {c}[{timestamp()}] [{phase}] {msg}{reset}")


def check_prerequisites():
    """Validate that all prerequisites are met before running."""
    issues = []

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        issues.append("ANTHROPIC_API_KEY not set in .env")

    # Check data directories
    raw_dir = DATA_DIR / "raw-edgar"
    deliv_dir = DATA_DIR / "deliverables"

    if not raw_dir.exists():
        issues.append(f"Missing: {raw_dir} (copy your EDGAR downloads here)")
    if not deliv_dir.exists():
        issues.append(f"Missing: {deliv_dir} (copy your 36 DOCX reports here)")

    # Check for actual data
    raw_files = list(raw_dir.rglob("*")) if raw_dir.exists() else []
    deliverable_files = list(deliv_dir.rglob("*.docx")) if deliv_dir.exists() else []

    if len(raw_files) < 5:
        issues.append(f"raw-edgar/ has only {len(raw_files)} files (expected hundreds of EDGAR filings)")
    if len(deliverable_files) < 20:
        issues.append(f"deliverables/ has only {len(deliverable_files)} DOCX files (expected 24+)")

    # Check Proton Bridge (non-blocking — only needed for Phase 4)
    proton_configured = bool(os.environ.get("PROTON_EMAIL") and os.environ.get("PROTON_PASSWORD"))

    return issues, {
        "api_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "agent_sdk": AGENT_SDK_AVAILABLE,
        "raw_edgar_files": len(raw_files),
        "deliverable_files": len(deliverable_files),
        "proton_configured": proton_configured,
        "data_dir": str(DATA_DIR),
    }


# ═══════════════════════════════════════════════
# DIRECT MODULE EXECUTION (Agent SDK not required)
# ═══════════════════════════════════════════════

def run_direct_ingest():
    """Phase 1: Direct Python module execution — no Agent SDK needed."""
    log("INGEST", "Starting EDGAR corpus ingestion (direct execution)...", "PHASE")
    from src.agents.edgar_ingest import run_full_ingestion
    summary = run_full_ingestion()
    log("INGEST", f"Phase 1 complete: {json.dumps(summary.get('phases', {}), default=str)[:300]}", "OK")
    return summary


def run_direct_extract():
    """Phase 1.5: Extract anomalies from parsed deliverable DOCX trio bundles."""
    log("EXTRACT", "Starting deliverable anomaly extraction (direct execution)...", "PHASE")
    from src.agents.deliverable_extractor import run_deliverable_extraction
    summary = run_deliverable_extraction()
    log("EXTRACT", f"Phase 1.5 complete: {summary.get('unique_anomalies', 0)} anomalies, "
         f"{summary.get('compounding_patterns', 0)} patterns", "OK")
    return summary


def run_direct_crossref():
    """Phase 2: Direct Python module execution."""
    log("XREF", "Starting cross-reference analysis (direct execution)...", "PHASE")
    from src.agents.cross_reference import run_cross_reference
    summary = run_cross_reference()
    log("XREF", f"Phase 2 complete: {summary.get('total_anomalies', 0)} anomalies, "
         f"{summary.get('total_patterns', 0)} patterns", "OK")
    return summary


def run_direct_visualize(charts=None, formats=None):
    """Phase 2.5: Generate forensic visualizations (direct execution)."""
    log("VIZ", "Starting visualization generation (direct execution)...", "PHASE")
    from src.agents.visualization_agent import run_visualization
    results = run_visualization(charts=charts, formats=formats)
    static_count = len(results.get("static_charts", {}))
    dashboard = "✓" if results.get("dashboard") else "✗"
    deck = "✓" if results.get("deck") else "✗"
    log("VIZ", f"Phase 2.5 complete: {static_count} charts, dashboard={dashboard}, deck={deck}", "OK")
    return results


def run_direct_report(report_type: str = "all"):
    """Phase 3: Direct Python module execution."""
    log("REPORT", f"Starting report generation ({report_type}, direct execution)...", "PHASE")
    from src.agents.report_generator import generate_report, generate_master_report, \
        generate_sec_bundle, generate_doj_referral, generate_legislative_brief

    if report_type == "all":
        types = ["master", "sec", "doj", "legislative"]
    else:
        types = [report_type]

    outputs = []
    for rt in types:
        log("REPORT", f"Generating: {rt}...", "PHASE")
        output_path = generate_report(rt)
        log("REPORT", f"  → {output_path}", "OK")
        outputs.append(str(output_path))

    log("REPORT", f"Phase 3 complete: {len(outputs)} reports generated", "OK")
    return outputs


def run_direct_submit(target: str = "sec"):
    """Phase 4: Direct Python module execution."""
    log("SUBMIT", f"Starting submission workflow ({target}, direct execution)...", "PHASE")
    log("SUBMIT", "⚠ HUMAN APPROVAL REQUIRED FOR EVERY SEND ACTION ⚠", "GATE")
    from src.agents.submission_manager import draft_submission, review_draft, send_draft

    draft = draft_submission(target)
    if "error" in draft:
        log("SUBMIT", f"Draft creation failed: {draft['error']}", "ERROR")
        return

    draft_id = draft["draft_id"]
    review_draft(draft_id)

    confirm = input("\n  Send this submission? Type 'APPROVE' to send, or anything else to cancel: ").strip()
    if confirm == "APPROVE":
        send_draft(draft_id)
    else:
        log("SUBMIT", "Submission cancelled by user.", "GATE")

    log("SUBMIT", "Phase 4 finished.", "OK")


# ═══════════════════════════════════════════════
# AGENT SDK EXECUTION (requires claude-agent-sdk)
# ═══════════════════════════════════════════════

async def run_agent_phase(phase_name: str, prompt: str, permission_mode: str = "acceptEdits"):
    """Generic Agent SDK phase runner."""
    log(phase_name, f"Starting via Agent SDK...", "PHASE")

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        model="claude-sonnet-4-20250514",
        cwd=str(PROJECT_ROOT),
        setting_sources=["project"],
        permission_mode=permission_mode,
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            text = str(message.content)
            if len(text) > 300:
                log(phase_name, text[:300] + "...")
            else:
                log(phase_name, text)
        elif isinstance(message, ResultMessage):
            log(phase_name, f"Complete: {message.result}", "OK")

    log(phase_name, "Finished.", "OK")


async def run_agent_ingest():
    """Phase 1 via Agent SDK."""
    prompt = f"""Execute Phase 1: INGEST.

Your working directory is {PROJECT_ROOT}.
Data directory is {DATA_DIR}.

Step 1: Scan {DATA_DIR}/raw-edgar/ and inventory all files by type (PDF, XLS, XLSX, XML, HTML).
Step 2: Scan {DATA_DIR}/deliverables/ and inventory all DOCX files.
Step 3: For each fiscal year directory in raw-edgar/filings/, run the appropriate parser:
   - XML files → src/ingestion/form4_parser.py (with business-day timeliness)
   - PDF files → src/ingestion/pdf_parser.py (section extraction + forensic keywords)
   - XLS/XLSX files → src/ingestion/xls_parser.py (structured data extraction)
   - RSS/XML index → src/ingestion/rss_parser.py (filing inventory)
Step 4: Parse all DOCX deliverables using src/ingestion/docx_parser.py
Step 5: Output all structured JSON to {DATA_DIR}/parsed/ organized by fiscal year.
Step 6: Generate an ingestion summary report with file counts, parse success/failure, and any anomalies detected during parsing.

Use Bash to run the Python parsers. Use Read/Glob to scan directories.
Report progress after each fiscal year is processed."""

    await run_agent_phase("INGEST", prompt)


async def run_agent_crossref():
    """Phase 2 via Agent SDK."""
    prompt = f"""Execute Phase 2: CROSS-REFERENCE.

Working directory: {PROJECT_ROOT}
Parsed data: {DATA_DIR}/parsed/
Anomaly output: {DATA_DIR}/anomalies/

Run the 5 cross-reference analyses defined in src/agents/cross_reference.py:

1. FORM 4 TIMELINESS AUDIT: For every parsed Form 4, verify the timeliness calculation.
   Flag any filing >2 business days. Track Rule 16a-13 exemption usage.
   Known late filers: Travis Knight (Jan 2026), Sprunk (gifts deferred to Form 5),
   Friend (1 day late FY2021), Nielsen (late FY2024).

2. EXHIBIT INDEX COMPARISON: Compare 10-K exhibit indices FY2019→FY2025.
   Flag: Exhibit 19 addition (FY2024), exhibit number reuse, missing separation agreements.

3. INSIDER SELLING PATTERN: Map Parker's quarterly cadence across all years.
   Calculate cumulative by fiscal year. Identify plan adoption dates from Item 408(a).
   Track the FY2025 buy/sell divergence ($6.2M buys vs $57.5M Parker sells).

4. 13D STALENESS: Track Swoosh share count across all proxy beneficial ownership tables.
   Map distribution dates against 13D amendment deadlines (2-day rule post-Feb 2024).

5. KEYWORD DENSITY: Scan all parsed filings for forensic terms: "restatement",
   "material weakness", "blackout", "pre-clearance", "hardship exception",
   "related party", "dual-class", "controlling shareholder".

For each analysis, create anomaly records in {DATA_DIR}/anomalies/ with:
- Exact accession numbers
- Exact dates (YYYY-MM-DD)
- Severity rating (STRUCTURAL / HIGH / MEDIUM / LOW)
- Compounding year list
- Regulatory relevance scores

Link anomalies into the 5 compounding patterns identified in the micro-forensic audit.
Save the complete anomaly database as {DATA_DIR}/anomalies/anomaly_database.json."""

    await run_agent_phase("XREF", prompt)


async def run_agent_report(report_type: str = "all"):
    """Phase 3 via Agent SDK."""
    # Attempt to embed charts from Phase 2.5 into reports
    viz_manifest = DATA_DIR / "visualizations" / "visualization_manifest.json"
    chart_note = ""
    if viz_manifest.exists():
        chart_note = (
            f"\n\nVisualization manifest available at {viz_manifest}. "
            f"Static charts are in {DATA_DIR / 'visualizations' / 'charts'}/ — "
            f"embed them into reports using src/visualization/docx_embedder.py."
        )

    report_prompts = {
        "master": f"""Generate the MASTER CROSS-ANALYSIS DOCUMENT (FY2019–FY2025).
This is the capstone deliverable — the single document that synthesizes ALL 36 existing
reports, ALL anomalies in the database, and ALL 5 compounding patterns.

Structure:
I. Executive Summary (2 pages max)
II. Seven-Year Investigation Arc (narrative from Dec 2019 blackout trade to Mar 2026)
III. Year-by-Year Findings Catalog (FY2019-FY2025, Q1 CY2026)
IV. Compounding Patterns (5 patterns with year-by-year evidence)
V. Micro-Forensic Anomaly Index (all 23+ items, machine-readable)
VI. Regulatory Recommendation Matrix (SEC, DOJ, PCAOB, ISS, Congressional)
VII. Evidence Appendix (accession numbers, filing dates, transaction details)

Every finding must cite exact accession numbers. Use the anomaly database.
Output as DOCX to {DATA_DIR}/reports/JLAW_Master_Cross_Analysis.docx""",

        "sec": f"""Generate the SEC DIVISION OF ENFORCEMENT SUBMISSION BUNDLE.
TCR-formatted cover letter + evidence organized by violation type.
Include: Swoosh 13D deficiency (Rule 13d-2 violation), Parker pre-clearance self-approval,
Travis Knight §16(a) late filing, 14-year CORRESP gap, Exhibit 19 loophole.
Output to {DATA_DIR}/reports/JLAW_SEC_Enforcement_Bundle_FINAL.docx""",

        "doj": f"""Generate the DOJ FRAUD SECTION CRIMINAL REFERRAL PACKAGE.
Cover letter + securities fraud pattern summary + $565M insider sales analysis.
Reference the pending class action (D. Or. 3:24-cv-00974-AN) and its 19 confidential witnesses.
Output to {DATA_DIR}/reports/JLAW_DOJ_Criminal_Referral_FINAL.docx""",

        "legislative": f"""Generate the CONGRESSIONAL BRIEFING PACKAGE.
One-page executive summary + dual-class governance case study + regulatory gap analysis.
Target: Senate Banking Committee and House Financial Services Committee.
Output to {DATA_DIR}/reports/JLAW_Legislative_Briefing_FINAL.docx""",
    }

    types_to_generate = ["master", "sec", "doj", "legislative"] if report_type == "all" else [report_type]

    for rt in types_to_generate:
        prompt_template = report_prompts.get(rt)
        if not prompt_template:
            log("REPORT", f"Unknown report type: {rt}", "ERROR")
            continue

        prompt = f"""Execute Phase 3: REPORT GENERATION — {rt.upper()}.

Working directory: {PROJECT_ROOT}
Anomaly database: {DATA_DIR}/anomalies/anomaly_database.json
Parsed data: {DATA_DIR}/parsed/
Existing deliverables: {DATA_DIR}/deliverables/
Output directory: {DATA_DIR}/reports/

{prompt_template}

Use python-docx to create a professionally formatted DOCX with:
- Proper headers/footers with "PRIVILEGED & CONFIDENTIAL" markings
- Evidence tables with accession numbers
- Section numbering
- Page breaks between major sections

Read the anomaly database first, then cross-reference with parsed filing data."""

        await run_agent_phase("REPORT", prompt)


async def run_agent_submit(target: str = "sec"):
    """Phase 4 via Agent SDK — REQUIRES human approval."""
    log("SUBMIT", "⚠ HUMAN APPROVAL REQUIRED FOR EVERY SEND ACTION ⚠", "GATE")

    prompt = f"""Execute Phase 4: SUBMISSION — {target.upper()}.

Working directory: {PROJECT_ROOT}
Reports directory: {DATA_DIR}/reports/
Submissions directory: {DATA_DIR}/submissions/

Step 1: Read the generated report(s) from {DATA_DIR}/reports/
Step 2: Draft the submission email using src/agents/submission_manager.py logic:
   - Compose subject line and body text appropriate for the target agency
   - List all report attachments
   - Save draft JSON to {DATA_DIR}/submissions/
Step 3: PRESENT THE DRAFT FOR HUMAN REVIEW
   - Print the COMPLETE draft (recipient, subject, body, attachments)
   - Print the file paths of all attachments
   - Ask explicitly: "Do you approve sending this submission? (yes/no)"
Step 4: WAIT FOR HUMAN INPUT — do NOT proceed without explicit "yes"
Step 5: If approved, send via Proton Bridge SMTP using src/submission/proton_client.py
Step 6: Log the submission with timestamp and confirmation

Target: {target}
Available targets: sec_enforcement, sec_whistleblower, doj_fraud, iss_governance

CRITICAL: You must STOP and WAIT for human input at Step 4. Do not auto-approve."""

    await run_agent_phase("SUBMIT", prompt, permission_mode="default")


async def run_agent_interactive():
    """Interactive mode — direct conversation with the orchestrator."""
    log("INTERACTIVE", "Launching interactive mode...", "PHASE")
    log("INTERACTIVE", "Type your commands. The agent has full access to the investigation data.", "INFO")
    log("INTERACTIVE", "Type 'exit' or Ctrl+C to quit.\n", "INFO")

    while True:
        try:
            user_input = input("\n\033[36m[YOU] >\033[0m ")
            if user_input.strip().lower() in ("exit", "quit", "q"):
                break
            if not user_input.strip():
                continue

            options = ClaudeAgentOptions(
                allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
                model="claude-sonnet-4-20250514",
                cwd=str(PROJECT_ROOT),
                setting_sources=["project"],
                permission_mode="default",
            )

            async for message in query(prompt=user_input, options=options):
                if isinstance(message, AssistantMessage):
                    print(f"\n\033[37m[JLAW]\033[0m {message.content}")
                elif isinstance(message, ResultMessage):
                    print(f"\n\033[32m[RESULT]\033[0m {message.result}")

        except KeyboardInterrupt:
            print("\n")
            break
        except Exception as e:
            log("INTERACTIVE", f"Error: {e}", "ERROR")

    log("INTERACTIVE", "Session ended.", "OK")


# ═══════════════════════════════════════════════
# PIPELINE ORCHESTRATION
# ═══════════════════════════════════════════════

def run_pipeline_direct():
    """Execute all four phases using direct module execution."""
    log("PIPELINE", "Starting full pipeline (direct execution)...", "PHASE")
    start_time = time.time()

    # Phase 1
    log("PIPELINE", "═══ PHASE 1/6: INGEST ═══", "PHASE")
    run_direct_ingest()

    # Phase 1.5
    log("PIPELINE", "═══ PHASE 1.5/6: DELIVERABLE EXTRACTION ═══", "PHASE")
    run_direct_extract()

    # Phase 2
    log("PIPELINE", "═══ PHASE 2/6: CROSS-REFERENCE ═══", "PHASE")
    run_direct_crossref()

    # Phase 2.5
    log("PIPELINE", "═══ PHASE 2.5/6: VISUALIZATION ═══", "PHASE")
    run_direct_visualize()

    # Phase 3
    log("PIPELINE", "═══ PHASE 3/6: REPORT GENERATION ═══", "PHASE")
    run_direct_report("all")

    # Human checkpoint
    print("\n" + "=" * 60)
    print(f"  PIPELINE CHECKPOINT: Phases 1-3 complete.")
    print(f"  Reports generated in: {DATA_DIR / 'reports'}")
    print(f"  Visualizations in:    {DATA_DIR / 'visualizations'}")
    print(f"  Review the reports before proceeding to submission.")
    print("=" * 60)

    proceed = input("\n  Proceed to Phase 4 (SUBMISSION)? [yes/no]: ").strip().lower()
    if proceed != "yes":
        log("PIPELINE", "Pipeline paused at submission gate. Run 'python run.py submit' when ready.", "GATE")
        return

    # Phase 4
    log("PIPELINE", "═══ PHASE 4/5: SUBMISSION ═══", "PHASE")
    run_direct_submit("sec")

    elapsed = time.time() - start_time
    log("PIPELINE", f"Full pipeline complete in {elapsed / 60:.1f} minutes.", "OK")


async def run_pipeline_agent():
    """Execute all four phases using Agent SDK."""
    log("PIPELINE", "Starting full pipeline (Agent SDK)...", "PHASE")
    start_time = time.time()

    log("PIPELINE", "═══ PHASE 1/6: INGEST ═══", "PHASE")
    await run_agent_ingest()

    # Phase 1.5 — always direct (local extraction)
    log("PIPELINE", "═══ PHASE 1.5/6: DELIVERABLE EXTRACTION ═══", "PHASE")
    run_direct_extract()

    log("PIPELINE", "═══ PHASE 2/6: CROSS-REFERENCE ═══", "PHASE")
    await run_agent_crossref()

    # Phase 2.5 — always runs direct (chart generation is local)
    log("PIPELINE", "═══ PHASE 2.5/6: VISUALIZATION ═══", "PHASE")
    run_direct_visualize()

    log("PIPELINE", "═══ PHASE 3/6: REPORT GENERATION ═══", "PHASE")
    await run_agent_report("all")

    print("\n" + "=" * 60)
    print(f"  PIPELINE CHECKPOINT: Phases 1-3 complete.")
    print(f"  Reports generated in: {DATA_DIR / 'reports'}")
    print(f"  Visualizations in:    {DATA_DIR / 'visualizations'}")
    print(f"  Review the reports before proceeding to submission.")
    print("=" * 60)

    proceed = input("\n  Proceed to Phase 4 (SUBMISSION)? [yes/no]: ").strip().lower()
    if proceed != "yes":
        log("PIPELINE", "Pipeline paused at submission gate. Run 'python run.py submit' when ready.", "GATE")
        return

    log("PIPELINE", "═══ PHASE 4/5: SUBMISSION ═══", "PHASE")
    await run_agent_submit("sec_enforcement")

    elapsed = time.time() - start_time
    log("PIPELINE", f"Full pipeline complete in {elapsed / 60:.1f} minutes.", "OK")


# ═══════════════════════════════════════════════
# MAIN CLI
# ═══════════════════════════════════════════════

def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        description="JLAW Agent Platform v5.0 — Nike Forensic Intelligence Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status       Check data directory status and prerequisites
  pipeline     Run all phases in sequence (INGEST → EXTRACT → CROSSREF → VISUALIZE → REPORT → SUBMIT)
  ingest       Phase 1: Parse all raw EDGAR data into structured JSON
  extract      Phase 1.5: Extract anomalies from deliverable trio bundles
  crossref     Phase 2: Cross-reference analysis and anomaly detection
  visualize    Phase 2.5: Generate charts, dashboard, and presentation deck
  report       Phase 3: Generate submission-ready reports
  submit       Phase 4: Draft and send regulatory submissions
  interactive  Open an interactive session with the JLAW agent

Execution Modes:
  --mode agent    Use Claude Agent SDK (default if installed)
  --mode direct   Use direct Python module execution (no API key needed for Phases 1-3)
        """,
    )
    parser.add_argument(
        "command", nargs="?", default="status",
        choices=["pipeline", "ingest", "extract", "crossref", "visualize", "report", "submit", "interactive", "status"],
    )
    parser.add_argument(
        "--report-type", default="all",
        choices=["all", "master", "sec", "doj", "legislative"],
        help="Report type for 'report' command",
    )
    parser.add_argument(
        "--target", default="sec",
        choices=["sec", "sec_whistleblower", "doj", "iss"],
        help="Submission target for 'submit' command",
    )
    parser.add_argument(
        "--mode", default="auto",
        choices=["auto", "agent", "direct"],
        help="Execution mode: 'agent' (Claude Agent SDK), 'direct' (local Python), 'auto' (agent if available)",
    )

    args = parser.parse_args()

    # Resolve execution mode
    use_agent = False
    if args.mode == "agent":
        if not AGENT_SDK_AVAILABLE:
            print("  ✗ Claude Agent SDK not installed. Run: pip install claude-agent-sdk")
            return
        use_agent = True
    elif args.mode == "direct":
        use_agent = False
    else:  # auto
        use_agent = AGENT_SDK_AVAILABLE

    # Status check
    issues, status = check_prerequisites()
    print(f"  Data directory:    {status['data_dir']}")
    print(f"  API key:           {'✓ Set' if status['api_key'] else '✗ MISSING'}")
    print(f"  Agent SDK:         {'✓ Installed' if status['agent_sdk'] else '○ Not installed (using direct mode)'}")
    print(f"  Raw EDGAR files:   {status['raw_edgar_files']}")
    print(f"  DOCX deliverables: {status['deliverable_files']}")
    print(f"  Proton Bridge:     {'✓ Configured' if status['proton_configured'] else '○ Not configured (needed for Phase 4)'}")
    print(f"  Execution mode:    {'Agent SDK' if use_agent else 'Direct (local Python)'}")
    print()

    if args.command == "status":
        if issues:
            print("  ⚠ Issues found:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  ✓ All prerequisites met. Ready to run.")
        return

    # For agent mode, API key is required
    if use_agent and not status["api_key"]:
        print("  ✗ Cannot proceed in agent mode without ANTHROPIC_API_KEY.")
        print("    Set it in .env, or use --mode direct for local execution.")
        return

    # Route commands
    if args.command == "pipeline":
        if issues and any("MISSING" in i.upper() for i in issues):
            print("  ⚠ Prerequisites not fully met. Continue anyway? [yes/no]: ", end="")
            if input().strip().lower() != "yes":
                return
        if use_agent:
            asyncio.run(run_pipeline_agent())
        else:
            run_pipeline_direct()

    elif args.command == "ingest":
        if use_agent:
            asyncio.run(run_agent_ingest())
        else:
            run_direct_ingest()

    elif args.command == "extract":
        run_direct_extract()

    elif args.command == "crossref":
        if use_agent:
            asyncio.run(run_agent_crossref())
        else:
            run_direct_crossref()

    elif args.command == "visualize":
        # Phase 2.5 always runs direct (local chart generation)
        run_direct_visualize()

    elif args.command == "report":
        if use_agent:
            asyncio.run(run_agent_report(args.report_type))
        else:
            run_direct_report(args.report_type)

    elif args.command == "submit":
        if use_agent:
            asyncio.run(run_agent_submit(args.target))
        else:
            run_direct_submit(args.target)

    elif args.command == "interactive":
        if use_agent:
            asyncio.run(run_agent_interactive())
        else:
            print("  Interactive mode requires Claude Agent SDK.")
            print("  Install: pip install claude-agent-sdk")
            print("  Or run individual phases with: python run.py ingest --mode direct")


if __name__ == "__main__":
    main()
