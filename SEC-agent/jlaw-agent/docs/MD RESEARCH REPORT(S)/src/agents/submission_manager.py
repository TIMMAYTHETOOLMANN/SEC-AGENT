"""
JLAW Submission Manager Agent
Manages the full regulatory submission lifecycle with mandatory
human-in-the-loop gates at every send point.

Usage:
    python -m src.agents.submission_manager --draft sec
    python -m src.agents.submission_manager --review DRAFT-ID
    python -m src.agents.submission_manager --approve DRAFT-ID
    python -m src.agents.submission_manager --check-inbox
    python -m src.agents.submission_manager --status
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

from ..submission.proton_client import ProtonClient
from ..submission.draft_manager import DraftManager
from ..submission.response_handler import ResponseHandler


DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", "./data"))

SUBMISSION_TARGETS = {
    "sec": {
        "id": "sec_enforcement",
        "name": "SEC Division of Enforcement",
        "email": "enforcement@sec.gov",
    },
    "sec_whistleblower": {
        "id": "sec_whistleblower",
        "name": "SEC Office of the Whistleblower",
        "email": "whistleblower@sec.gov",
    },
    "doj": {
        "id": "doj_fraud",
        "name": "DOJ Fraud Section",
        "email": "fraud.section@usdoj.gov",
    },
    "iss": {
        "id": "iss_governance",
        "name": "ISS Governance Research",
        "email": "governance@issgovernance.com",
    },
    "senate": {
        "id": "senate_banking",
        "name": "Senate Banking Committee",
        "email": "banking@senate.gov",
    },
    "house": {
        "id": "house_financial",
        "name": "House Financial Services Committee",
        "email": "financialsvcs@mail.house.gov",
    },
}


def cmd_draft(target_key: str):
    """Create a draft submission."""
    target = SUBMISSION_TARGETS.get(target_key)
    if not target:
        print(f"Unknown target: {target_key}")
        print(f"Available: {', '.join(SUBMISSION_TARGETS.keys())}")
        return

    dm = DraftManager(DATA_DIR / "submissions")

    # Check for generated reports
    reports_dir = DATA_DIR / "reports"
    attachments = []
    if reports_dir.exists():
        for docx in sorted(reports_dir.glob("*.docx")):
            attachments.append(str(docx))

    subject = f"JLAW Forensic Intelligence Report — Nike Inc. (CIK 0000320187) — {target['name']}"
    body = (
        f"Dear {target['name']},\n\n"
        f"Please find attached the results of a seven-year forensic investigation "
        f"of Nike, Inc. (CIK 0000320187, NYSE: NKE) spanning fiscal years 2019 through 2025 "
        f"and supplemental Q1 CY2026 analysis.\n\n"
        f"This submission documents {len(attachments)} investigative deliverables covering "
        f"12 EDGAR filing categories per fiscal year, including:\n"
        f"- Exhibit 19 insider trading policy self-approval loophole (first filed FY2024)\n"
        f"- Swoosh LLC Schedule 13D: 9+ years without amendment (last: June 2016)\n"
        f"- $565M+ in Executive Chairman cumulative stock sales (FY2019-FY2025)\n"
        f"- Securities fraud class action (D.Or. 3:24-cv-00974-AN) — MTD pending\n"
        f"- 14-year SEC correspondence gap\n"
        f"- 23 discrete filing-level anomalies with 5 compounding patterns\n\n"
        f"We respectfully request review and are available for any follow-up inquiries.\n\n"
        f"Respectfully submitted,\n"
        f"JLAW Forensic Intelligence Platform v5.0\n"
    )

    draft = dm.create_draft(
        target_id=target["id"],
        target_name=target["name"],
        target_email=target["email"],
        subject=subject,
        body=body,
        attachment_paths=attachments,
    )

    print(f"\n{'='*60}")
    print(f"  DRAFT CREATED: {draft['draft_id']}")
    print(f"  Target: {target['name']} ({target['email']})")
    print(f"  Attachments: {len(attachments)}")
    print(f"  Status: {draft['status']}")
    print(f"\n  To review: python -m src.agents.submission_manager --review {draft['draft_id']}")
    print(f"  To approve: python -m src.agents.submission_manager --approve {draft['draft_id']}")
    print(f"{'='*60}\n")


def cmd_review(draft_id: str):
    """Display a draft for human review."""
    dm = DraftManager(DATA_DIR / "submissions")
    draft = dm.get_draft(draft_id)
    if not draft:
        print(f"Draft {draft_id} not found.")
        return

    print(f"\n{'='*60}")
    print(f"  DRAFT REVIEW — {draft['draft_id']}")
    print(f"{'='*60}")
    print(f"  To:      {draft['target_email']}")
    print(f"  Subject: {draft['subject']}")
    print(f"  Status:  {draft['status']}")
    print(f"  Created: {draft['created_at']}")
    print(f"\n  --- BODY ---")
    print(f"  {draft['body']}")
    print(f"\n  --- ATTACHMENTS ({len(draft['attachments'])}) ---")
    for att in draft["attachments"]:
        status = "✓" if att.get("exists") else "✗ MISSING"
        print(f"    {status} {att['name']} ({att.get('size_kb', 0)} KB)")
    print(f"\n  --- AUDIT TRAIL ---")
    for entry in draft.get("audit_trail", []):
        print(f"    [{entry['timestamp']}] {entry['action']}: {entry['details']}")
    print(f"{'='*60}\n")


def cmd_approve(draft_id: str):
    """Approve a draft and send it."""
    dm = DraftManager(DATA_DIR / "submissions")
    draft = dm.get_draft(draft_id)
    if not draft:
        print(f"Draft {draft_id} not found.")
        return

    if draft["status"] != "PENDING_REVIEW":
        print(f"Draft status is {draft['status']}, cannot approve.")
        return

    # Final confirmation
    print(f"\n  ⚠ CONFIRMATION REQUIRED ⚠")
    print(f"  You are about to SEND this submission to:")
    print(f"    {draft['target_name']} ({draft['target_email']})")
    print(f"    Subject: {draft['subject']}")
    print(f"    Attachments: {len(draft['attachments'])}")
    confirm = input("\n  Type 'SEND' to confirm, anything else to cancel: ")

    if confirm.strip() != "SEND":
        print("  Cancelled.")
        return

    # Approve
    dm.approve(draft_id)

    # Send
    client = ProtonClient()
    health = client.health_check()
    if not health.get("healthy"):
        print(f"  ✗ Proton Bridge not healthy: {health}")
        dm.mark_failed(draft_id, "Proton Bridge health check failed")
        return

    attachments = [Path(a["path"]) for a in draft["attachments"] if a.get("exists")]
    result = client.send_email(
        to=draft["target_email"],
        subject=draft["subject"],
        body=draft["body"],
        attachments=attachments,
    )

    if result["status"] == "SENT":
        dm.mark_sent(draft_id, result)
        print(f"\n  ✓ SENT to {draft['target_email']} at {result['sent_at']}")
    else:
        dm.mark_failed(draft_id, result.get("error", "Unknown error"))
        print(f"\n  ✗ SEND FAILED: {result.get('error')}")


def cmd_check_inbox():
    """Check for regulatory responses."""
    handler = ResponseHandler(DATA_DIR)
    print("\n  Checking inbox...")
    responses = handler.check_inbox(since_days=30)
    print(f"  → {len(responses)} messages found\n")

    for r in responses:
        if "error" in r:
            print(f"  ✗ Error: {r['error']}")
            continue
        priority = r.get("priority", "LOW")
        marker = "🔴" if priority == "CRITICAL" else "🟡" if priority == "HIGH" else "⚪"
        print(f"  {marker} [{r.get('classification', 'UNK')}] {r.get('subject', 'No subject')}")
        print(f"     From: {r.get('from', 'Unknown')} | Date: {r.get('date', '')}")

    # Show pending actions
    pending = handler.get_pending_actions()
    if pending:
        print(f"\n  ⚠ {len(pending)} responses require action")


def cmd_status():
    """Show overall submission status."""
    dm = DraftManager(DATA_DIR / "submissions")
    handler = ResponseHandler(DATA_DIR)

    drafts = dm.list_drafts()
    status_report = handler.generate_status_report()

    print(f"\n{'='*60}")
    print(f"  SUBMISSION STATUS REPORT")
    print(f"  Generated: {datetime.now().isoformat()}")
    print(f"{'='*60}")
    print(f"\n  Drafts: {len(drafts)}")
    for d in drafts:
        status_marker = {"SENT": "✓", "APPROVED": "→", "PENDING_REVIEW": "⏳",
                        "REJECTED": "✗", "SEND_FAILED": "✗"}.get(d["status"], "?")
        print(f"    {status_marker} [{d['status']}] {d['target']} — {d['subject'][:50]}")

    print(f"\n  Responses: {status_report['total_responses']}")
    for ctype, count in status_report.get("by_classification", {}).items():
        print(f"    {ctype}: {count}")
    print(f"  Pending actions: {status_report.get('pending_action', 0)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JLAW Submission Manager")
    parser.add_argument("--draft", type=str, help="Create draft (sec|doj|iss|senate|house)")
    parser.add_argument("--review", type=str, help="Review a draft by ID")
    parser.add_argument("--approve", type=str, help="Approve and send a draft")
    parser.add_argument("--check-inbox", action="store_true", help="Check for responses")
    parser.add_argument("--status", action="store_true", help="Show submission status")
    args = parser.parse_args()

    if args.draft:
        cmd_draft(args.draft)
    elif args.review:
        cmd_review(args.review)
    elif args.approve:
        cmd_approve(args.approve)
    elif args.check_inbox:
        cmd_check_inbox()
    elif args.status:
        cmd_status()
    else:
        parser.print_help()
