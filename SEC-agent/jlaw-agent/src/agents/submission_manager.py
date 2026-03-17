"""
JLAW Submission Manager Agent
Manages secure regulatory communications via Proton Bridge.
Drafts emails, presents for human review, sends after approval,
monitors inbox, and classifies responses.

CRITICAL: All send operations require explicit human approval.
No email is ever sent autonomously.

Usage:
    python -m src.agents.submission_manager --draft sec
    python -m src.agents.submission_manager --review DRAFT-20260315-120000-sec_enforcement
    python -m src.agents.submission_manager --send DRAFT-20260315-120000-sec_enforcement
    python -m src.agents.submission_manager --inbox 7
    python -m src.agents.submission_manager --log
"""

import argparse
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from src.submission.proton_client import ProtonBridgeClient
from src.submission.draft_manager import DraftManager
from src.submission.response_handler import ResponseHandler


# ═══════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", PROJECT_ROOT / "data"))
REPORTS_DIR = DATA_DIR / "reports"
SUBMISSION_DIR = DATA_DIR / "submissions"
LOG_DIR = Path(os.environ.get("JLAW_LOG_DIR", PROJECT_ROOT / "logs"))

# Submission targets
TARGETS = {
    "sec": {
        "target_id": "sec_enforcement",
        "name": "SEC Division of Enforcement",
        "email": "enforcement@sec.gov",
        "report_prefix": "SEC_Enforcement_Bundle",
        "subject_template": "TCR Submission — Nike, Inc. (CIK 0000320187) — Seven-Year Forensic Analysis",
    },
    "sec_whistleblower": {
        "target_id": "sec_whistleblower",
        "name": "SEC Office of the Whistleblower",
        "email": "whistleblower@sec.gov",
        "report_prefix": "SEC_Enforcement_Bundle",
        "subject_template": "Whistleblower Submission — Nike, Inc. (CIK 0000320187)",
    },
    "doj": {
        "target_id": "doj_fraud",
        "name": "DOJ Fraud Section",
        "email": "fraud.section@usdoj.gov",
        "report_prefix": "DOJ_Criminal_Referral",
        "subject_template": "Criminal Referral — Nike, Inc. — Securities Fraud Investigation",
    },
    "iss": {
        "target_id": "iss_governance",
        "name": "ISS Governance Research",
        "email": "governance@issgovernance.com",
        "report_prefix": "Legislative_Briefing",
        "subject_template": "Governance Engagement — Nike, Inc. — Dual-Class Structure Analysis",
    },
}


def find_latest_report(prefix: str) -> Optional[Path]:
    """Find the most recently generated report matching a prefix."""
    if not REPORTS_DIR.exists():
        return None
    matches = sorted(REPORTS_DIR.glob(f"{prefix}*.docx"), reverse=True)
    return matches[0] if matches else None


def draft_submission(target_key: str) -> Dict:
    """
    Create a draft submission for a regulatory target.
    Returns the draft metadata (NOT sent yet).
    """
    target = TARGETS.get(target_key)
    if not target:
        print(f"  ✗ Unknown target: {target_key}. Available: {', '.join(TARGETS.keys())}")
        return {"error": f"Unknown target: {target_key}"}

    # Find the latest relevant report
    report_path = find_latest_report(target["report_prefix"])
    attachments = []
    if report_path:
        attachments.append(str(report_path))
        print(f"  Found report: {report_path.name}")
    else:
        print(f"  ⚠ No report found matching '{target['report_prefix']}*'. "
              f"Run report_generator first.")

    # Build the email body
    body = build_submission_body(target_key)

    # Create draft via draft manager
    manager = DraftManager(SUBMISSION_DIR)
    draft = manager.create_draft(
        target_id=target["target_id"],
        target_name=target["name"],
        target_email=target["email"],
        subject=target["subject_template"],
        body=body,
        attachment_paths=attachments,
    )

    print(f"\n  ✓ Draft created: {draft['draft_id']}")
    print(f"  To: {draft['to']}")
    print(f"  Subject: {draft['subject']}")
    print(f"  Attachments: {len(draft.get('attachments', []))}")
    print(f"  Status: {draft['status']}")
    print(f"\n  ⚠ This draft has NOT been sent.")
    print(f"  Review with: --review {draft['draft_id']}")
    print(f"  Send with:   --send {draft['draft_id']}")

    return draft


