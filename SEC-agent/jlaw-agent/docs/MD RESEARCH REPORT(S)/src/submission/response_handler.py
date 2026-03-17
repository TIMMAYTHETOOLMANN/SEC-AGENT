"""
JLAW Response Handler
Monitors inbox for regulatory responses, classifies them by source
and type, and routes escalations to human attention.
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from .proton_client import ProtonClient


# Response classification rules
CLASSIFICATION_RULES = {
    "SEC_ACKNOWLEDGMENT": {
        "sender_patterns": ["sec.gov", "securities.*commission"],
        "subject_patterns": ["receipt", "acknowledge", "received", "TCR"],
        "priority": "LOW",
    },
    "SEC_INQUIRY": {
        "sender_patterns": ["sec.gov"],
        "subject_patterns": ["inquiry", "question", "request.*information", "follow.?up"],
        "priority": "HIGH",
    },
    "DOJ_ACKNOWLEDGMENT": {
        "sender_patterns": ["usdoj.gov", "justice.gov"],
        "subject_patterns": ["receipt", "acknowledge", "received"],
        "priority": "LOW",
    },
    "DOJ_INQUIRY": {
        "sender_patterns": ["usdoj.gov", "justice.gov"],
        "subject_patterns": ["inquiry", "investigation", "request", "subpoena"],
        "priority": "CRITICAL",
    },
    "ISS_RESPONSE": {
        "sender_patterns": ["issgovernance", "iss-governance"],
        "subject_patterns": ["governance", "qualityscore", "engagement"],
        "priority": "MEDIUM",
    },
    "CONGRESSIONAL": {
        "sender_patterns": ["senate.gov", "house.gov", "congress.gov"],
        "subject_patterns": ["committee", "hearing", "briefing", "staff"],
        "priority": "HIGH",
    },
}


class ResponseHandler:
    """Handles incoming regulatory responses."""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path(os.environ.get("JLAW_DATA_DIR", "./data"))
        self.response_dir = self.data_dir / "submissions" / "responses"
        self.response_dir.mkdir(parents=True, exist_ok=True)
        self.client = ProtonClient()

    def check_inbox(self, since_days: int = 7) -> List[Dict]:
        """Check inbox and classify all new messages."""
        messages = self.client.fetch_inbox(since_days=since_days)
        classified = []

        for msg in messages:
            if "error" in msg:
                classified.append(msg)
                continue

            classification = self._classify(msg)
            msg["classification"] = classification["type"]
            msg["priority"] = classification["priority"]
            msg["requires_action"] = classification["priority"] in ["HIGH", "CRITICAL"]
            classified.append(msg)

            # Save high-priority responses
            if msg["requires_action"]:
                self._save_response(msg)

        return classified

    def _classify(self, message: Dict) -> Dict:
        """Classify a message based on sender and subject patterns."""
        sender = (message.get("from", "") or "").lower()
        subject = (message.get("subject", "") or "").lower()

        for class_name, rules in CLASSIFICATION_RULES.items():
            sender_match = any(
                re.search(p, sender) for p in rules["sender_patterns"]
            )
            subject_match = any(
                re.search(p, subject) for p in rules["subject_patterns"]
            )

            if sender_match and subject_match:
                return {"type": class_name, "priority": rules["priority"]}
            elif sender_match:
                # Sender match alone gets one priority level lower
                return {"type": class_name, "priority": "MEDIUM"}

        return {"type": "UNCLASSIFIED", "priority": "LOW"}

    def _save_response(self, message: Dict):
        """Persist a response that requires action."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"RESPONSE-{ts}-{message.get('classification', 'UNK')}.json"
        filepath = self.response_dir / filename

        record = {
            **message,
            "saved_at": datetime.now().isoformat(),
            "action_taken": None,
            "action_date": None,
        }

        with open(filepath, "w") as f:
            json.dump(record, f, indent=2)

    def get_pending_actions(self) -> List[Dict]:
        """Get all responses requiring human action."""
        pending = []
        for f in sorted(self.response_dir.glob("RESPONSE-*.json")):
            with open(f) as fh:
                record = json.load(fh)
            if record.get("action_taken") is None and record.get("requires_action"):
                pending.append(record)
        return pending

    def mark_action_taken(self, response_file: str, action: str) -> Dict:
        """Record that action was taken on a response."""
        filepath = self.response_dir / response_file
        if not filepath.exists():
            return {"error": f"Response file {response_file} not found"}

        with open(filepath) as f:
            record = json.load(f)

        record["action_taken"] = action
        record["action_date"] = datetime.now().isoformat()

        with open(filepath, "w") as f:
            json.dump(record, f, indent=2)

        return record

    def generate_status_report(self) -> Dict:
        """Generate a summary of all response activity."""
        all_responses = []
        for f in sorted(self.response_dir.glob("RESPONSE-*.json")):
            with open(f) as fh:
                all_responses.append(json.load(fh))

        return {
            "generated_at": datetime.now().isoformat(),
            "total_responses": len(all_responses),
            "by_classification": {
                ctype: len([r for r in all_responses if r.get("classification") == ctype])
                for ctype in set(r.get("classification", "UNK") for r in all_responses)
            },
            "pending_action": len([r for r in all_responses if r.get("action_taken") is None and r.get("requires_action")]),
            "actions_completed": len([r for r in all_responses if r.get("action_taken") is not None]),
        }
