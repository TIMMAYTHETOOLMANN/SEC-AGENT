#!/usr/bin/env python3
"""
JLAW Agent Platform v5.0 — Primary CLI Entry Point

Full pipeline: python run.py pipeline
Individual phases: python run.py ingest | crossref | report | submit
Interactive mode: python run.py interactive

Local machine deployment. CLI-first interface.
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

# Load environment
load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path(__file__).parent / "config" / ".env.template")

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", PROJECT_ROOT / "data"))
LOG_DIR = Path(os.environ.get("JLAW_LOG_DIR", PROJECT_ROOT / "logs"))

# ═══════════════════════════════════════════════
# BANNER
# ═══════════════════════════════════════════════

BANNER = """
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
    colors = {"INFO": "\033[37m", "OK": "\033[32m", "WARN": "\033[33m",
              "ERROR": "\033[31m", "GATE": "\033[35m", "PHASE": "\033[36m"}
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
    if not (DATA_DIR / "raw-edgar").exists():
        issues.append(f"Missing: {DATA_DIR}/raw-edgar/ (copy your EDGAR downloads here)")
    if not (DATA_DIR / "deliverables").exists():
        issues.append(f"Missing: {DATA_DIR}/deliverables/ (copy your 36 DOCX reports here)")

    # Check for actual data
    raw_files = list((DATA_DIR / "raw-edgar").rglob("*")) if (DATA_DIR / "raw-edgar").exists() else []
    deliverable_files = list((DATA_DIR / "deliverables").rglob("*.docx")) if (DATA_DIR / "deliverables").exists() else []

    if len(raw_files) < 5:
        issues.append(f"raw-edgar/ has only {len(raw_files)} files (expected hundreds of EDGAR filings)")
    if len(deliverable_files) < 30:
        issues.append(f"deliverables/ has only {len(deliverable_files)} DOCX files (expected 36)")

    # Check Proton Bridge (non-blocking — only needed for Phase 4)
    proton_configured = os.environ.get("PROTON_EMAIL") and os.environ.get("PROTON_PASSWORD")

    return issues, {
        "api_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "raw_edgar_files": len(raw_files),
        "deliverable_files": len(deliverable_files),
        "proton_configured": proton_configured,
        "data_dir": str(DATA_DIR),
    }


# ═══════════════════════════════════════════════
# PHASE RUNNERS
# ═══════════════════════════════════════════════

async def run_phase_ingest():
    """Phase 1: Ingest all raw EDGAR data and existing deliverables."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

    log("INGEST", "Starting EDGAR corpus ingestion...", "PHASE")

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

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        model="claude-sonnet-4-20250514",
        cwd=str(PROJECT_ROOT),
        setting_sources=["project"],
        permission_mode="acceptEdits",
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            # Print assistant reasoning (truncated for readability)
            text = str(message.content)
            if len(text) > 300:
                log("INGEST", text[:300] + "...")
            else:
                log("INGEST", text)
        elif isinstance(message, ResultMessage):
            log("INGEST", f"Phase 1 complete: {message.result}", "OK")

    log("INGEST", "Phase 1 finished.", "OK")


async def run_phase_crossref():
    """Phase 2: Cross-reference all parsed data and build anomaly database."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

    log("XREF", "Starting cross-reference analysis...", "PHASE")

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

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        model="claude-sonnet-4-20250514",
        cwd=str(PROJECT_ROOT),
        setting_sources=["project"],
        permission_mode="acceptEdits",
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            text = str(message.content)
            if len(text) > 300:
                log("XREF", text[:300] + "...")
            else:
                log("XREF", text)
        elif isinstance(message, ResultMessage):
            log("XREF", f"Phase 2 complete: {message.result}", "OK")

    log("XREF", "Phase 2 finished.", "OK")


async def run_phase_report(report_type: str = "all"):
    """Phase 3: Generate submission-ready reports."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

    log("REPORT", f"Starting report generation ({report_type})...", "PHASE")

    report_prompts = {
        "master": """Generate the MASTER CROSS-ANALYSIS DOCUMENT (FY2019–FY2025).
