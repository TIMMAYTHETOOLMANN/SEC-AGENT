"""
JLAW Draft Manager
Handles creation, storage, review, and lifecycle of submission drafts.

Every regulatory submission draft is persisted as a JSON file in
data/submissions/ with full audit metadata.

Draft lifecycle:
  PENDING_HUMAN_REVIEW → APPROVED → SENT
  PENDING_HUMAN_REVIEW → CANCELLED
  PENDING_HUMAN_REVIEW → APPROVED → SEND_FAILED
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class DraftManager:
    """Manages submission draft creation, storage, and lifecycle."""

    def __init__(self, submission_dir: Path = None):
        self.submission_dir = submission_dir or Path(
            os.environ.get("JLAW_DATA_DIR", "./data")
        ) / "submissions"
        self.submission_dir.mkdir(parents=True, exist_ok=True)

    def create_draft(self, target_id: str, target_name: str, target_email: str,
                     subject: str, body: str,
                     attachment_paths: List[str] = None) -> Dict:
        """
        Create a new submission draft.

        Args:
            target_id: Internal target identifier (e.g., 'sec_enforcement')
            target_name: Human-readable target name
            target_email: Recipient email address
            subject: Email subject line
            body: Email body text
            attachment_paths: List of file paths to attach

        Returns:
            Draft dict with draft_id and metadata
        """
        draft_id = f"DRAFT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{target_id}"

        # Validate attachments
        attachments = []
        for path_str in (attachment_paths or []):
            p = Path(path_str)
            if p.exists():
                attachments.append({
                    "path": str(p.resolve()),
                    "name": p.name,
                    "size_kb": p.stat().st_size // 1024,
                    "status": "VALID",
                })
            else:
                attachments.append({
                    "path": str(p),
                    "name": p.name,
                    "size_kb": 0,
                    "status": "FILE_NOT_FOUND",
                })

        from_email = os.environ.get("PROTON_EMAIL", "")

        draft = {
            "draft_id": draft_id,
            "target_id": target_id,
            "target_name": target_name,
            "from": from_email,
            "to": target_email,
            "subject": subject,
            "body": body,
            "attachments": attachments,
            "created_at": datetime.now().isoformat(),
            "status": "PENDING_HUMAN_REVIEW",
            "sent_at": None,
            "human_approved": False,
            "review_notes": None,
            "audit_trail": [
                {
                    "action": "CREATED",
                    "timestamp": datetime.now().isoformat(),
                    "actor": "system",
                }
            ],
        }

        self.save_draft(draft)
        return draft

    def save_draft(self, draft: Dict):
        """Save/update a draft to disk."""
        draft_file = self.submission_dir / f"{draft['draft_id']}.json"
        with open(draft_file, "w") as f:
            json.dump(draft, f, indent=2)

    def load_draft(self, draft_id: str) -> Optional[Dict]:
        """Load a draft by ID."""
        draft_file = self.submission_dir / f"{draft_id}.json"
        if draft_file.exists():
            with open(draft_file) as f:
                return json.load(f)
        return None

    def approve_draft(self, draft_id: str, notes: str = None) -> Optional[Dict]:
        """Mark a draft as approved (but not yet sent)."""
        draft = self.load_draft(draft_id)
        if not draft:
            return None

        draft["status"] = "APPROVED"
        draft["human_approved"] = True
        draft["review_notes"] = notes
        draft["audit_trail"].append({
            "action": "APPROVED",
            "timestamp": datetime.now().isoformat(),
            "actor": "human",
            "notes": notes,
        })

        self.save_draft(draft)
        return draft

    def mark_sent(self, draft_id: str) -> Optional[Dict]:
        """Mark a draft as successfully sent."""
        draft = self.load_draft(draft_id)
        if not draft:
            return None

        draft["status"] = "SENT"
        draft["sent_at"] = datetime.now().isoformat()
        draft["audit_trail"].append({
            "action": "SENT",
            "timestamp": datetime.now().isoformat(),
            "actor": "system",
        })

        self.save_draft(draft)
        return draft

    def mark_failed(self, draft_id: str, error: str) -> Optional[Dict]:
        """Mark a draft as failed to send."""
        draft = self.load_draft(draft_id)
        if not draft:
            return None

        draft["status"] = f"SEND_FAILED: {error}"
        draft["audit_trail"].append({
            "action": "SEND_FAILED",
            "timestamp": datetime.now().isoformat(),
            "actor": "system",
            "error": error,
        })

        self.save_draft(draft)
        return draft

    def cancel_draft(self, draft_id: str, reason: str = None) -> Optional[Dict]:
        """Cancel a pending draft."""
        draft = self.load_draft(draft_id)
        if not draft:
            return None

        draft["status"] = "CANCELLED"
        draft["audit_trail"].append({
            "action": "CANCELLED",
            "timestamp": datetime.now().isoformat(),
            "actor": "human",
            "reason": reason,
        })

        self.save_draft(draft)
        return draft

    def list_all(self) -> List[Dict]:
        """List all drafts with their current status."""
        drafts = []
        for f in sorted(self.submission_dir.glob("DRAFT-*.json")):
            try:
                with open(f) as fh:
                    drafts.append(json.load(fh))
            except (json.JSONDecodeError, OSError):
                continue
        return drafts

    def list_pending(self) -> List[Dict]:
        """List only pending (unreviewed) drafts."""
        return [d for d in self.list_all() if d.get("status") == "PENDING_HUMAN_REVIEW"]

    def list_sent(self) -> List[Dict]:
        """List only sent drafts."""
        return [d for d in self.list_all() if d.get("status") == "SENT"]

    def get_audit_trail(self, draft_id: str) -> List[Dict]:
        """Get the full audit trail for a draft."""
        draft = self.load_draft(draft_id)
        if draft:
            return draft.get("audit_trail", [])
        return []
