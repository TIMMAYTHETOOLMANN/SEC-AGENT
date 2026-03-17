"""
JLAW Draft Manager
Creates, persists, and manages the approval workflow for regulatory
submission drafts. Maintains a complete audit trail.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", "./data"))
SUBMISSION_DIR = DATA_DIR / "submissions"


class DraftManager:
    """Manages the lifecycle of regulatory submission drafts."""

    def __init__(self, submission_dir: Path = None):
        self.dir = submission_dir or SUBMISSION_DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def create_draft(
        self,
        target_id: str,
        target_name: str,
        target_email: str,
        subject: str,
        body: str,
        attachment_paths: List[str] = None,
    ) -> Dict:
        """Create a new draft submission."""
        draft_id = f"DRAFT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{target_id}"

        attachments = []
        for path_str in (attachment_paths or []):
            p = Path(path_str)
            attachments.append({
                "path": str(p),
                "name": p.name,
                "exists": p.exists(),
                "size_kb": p.stat().st_size // 1024 if p.exists() else 0,
            })

        draft = {
            "draft_id": draft_id,
            "target_id": target_id,
            "target_name": target_name,
            "target_email": target_email,
            "subject": subject,
            "body": body,
            "attachments": attachments,
            "status": "PENDING_REVIEW",
            "created_at": datetime.now().isoformat(),
            "reviewed_at": None,
            "approved_at": None,
            "sent_at": None,
            "rejected_at": None,
            "rejection_reason": None,
            "audit_trail": [
                {
                    "action": "CREATED",
                    "timestamp": datetime.now().isoformat(),
                    "details": f"Draft created for {target_name}",
                }
            ],
        }

        self._save(draft)
        return draft

    def get_draft(self, draft_id: str) -> Optional[Dict]:
        """Load a draft by ID."""
        path = self.dir / f"{draft_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def list_drafts(self, status: str = None) -> List[Dict]:
        """List all drafts, optionally filtered by status."""
        drafts = []
        for f in sorted(self.dir.glob("DRAFT-*.json")):
            with open(f) as fh:
                draft = json.load(fh)
            if status is None or draft.get("status") == status:
                drafts.append({
                    "draft_id": draft["draft_id"],
                    "target": draft["target_name"],
                    "subject": draft["subject"],
                    "status": draft["status"],
                    "created_at": draft["created_at"],
                })
        return drafts

    def approve(self, draft_id: str) -> Dict:
        """Mark a draft as approved for sending."""
        draft = self.get_draft(draft_id)
        if not draft:
            return {"error": f"Draft {draft_id} not found"}
        if draft["status"] != "PENDING_REVIEW":
            return {"error": f"Draft is {draft['status']}, not PENDING_REVIEW"}

        draft["status"] = "APPROVED"
        draft["approved_at"] = datetime.now().isoformat()
        draft["audit_trail"].append({
            "action": "APPROVED",
            "timestamp": datetime.now().isoformat(),
            "details": "Human approval granted for sending",
        })
        self._save(draft)
        return draft

    def reject(self, draft_id: str, reason: str = "") -> Dict:
        """Reject a draft."""
        draft = self.get_draft(draft_id)
        if not draft:
            return {"error": f"Draft {draft_id} not found"}

        draft["status"] = "REJECTED"
        draft["rejected_at"] = datetime.now().isoformat()
        draft["rejection_reason"] = reason
        draft["audit_trail"].append({
            "action": "REJECTED",
            "timestamp": datetime.now().isoformat(),
            "details": f"Rejected: {reason}",
        })
        self._save(draft)
        return draft

    def mark_sent(self, draft_id: str, send_result: Dict) -> Dict:
        """Record that a draft was successfully sent."""
        draft = self.get_draft(draft_id)
        if not draft:
            return {"error": f"Draft {draft_id} not found"}

        draft["status"] = "SENT"
        draft["sent_at"] = datetime.now().isoformat()
        draft["send_result"] = send_result
        draft["audit_trail"].append({
            "action": "SENT",
            "timestamp": datetime.now().isoformat(),
            "details": f"Sent to {draft['target_email']}",
        })
        self._save(draft)
        return draft

    def mark_failed(self, draft_id: str, error: str) -> Dict:
        """Record a send failure."""
        draft = self.get_draft(draft_id)
        if not draft:
            return {"error": f"Draft {draft_id} not found"}

        draft["status"] = "SEND_FAILED"
        draft["audit_trail"].append({
            "action": "SEND_FAILED",
            "timestamp": datetime.now().isoformat(),
            "details": f"Send failed: {error}",
        })
        self._save(draft)
        return draft

    def get_audit_trail(self, draft_id: str) -> List[Dict]:
        """Get the complete audit trail for a draft."""
        draft = self.get_draft(draft_id)
        if draft:
            return draft.get("audit_trail", [])
        return []

    def _save(self, draft: Dict):
        """Persist a draft to disk."""
        path = self.dir / f"{draft['draft_id']}.json"
        with open(path, "w") as f:
            json.dump(draft, f, indent=2)