This is the capstone deliverable — the single document that synthesizes ALL 36 existing
reports, ALL anomalies in the database, and ALL 5 compounding patterns.

Structure:
I. Executive Summary (2 pages max)
II. Seven-Year Investigation Arc (narrative from Dec 2019 blackout trade to Mar 2026)
III. Year-by-Year Findings Catalog (FY2019, FY2020, FY2021, FY2022, FY2023, FY2024, FY2025, Q1 CY2026)
IV. Compounding Patterns (5 patterns with year-by-year evidence)
V. Micro-Forensic Anomaly Index (all 23+ items, machine-readable)
VI. Regulatory Recommendation Matrix (SEC, DOJ, PCAOB, ISS, Congressional)
VII. Evidence Appendix (accession numbers, filing dates, transaction details)

Every finding must cite exact accession numbers. Use the anomaly database.
Output as DOCX to {data_dir}/reports/JLAW_Master_Cross-Analysis_FY2019-FY2025.docx""",

        "sec": """Generate the SEC DIVISION OF ENFORCEMENT SUBMISSION BUNDLE.
TCR-formatted cover letter + evidence organized by violation type.
Include: Swoosh 13D deficiency (Rule 13d-2 violation), Parker pre-clearance self-approval,
Travis Knight §16(a) late filing, 14-year CORRESP gap, Exhibit 19 loophole.
Output to {data_dir}/reports/JLAW_SEC_Enforcement_Bundle_FINAL.docx""",

        "doj": """Generate the DOJ FRAUD SECTION CRIMINAL REFERRAL PACKAGE.
Cover letter + securities fraud pattern summary + $565M insider sales analysis.
Reference the pending class action (D. Or. 3:24-cv-00974-AN) and its 19 confidential witnesses.
Output to {data_dir}/reports/JLAW_DOJ_Criminal_Referral_FINAL.docx""",

        "legislative": """Generate the CONGRESSIONAL BRIEFING PACKAGE.
One-page executive summary + dual-class governance case study + regulatory gap analysis.
Target: Senate Banking Committee and House Financial Services Committee.
Output to {data_dir}/reports/JLAW_Legislative_Briefing_FINAL.docx""",
    }

    if report_type == "all":
        types_to_generate = ["master", "sec", "doj", "legislative"]
    else:
        types_to_generate = [report_type]

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

{prompt_template.format(data_dir=DATA_DIR)}

Use python-docx to create a professionally formatted DOCX with:
- Proper headers/footers with "PRIVILEGED & CONFIDENTIAL" markings
- Evidence tables with accession numbers
- Section numbering
- Page breaks between major sections

Read the anomaly database first, then cross-reference with parsed filing data."""

        options = ClaudeAgentOptions(
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            model="claude-sonnet-4-20250514",
            cwd=str(PROJECT_ROOT),
            setting_sources=["project"],
            permission_mode="acceptEdits",
        )

        log("REPORT", f"Generating: {rt}", "PHASE")
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                text = str(message.content)
                if len(text) > 300:
                    log("REPORT", text[:300] + "...")
                else:
                    log("REPORT", text)
            elif isinstance(message, ResultMessage):
                log("REPORT", f"{rt} report complete: {message.result}", "OK")

    log("REPORT", "Phase 3 finished.", "OK")


