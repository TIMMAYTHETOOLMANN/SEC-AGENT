"""
JLAW Response Handler
Monitors Proton inbox for regulatory responses, classifies them,
and routes escalations to the orchestrator/human.

Response classifications:
  ACKNOWLEDGMENT    — Receipt confirmation, case number assignment
  INQUIRY           — Follow-up question from agency
  REQUEST_FOR_INFO  — Formal request for additional documentation
  ESCALATION        — Subpoena, investigation notice, enforcement action
  GENERAL           — Unclassified / non-regulatory email

Usage:
    Typically called by submission_manager agent, not directly.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from src.submission.proton_client import ProtonBridgeClient


# Response classification rules
CLASSIFICATION_RULES = {
    "SEC_RESPONSE": {
        "sender_patterns": ["sec.gov", "edgar", "enforcement"],
        "subject_patterns": ["tcr", "enforcement", "inquiry", "investigation",
                             "subpoena", "case number", "receipt"],
    },
    "DOJ_RESPONSE": {
        "sender_patterns": ["usdoj.gov", "justice.gov", "fraud"],
        "subject_patterns": ["referral", "investigation", "criminal", "subpoena"],
    },
    "ISS_RESPONSE": {
        "sender_patterns": ["issgovernance", "iss-governance"],
        "subject_patterns": ["governance", "engagement", "proxy"],
    },
    "CONGRESSIONAL_RESPONSE": {
        "sender_patterns": ["senate.gov", "house.gov", "congress.gov"],
        "subject_patterns": ["briefing", "committee", "hearing", "testimony"],
    },
}

# Escalation keywords (require immediate human attention)
ESCALATION_KEYWORDS = [
    "subpoena",
    "enforcement action",
    "formal investigation",
    "formal order",
    "cease and desist",
    "wells notice",
    "testimony",
    "deposition",
    "grand jury",
    "indictment",
]


class ResponseHandler:
    """Handles inbox monitoring, classification, and escalation routing."""

    def __init__(self, submission_dir: Path = None):
        self.client = ProtonBridgeClient()
        self.submission_dir = submission_dir or Path(
            os.environ.get("JLAW_DATA_DIR", "./data")
        ) / "submissions"
        self.response_log_path = self.submission_dir / "response_log.json"

    def _load_response_log(self) -> List[Dict]:
        """Load the response log."""
        if self.response_log_path.exists():
            with open(self.response_log_path) as f:
                return json.load(f)
        return []

    def _save_response_log(self, log: List[Dict]):
        """Save the response log."""
        self.submission_dir.mkdir(parents=True, exist_ok=True)
        with open(self.response_log_path, "w") as f:
            json.dump(log, f, indent=2)

    def classify_email(self, sender: str, subject: str, body: str = "") -> Dict:
        """
        Classify an email response by sender and content.

        Returns:
            Dict with classification, priority, and escalation status
        """
        sender_lower = (sender or "").lower()
        subject_lower = (subject or "").lower()
        body_lower = (body or "").lower()
        combined = f"{sender_lower} {subject_lower} {body_lower}"

        # Determine source classification
        source = "GENERAL"
        for cls, rules in CLASSIFICATION_RULES.items():
            sender_match = any(p in sender_lower for p in rules["sender_patterns"])
            subject_match = any(p in subject_lower for p in rules["subject_patterns"])
            if sender_match or subject_match:
                source = cls
                break

        # Determine response type
        response_type = "ACKNOWLEDGMENT"
        if any(kw in combined for kw in ["inquiry", "question", "clarif", "please provide"]):
            response_type = "INQUIRY"
        elif any(kw in combined for kw in ["request for", "additional documentation",
                                            "supplemental", "please submit"]):
            response_type = "REQUEST_FOR_INFO"
        elif any(kw in combined for kw in ESCALATION_KEYWORDS):
            response_type = "ESCALATION"

        # Determine priority
        priority = "NORMAL"
        if response_type == "ESCALATION":
            priority = "CRITICAL"
        elif response_type == "REQUEST_FOR_INFO":
            priority = "HIGH"
        elif response_type == "INQUIRY":
            priority = "MEDIUM"

        # Check for escalation
        requires_escalation = response_type == "ESCALATION" or any(
            kw in combined for kw in ESCALATION_KEYWORDS
        )

        return {
            "source": source,
            "response_type": response_type,
            "priority": priority,
            "requires_escalation": requires_escalation,
        }

    def check_inbox(self, since_days: int = 7) -> List[Dict]:
        """
        Check inbox for regulatory responses.

        Args:
            since_days: Check emails from last N days

        Returns:
            List of classified email dicts
        """
        try:
            raw_messages = self.client.fetch_inbox(since_days)
        except Exception as e:
            return [{"error": f"Inbox check failed: {str(e)}"}]

        classified = []
        log = self._load_response_log()
        seen_ids = {r.get("message_id") for r in log}

        for msg in raw_messages:
            msg_id = msg.get("message_id", "")

            # Classify
            classification = self.classify_email(
                sender=msg.get("from", ""),
                subject=msg.get("subject", ""),
            )

            result = {
                "message_id": msg_id,
                "from": msg.get("from", ""),
                "subject": msg.get("subject", ""),
                "date": msg.get("date", ""),
                "classification": classification["source"],
                "response_type": classification["response_type"],
                "priority": classification["priority"],
                "requires_escalation": classification["requires_escalation"],
                "processed_at": datetime.now().isoformat(),
            }

            classified.append(result)

            # Log new messages
            if msg_id and msg_id not in seen_ids:
                log.append(result)
                seen_ids.add(msg_id)

        self._save_response_log(log)
        return classified

    def get_escalations(self) -> List[Dict]:
        """Get all responses marked for escalation."""
        log = self._load_response_log()
        return [r for r in log if r.get("requires_escalation")]

    def get_pending_inquiries(self) -> List[Dict]:
        """Get all unresolved inquiries and info requests."""
        log = self._load_response_log()
        return [r for r in log if r.get("response_type") in ("INQUIRY", "REQUEST_FOR_INFO")
                and not r.get("resolved")]

    def mark_resolved(self, message_id: str, resolution: str):
        """Mark a response as resolved."""
        log = self._load_response_log()
        for entry in log:
            if entry.get("message_id") == message_id:
                entry["resolved"] = True
                entry["resolution"] = resolution
                entry["resolved_at"] = datetime.now().isoformat()
                break
        self._save_response_log(log)

    def generate_response_summary(self) -> Dict:
        """Generate a summary of all responses for the orchestrator."""
        log = self._load_response_log()

        return {
            "generated_at": datetime.now().isoformat(),
            "total_responses": len(log),
            "by_source": {
                source: len([r for r in log if r.get("classification") == source])
                for source in set(r.get("classification", "UNKNOWN") for r in log)
            },
            "by_type": {
                rtype: len([r for r in log if r.get("response_type") == rtype])
                for rtype in set(r.get("response_type", "UNKNOWN") for r in log)
            },
            "escalations": len([r for r in log if r.get("requires_escalation")]),
            "pending_inquiries": len([r for r in log if r.get("response_type")
                                      in ("INQUIRY", "REQUEST_FOR_INFO")
                                      and not r.get("resolved")]),
        }