def build_submission_body(target_key: str) -> str:
    """Build the email body text for a submission."""
    now = datetime.now().strftime("%B %d, %Y")

    if target_key == "sec":
        return (
            f"Date: {now}\n\n"
            f"To: SEC Division of Enforcement\n"
            f"Re: Tips, Complaints, and Referrals — Nike, Inc. (CIK 0000320187)\n\n"
            f"Dear Division of Enforcement,\n\n"
            f"Attached please find an evidence bundle documenting multiple potential "
            f"securities law violations by Nike, Inc. and certain of its officers and "
            f"directors, identified through a systematic seven-year forensic analysis "
            f"of SEC EDGAR filings spanning FY2019 through Q1 CY2026.\n\n"
            f"The enclosed bundle documents anomalies including:\n"
            f"  — Section 16(a) filing delinquencies (Form 4 timeliness violations)\n"
            f"  — Cumulative insider selling patterns exceeding $500 million\n"
            f"  — Schedule 13D amendment delinquency (9+ years stale)\n"
            f"  — Insider trading policy self-approval mechanisms (Exhibit 19)\n"
            f"  — Proxy statement disclosure inconsistencies\n\n"
            f"All findings are supported by exact EDGAR accession numbers, "
            f"transaction dates, and statutory references.\n\n"
            f"We are available to provide additional documentation or testimony "
            f"as requested.\n\n"
            f"Respectfully submitted."
        )
    elif target_key == "doj":
        return (
            f"Date: {now}\n\n"
            f"To: DOJ Fraud Section\n"
            f"Re: Criminal Referral — Nike, Inc. (CIK 0000320187)\n\n"
            f"Dear Fraud Section,\n\n"
            f"This letter constitutes a criminal referral regarding potential "
            f"securities fraud by officers and directors of Nike, Inc.\n\n"
            f"The enclosed package documents a seven-year pattern of insider "
            f"trading, disclosure failures, and governance circumvention.\n\n"
            f"Respectfully submitted."
        )
    else:
        return (
            f"Date: {now}\n\n"
            f"Please find attached the referenced submission materials "
            f"regarding Nike, Inc. (CIK 0000320187).\n\n"
            f"Respectfully submitted."
        )


def review_draft(draft_id: str) -> Dict:
    """Display a draft for human review."""
    manager = DraftManager(SUBMISSION_DIR)
    draft = manager.load_draft(draft_id)

    if not draft:
        print(f"  ✗ Draft not found: {draft_id}")
        return {"error": "Draft not found"}

    print(f"\n{'═'*60}")
    print(f"  SUBMISSION DRAFT — HUMAN REVIEW REQUIRED")
    print(f"{'═'*60}")
    print(f"  Draft ID:    {draft['draft_id']}")
    print(f"  Target:      {draft.get('target_name', 'N/A')}")
    print(f"  To:          {draft['to']}")
    print(f"  Subject:     {draft['subject']}")
    print(f"  Created:     {draft['created_at']}")
    print(f"  Status:      {draft['status']}")
    print(f"  Attachments: {len(draft.get('attachments', []))}")
    print(f"{'─'*60}")
    print(f"  BODY:")
    print(f"  {draft['body'][:600]}")
    if len(draft['body']) > 600:
        print(f"  ... [{len(draft['body']) - 600} more characters]")
    print(f"{'─'*60}")
    if draft.get("attachments"):
        print(f"  ATTACHMENTS:")
        for att in draft["attachments"]:
            print(f"    — {att.get('name', 'unknown')} ({att.get('size_kb', '?')} KB)")
    print(f"{'═'*60}")
    print(f"\n  TO APPROVE AND SEND: --send {draft_id}")
    print(f"  Draft will NOT be sent without explicit approval.\n")

    return draft


