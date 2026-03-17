"""
JLAW Correspondence Agent
═══════════════════════════════════════════════════════════════════════
Claude-powered autonomous correspondence management via Proton Bridge.
Handles the full lifecycle of regulatory communications:

  1. Intelligent email drafting (Claude-composed, not template-based)
  2. Inbox monitoring with AI-powered response classification
  3. Adaptive follow-up drafting based on inquiry content
  4. Escalation detection and human alerting
  5. Correspondence state tracking across multi-turn regulatory dialogues

This agent BRIDGES the Claude Compositor (AI brain) with the Proton client
(email transport) and the Draft Manager (lifecycle tracking).

CRITICAL: ALL outbound emails require explicit human approval.
This agent drafts — it NEVER sends autonomously.

Usage:
    python -m src.agents.correspondence_agent --monitor
    python -m src.agents.correspondence_agent --draft sec
    python -m src.agents.correspondence_agent --respond
    python -m src.agents.correspondence_agent --status
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from dotenv import load_dotenv

# ═══════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")
DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", PROJECT_ROOT / "data"))
SUBMISSIONS_DIR = DATA_DIR / "submissions"
REPORTS_DIR = DATA_DIR / "reports"
LOG_DIR = Path(os.environ.get("JLAW_LOG_DIR", PROJECT_ROOT / "logs"))

# Import sibling modules
from src.agents.claude_compositor import ClaudeCompositor
from src.submission.proton_client import ProtonBridgeClient
from src.submission.draft_manager import DraftManager
from src.submission.response_handler import ResponseHandler


# Submission targets (mirrors submission_manager.py)
TARGETS = {
    "sec": {
        "target_id": "sec_enforcement",
        "name": "SEC Division of Enforcement",
        "email": "enforcement@sec.gov",
        "report_prefix": "SEC_Enforcement_Bundle",
    },
    "sec_whistleblower": {
        "target_id": "sec_whistleblower",
        "name": "SEC Office of the Whistleblower",
        "email": "whistleblower@sec.gov",
        "report_prefix": "SEC_Enforcement_Bundle",
    },
    "doj": {
        "target_id": "doj_fraud",
        "name": "DOJ Fraud Section",
        "email": "fraud.section@usdoj.gov",
        "report_prefix": "DOJ_Criminal_Referral",
    },
    "iss": {
        "target_id": "iss_governance",
        "name": "ISS Governance Research",
        "email": "governance@issgovernance.com",
        "report_prefix": "Legislative_Briefing",
    },
    "senate": {
        "target_id": "senate_banking",
        "name": "Senate Banking Committee",
        "email": "banking@senate.gov",
        "report_prefix": "Legislative_Briefing",
    },
    "house": {
        "target_id": "house_financial",
        "name": "House Financial Services Committee",
        "email": "financialsvcs@mail.house.gov",
        "report_prefix": "Legislative_Briefing",
    },
}


def _find_latest_report(prefix: str) -> Optional[Path]:
    """Find the most recently generated report matching a prefix."""
    if not REPORTS_DIR.exists():
        return None
    matches = sorted(REPORTS_DIR.glob(f"{prefix}*.docx"), reverse=True)
    return matches[0] if matches else None


class CorrespondenceAgent:
    """
    Full-lifecycle correspondence manager.
    Compositor → Draft → Review → Send → Monitor → Respond (loop).
    """

    def __init__(self):
        self.compositor = ClaudeCompositor()
        self.draft_manager = DraftManager(SUBMISSIONS_DIR)
        self.response_handler = ResponseHandler(SUBMISSIONS_DIR)
        self.proton_client = ProtonBridgeClient()
        self.correspondence_log_path = SUBMISSIONS_DIR / "correspondence_state.json"

    def _load_correspondence_state(self) -> Dict:
        """Load the full correspondence state."""
        if self.correspondence_log_path.exists():
            with open(self.correspondence_log_path) as f:
                return json.load(f)
        return {
            "threads": {},
            "last_inbox_check": None,
            "total_sent": 0,
            "total_drafted": 0,
            "total_responses_received": 0,
            "active_dialogues": [],
        }

    def _save_correspondence_state(self, state: Dict):
        """Save the correspondence state."""
        SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
        state["last_updated"] = datetime.now().isoformat()
        with open(self.correspondence_log_path, "w") as f:
            json.dump(state, f, indent=2)

    # ═══════════════════════════════════════════════
    # DRAFTING — Claude-Composed Submissions
    # ═══════════════════════════════════════════════

    def draft_submission(self, target_key: str) -> Dict:
        """
        Draft a submission using Claude-composed content.
        The Compositor generates the email body; the Draft Manager
        handles lifecycle tracking.
        """
        target = TARGETS.get(target_key)
        if not target:
            print(f"  ✗ Unknown target: {target_key}. Available: {', '.join(TARGETS.keys())}")
            return {"error": f"Unknown target: {target_key}"}

        print(f"  [CORRESPONDENCE] Composing submission for {target['name']}...")

        # Use Claude Compositor for intelligent body composition
        composed = self.compositor.draft_initial_submission(target_key)

        # Find the latest report to attach
        report_path = _find_latest_report(target["report_prefix"])
        attachments = []
        if report_path:
            attachments.append(str(report_path))
            print(f"  [CORRESPONDENCE] Attaching report: {report_path.name}")
        else:
            print(f"  ⚠ No report found matching '{target['report_prefix']}*'. "
                  f"Run report generation first.")

        # Also look for the master report as supplemental
        master = _find_latest_report("Master_Cross_Analysis")
        if master and str(master) not in attachments:
            attachments.append(str(master))
            print(f"  [CORRESPONDENCE] Attaching master report: {master.name}")

        # Create the draft via Draft Manager
        draft = self.draft_manager.create_draft(
            target_id=target["target_id"],
            target_name=target["name"],
            target_email=target["email"],
            subject=composed["subject"],
            body=composed["body"],
            attachment_paths=attachments,
        )

        # Update correspondence state
        state = self._load_correspondence_state()
        state["total_drafted"] = state.get("total_drafted", 0) + 1
        thread_id = f"THREAD-{target_key}-{datetime.now().strftime('%Y%m%d')}"
        state["threads"][thread_id] = {
            "target": target_key,
            "target_name": target["name"],
            "draft_id": draft["draft_id"],
            "created_at": datetime.now().isoformat(),
            "status": "DRAFTED",
            "messages": [
                {
                    "direction": "OUTBOUND",
                    "draft_id": draft["draft_id"],
                    "composed_by": "claude_compositor",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }
        self._save_correspondence_state(state)

        # Save the compositor draft separately for audit
        self.compositor.save_correspondence_draft(composed)

        print(f"\n  ✓ Draft created: {draft['draft_id']}")
        print(f"  ═══ COMPOSED DRAFT PREVIEW ═══")
        print(f"  To: {draft['to']}")
        print(f"  Subject: {draft['subject']}")
        print(f"  Attachments: {len(draft.get('attachments', []))}")
        print(f"  ───────────────────────────────")
        body_preview = composed['body'][:1000]
        for line in body_preview.split('\n'):
            print(f"  {line}")
        if len(composed['body']) > 1000:
            print(f"  ... [{len(composed['body']) - 1000} more characters]")
        print(f"  ═══════════════════════════════")
        print(f"\n  ⚠ This draft has NOT been sent.")
        print(f"  Review: python run.py submit --review {draft['draft_id']}")
        print(f"  Send:   python run.py submit --send {draft['draft_id']}")

        return draft

    def draft_all_submissions(self) -> List[Dict]:
        """Draft submissions for ALL regulatory targets."""
        drafts = []
        for target_key in ["sec", "sec_whistleblower", "doj", "iss", "senate", "house"]:
            print(f"\n  {'─'*40}")
            print(f"  Drafting for: {target_key.upper()}")
            print(f"  {'─'*40}")
            draft = self.draft_submission(target_key)
            if "error" not in draft:
                drafts.append(draft)
        return drafts

    # ═══════════════════════════════════════════════
    # MONITORING — Intelligent Inbox Surveillance
    # ═══════════════════════════════════════════════

    def monitor_inbox(self, since_days: int = 7) -> Dict:
        """
        Check inbox for responses and auto-classify + draft responses.
        """
        print(f"  [CORRESPONDENCE] Checking inbox for last {since_days} days...")

        state = self._load_correspondence_state()

        # Check inbox
        responses = self.response_handler.check_inbox(since_days)

        if not responses:
            print("  [CORRESPONDENCE] No new messages found.")
            state["last_inbox_check"] = datetime.now().isoformat()
            self._save_correspondence_state(state)
            return {"messages": 0, "actions": []}

        print(f"  [CORRESPONDENCE] Found {len(responses)} messages.")

        actions = []
        for msg in responses:
            classification = msg.get("classification", "GENERAL")
            response_type = msg.get("response_type", "GENERAL")
            priority = msg.get("priority", "NORMAL")

            print(f"  [{priority}] {classification}/{response_type}: "
                  f"{msg.get('subject', 'No subject')}")

            # Handle based on type
            if msg.get("requires_escalation"):
                print(f"  🚨 ESCALATION DETECTED — drafting preliminary response...")
                draft = self.compositor.draft_escalation_response(
                    escalation_type=response_type,
                    original_message=msg,
                )
                self.compositor.save_correspondence_draft(draft)
                actions.append({
                    "type": "ESCALATION_DRAFT",
                    "message_id": msg.get("message_id"),
                    "priority": "CRITICAL",
                    "draft_saved": True,
                })
                print(f"  ⚠ HUMAN REVIEW REQUIRED for escalation response.")

            elif response_type in ("INQUIRY", "REQUEST_FOR_INFO"):
                print(f"  📨 Inquiry detected — drafting intelligent response...")
                draft = self.compositor.draft_inquiry_response(
                    inquiry_subject=msg.get("subject", ""),
                    inquiry_body="",  # Would need IMAP body fetch
                    inquiry_from=msg.get("from", ""),
                    classification=classification,
                )
                self.compositor.save_correspondence_draft(draft)
                actions.append({
                    "type": "INQUIRY_RESPONSE_DRAFT",
                    "message_id": msg.get("message_id"),
                    "priority": priority,
                    "draft_saved": True,
                })

            elif response_type == "ACKNOWLEDGMENT":
                print(f"  ✓ Acknowledgment received — logged.")
                actions.append({
                    "type": "ACKNOWLEDGMENT_LOGGED",
                    "message_id": msg.get("message_id"),
                })

            # Update correspondence state
            state["total_responses_received"] = state.get("total_responses_received", 0) + 1

        state["last_inbox_check"] = datetime.now().isoformat()
        self._save_correspondence_state(state)

        return {"messages": len(responses), "actions": actions}

    def monitor_continuous(self, interval_minutes: int = 30, max_checks: int = 48):
        """
        Continuous inbox monitoring loop.
        Runs for max_checks iterations (default 48 = 24 hours at 30min intervals).
        """
        print(f"  [CORRESPONDENCE] Starting continuous monitoring...")
        print(f"  Interval: {interval_minutes} minutes | Max checks: {max_checks}")
        print(f"  Press Ctrl+C to stop.\n")

        for i in range(max_checks):
            print(f"\n  ═══ CHECK {i+1}/{max_checks} — "
                  f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ═══")

            try:
                result = self.monitor_inbox(since_days=1)
                if result.get("actions"):
                    for action in result["actions"]:
                        if action.get("priority") == "CRITICAL":
                            print(f"\n  🚨🚨🚨 CRITICAL ACTION REQUIRED 🚨🚨🚨")
                            print(f"  Type: {action['type']}")
                            print(f"  Check data/submissions/ for draft responses.")

            except Exception as e:
                print(f"  ✗ Monitoring error: {e}")

            if i < max_checks - 1:
                print(f"  Next check in {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

    # ═══════════════════════════════════════════════
    # RESPONSE — Intelligent Follow-Up
    # ═══════════════════════════════════════════════

    def respond_to_pending(self) -> List[Dict]:
        """
        Draft responses to ALL pending inquiries and info requests.
        """
        pending = self.response_handler.get_pending_inquiries()

        if not pending:
            print("  [CORRESPONDENCE] No pending inquiries to respond to.")
            return []

        print(f"  [CORRESPONDENCE] Found {len(pending)} pending inquiries.")

        drafts = []
        for inquiry in pending:
            print(f"\n  Drafting response to: {inquiry.get('subject', 'No subject')}")
            print(f"  From: {inquiry.get('from', 'Unknown')}")
            print(f"  Classification: {inquiry.get('classification', 'GENERAL')}")

            draft = self.compositor.draft_inquiry_response(
                inquiry_subject=inquiry.get("subject", ""),
                inquiry_body="",
                inquiry_from=inquiry.get("from", ""),
                classification=inquiry.get("classification", "GENERAL"),
            )
            path = self.compositor.save_correspondence_draft(draft)
            drafts.append(draft)

            print(f"  ✓ Response draft saved: {path}")
            print(f"  ⚠ Human review required before sending.")

        return drafts

    # ═══════════════════════════════════════════════
    # STATUS — Correspondence Dashboard
    # ═══════════════════════════════════════════════

    def show_status(self):
        """Display full correspondence status dashboard."""
        state = self._load_correspondence_state()
        all_drafts = self.draft_manager.list_all()
        pending_drafts = self.draft_manager.list_pending()
        sent_drafts = self.draft_manager.list_sent()
        response_summary = self.response_handler.generate_response_summary()
        escalations = self.response_handler.get_escalations()
        pending_inquiries = self.response_handler.get_pending_inquiries()

        # Proton health check
        try:
            health = self.proton_client.check_health()
            proton_smtp = "✓" if health.get("smtp_ok") else "✗"
            proton_imap = "✓" if health.get("imap_ok") else "✗"
        except Exception:
            proton_smtp = "✗"
            proton_imap = "✗"

        print(f"\n{'═'*60}")
        print(f"  JLAW CORRESPONDENCE AGENT — STATUS DASHBOARD")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'═'*60}")

        print(f"\n  PROTON BRIDGE:")
        print(f"    SMTP: {proton_smtp}  |  IMAP: {proton_imap}")
        print(f"    Last inbox check: {state.get('last_inbox_check', 'Never')}")

        print(f"\n  DRAFTS:")
        print(f"    Total: {len(all_drafts)}  |  Pending: {len(pending_drafts)}  |  Sent: {len(sent_drafts)}")

        print(f"\n  RESPONSES:")
        print(f"    Total received: {response_summary.get('total_responses', 0)}")
        print(f"    Escalations: {len(escalations)}")
        print(f"    Pending inquiries: {len(pending_inquiries)}")

        print(f"\n  CORRESPONDENCE STATE:")
        print(f"    Active threads: {len(state.get('threads', {}))}")
        print(f"    Total drafted: {state.get('total_drafted', 0)}")
        print(f"    Total responses: {state.get('total_responses_received', 0)}")

        if pending_drafts:
            print(f"\n  PENDING REVIEW:")
            for d in pending_drafts:
                print(f"    [{d['draft_id']}] → {d['to']} | {d['subject'][:50]}")

        if escalations:
            print(f"\n  🚨 ESCALATIONS REQUIRING ATTENTION:")
            for e in escalations:
                print(f"    [{e.get('priority', '?')}] From: {e.get('from', '?')} | "
                      f"{e.get('subject', '?')[:50]}")

        if pending_inquiries:
            print(f"\n  📨 PENDING INQUIRIES:")
            for q in pending_inquiries:
                print(f"    From: {q.get('from', '?')} | {q.get('subject', '?')[:50]}")

        print(f"\n{'═'*60}\n")


# ═══════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="JLAW Correspondence Agent — Claude-Powered Regulatory Communications"
    )
    parser.add_argument("--draft", type=str,
                        choices=list(TARGETS.keys()) + ["all"],
                        help="Draft a submission for a target (or 'all')")
    parser.add_argument("--monitor", action="store_true",
                        help="Check inbox for responses (single check)")
    parser.add_argument("--monitor-continuous", action="store_true",
                        help="Start continuous inbox monitoring loop")
    parser.add_argument("--respond", action="store_true",
                        help="Draft responses to all pending inquiries")
    parser.add_argument("--status", action="store_true",
                        help="Show correspondence status dashboard")
    parser.add_argument("--interval", type=int, default=30,
                        help="Monitoring interval in minutes (default: 30)")
    parser.add_argument("--since-days", type=int, default=7,
                        help="Check inbox for last N days (default: 7)")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  JLAW CORRESPONDENCE AGENT v5.1")
    print(f"  Claude-Powered Regulatory Communications")
    print(f"{'='*60}\n")

    agent = CorrespondenceAgent()

    if args.draft:
        if args.draft == "all":
            agent.draft_all_submissions()
        else:
            agent.draft_submission(args.draft)

    elif args.monitor:
        agent.monitor_inbox(since_days=args.since_days)

    elif args.monitor_continuous:
        agent.monitor_continuous(interval_minutes=args.interval)

    elif args.respond:
        agent.respond_to_pending()

    elif args.status:
        agent.show_status()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