async def run_phase_submit(target: str = "sec"):
    """Phase 4: Draft and submit regulatory communications."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

    log("SUBMIT", f"Starting submission workflow ({target})...", "PHASE")
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

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        model="claude-sonnet-4-20250514",
        cwd=str(PROJECT_ROOT),
        setting_sources=["project"],
        # Use default permission mode — requires human approval for destructive actions
        permission_mode="default",
    )

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            text = str(message.content)
            log("SUBMIT", text)
        elif isinstance(message, ResultMessage):
            log("SUBMIT", f"Submission workflow complete: {message.result}", "OK")

    log("SUBMIT", "Phase 4 finished.", "OK")


async def run_interactive():
    """Interactive mode — direct conversation with the orchestrator."""
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

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
# FULL PIPELINE
# ═══════════════════════════════════════════════

async def run_full_pipeline():
    """Execute all four phases in sequence with human gates."""
    log("PIPELINE", "Starting full pipeline run...", "PHASE")
    start_time = time.time()

    # Phase 1: Ingest
    log("PIPELINE", "═══ PHASE 1/4: INGEST ═══", "PHASE")
    await run_phase_ingest()

    # Phase 2: Cross-reference
    log("PIPELINE", "═══ PHASE 2/4: CROSS-REFERENCE ═══", "PHASE")
    await run_phase_crossref()

    # Phase 3: Reports (all four types)
    log("PIPELINE", "═══ PHASE 3/4: REPORT GENERATION ═══", "PHASE")
    await run_phase_report("all")

    # Human checkpoint before submission
    print("\n" + "="*60)
    print("  PIPELINE CHECKPOINT: Phases 1-3 complete.")
    print("  Reports generated in: {}/reports/".format(DATA_DIR))
    print("  Review the reports before proceeding to submission.")
    print("="*60)

    proceed = input("\n  Proceed to Phase 4 (SUBMISSION)? [yes/no]: ").strip().lower()
    if proceed != "yes":
        log("PIPELINE", "Pipeline paused at submission gate. Run 'python run.py submit' when ready.", "GATE")
        return

    # Phase 4: Submit (SEC first — most critical)
    log("PIPELINE", "═══ PHASE 4/4: SUBMISSION ═══", "PHASE")
    await run_phase_submit("sec_enforcement")

    elapsed = time.time() - start_time
    log("PIPELINE", f"Full pipeline complete in {elapsed/60:.1f} minutes.", "OK")


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
  pipeline     Run all 4 phases in sequence (INGEST → CROSSREF → REPORT → SUBMIT)
  ingest       Phase 1: Parse all raw EDGAR data into structured JSON
  crossref     Phase 2: Cross-reference analysis and anomaly detection
  report       Phase 3: Generate submission-ready reports
  submit       Phase 4: Draft and send regulatory submissions
  interactive  Open an interactive session with the JLAW agent
  status       Check data directory status and prerequisites
        """
    )
    parser.add_argument("command", nargs="?", default="status",
                       choices=["pipeline", "ingest", "crossref", "report", "submit",
                               "interactive", "status"])
    parser.add_argument("--report-type", default="all",
                       choices=["all", "master", "sec", "doj", "legislative"],
                       help="Report type for 'report' command")
    parser.add_argument("--target", default="sec_enforcement",
                       choices=["sec_enforcement", "sec_whistleblower", "doj_fraud",
                               "iss_governance"],
                       help="Submission target for 'submit' command")

    args = parser.parse_args()

    # Status check (always runs first)
    issues, status = check_prerequisites()
    print(f"  Data directory:    {status['data_dir']}")
    print(f"  API key:           {'✓ Set' if status['api_key'] else '✗ MISSING'}")
    print(f"  Raw EDGAR files:   {status['raw_edgar_files']}")
    print(f"  DOCX deliverables: {status['deliverable_files']}")
    print(f"  Proton Bridge:     {'✓ Configured' if status['proton_configured'] else '○ Not configured (needed for Phase 4)'}")
    print()

    if args.command == "status":
        if issues:
            print("  ⚠ Issues found:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  ✓ All prerequisites met. Ready to run.")
        return

    # Check for blocking issues
    if not status["api_key"]:
        print("  ✗ Cannot proceed without ANTHROPIC_API_KEY. Set it in .env")
        return

    if args.command == "pipeline":
        if issues and any("MISSING" in i for i in issues):
            print("  ⚠ Prerequisites not fully met. Continue anyway? [yes/no]: ", end="")
            if input().strip().lower() != "yes":
                return
        asyncio.run(run_full_pipeline())
    elif args.command == "ingest":
        asyncio.run(run_phase_ingest())
    elif args.command == "crossref":
        asyncio.run(run_phase_crossref())
    elif args.command == "report":
        asyncio.run(run_phase_report(args.report_type))
    elif args.command == "submit":
        asyncio.run(run_phase_submit(args.target))
    elif args.command == "interactive":
        asyncio.run(run_interactive())


if __name__ == "__main__":
    main()