def send_draft(draft_id: str) -> Dict:
    """
    Send an approved draft via Proton Bridge.
    Requires interactive confirmation.
    """
    manager = DraftManager(SUBMISSION_DIR)
    draft = manager.load_draft(draft_id)

    if not draft:
        print(f"  ✗ Draft not found: {draft_id}")
        return {"error": "Draft not found"}

    if draft["status"] == "SENT":
        print(f"  ⚠ Draft {draft_id} was already sent on {draft.get('sent_at')}")
        return draft

    # Human approval gate
    print(f"\n{'═'*60}")
    print(f"  ⚠ HUMAN APPROVAL REQUIRED")
    print(f"  Sending to: {draft['to']}")
    print(f"  Subject: {draft['subject']}")
    print(f"{'═'*60}")

    confirm = input("\n  Type 'APPROVE' to send, or anything else to cancel: ").strip()
    if confirm != "APPROVE":
        print("  ✗ Submission cancelled by user.")
        return {"status": "CANCELLED"}

    # Send via Proton Bridge
    client = ProtonBridgeClient()
    try:
        result = client.send_email(
            to_email=draft["to"],
            subject=draft["subject"],
            body=draft["body"],
            attachment_paths=[att["path"] for att in draft.get("attachments", [])
                              if att.get("path")],
        )

        # Update draft status
        draft["status"] = "SENT"
        draft["sent_at"] = datetime.now().isoformat()
        draft["human_approved"] = True
        manager.save_draft(draft)

        print(f"\n  ✓ SENT SUCCESSFULLY")
        print(f"  To: {draft['to']}")
        print(f"  Sent at: {draft['sent_at']}")
        return draft

    except Exception as e:
        draft["status"] = f"SEND_FAILED: {str(e)}"
        manager.save_draft(draft)
        print(f"\n  ✗ SEND FAILED: {e}")
        return {"error": str(e)}


def check_inbox(since_days: int = 7) -> List[Dict]:
    """Check Proton inbox for regulatory responses."""
    handler = ResponseHandler()
    try:
        responses = handler.check_inbox(since_days)
        print(f"\n  Checked inbox for last {since_days} days:")
        print(f"  → {len(responses)} messages found")
        for r in responses:
            print(f"    [{r.get('classification', 'UNKNOWN')}] "
                  f"From: {r.get('from', 'N/A')} — {r.get('subject', 'N/A')}")
        return responses
    except Exception as e:
        print(f"  ✗ Inbox check failed: {e}")
        return []


def show_submission_log():
    """Display all submission drafts and their statuses."""
    manager = DraftManager(SUBMISSION_DIR)
    drafts = manager.list_all()

    print(f"\n{'═'*60}")
    print(f"  SUBMISSION LOG — {len(drafts)} drafts")
    print(f"{'═'*60}")

    sent = [d for d in drafts if d.get("status") == "SENT"]
    pending = [d for d in drafts if d.get("status") == "PENDING_HUMAN_REVIEW"]
    failed = [d for d in drafts if "FAILED" in str(d.get("status", ""))]

    print(f"  Sent: {len(sent)}  |  Pending: {len(pending)}  |  Failed: {len(failed)}")
    print(f"{'─'*60}")

    for d in drafts:
        print(f"  {d.get('draft_id', 'N/A')} | {d.get('status', 'N/A')} | "
              f"To: {d.get('to', 'N/A')} | {d.get('created_at', 'N/A')[:10]}")

    print(f"{'═'*60}\n")


def main():
    parser = argparse.ArgumentParser(description="JLAW Submission Manager Agent")
    parser.add_argument("--draft", type=str, help="Create draft for target (sec|doj|iss)")
    parser.add_argument("--review", type=str, help="Review a draft by ID")
    parser.add_argument("--send", type=str, help="Send an approved draft by ID")
    parser.add_argument("--inbox", type=int, help="Check inbox (last N days)")
    parser.add_argument("--log", action="store_true", help="Show submission log")

    args = parser.parse_args()

    if args.draft:
        draft_submission(args.draft)
    elif args.review:
        review_draft(args.review)
    elif args.send:
        send_draft(args.send)
    elif args.inbox:
        check_inbox(args.inbox)
    elif args.log:
        show_submission_log()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
