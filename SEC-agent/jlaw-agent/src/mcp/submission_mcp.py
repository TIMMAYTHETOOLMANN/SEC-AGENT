"""
JLAW Submission MCP Server
Manages secure regulatory communications via Proton Bridge SMTP/IMAP.
CRITICAL: All send operations require explicit human approval.

Run standalone: python -m src.mcp.submission_mcp
Used by submission_manager agent via stdio transport.
"""

import json
import os
import smtplib
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from datetime import datetime
from typing import Optional

from claude_agent_sdk import tool, create_sdk_mcp_server

# ═══════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════

PROTON_HOST = os.environ.get("PROTON_BRIDGE_HOST", "127.0.0.1")
PROTON_SMTP = int(os.environ.get("PROTON_BRIDGE_SMTP_PORT", "1025"))
PROTON_IMAP = int(os.environ.get("PROTON_BRIDGE_IMAP_PORT", "1143"))
PROTON_EMAIL = os.environ.get("PROTON_EMAIL", "")
PROTON_PASS = os.environ.get("PROTON_PASSWORD", "")

DATA_DIR = Path(os.environ.get("JLAW_DATA_DIR", "./data"))
SUBMISSION_DIR = DATA_DIR / "submissions"
SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)

# Pre-approved submission targets
APPROVED_TARGETS = {
    "sec_enforcement": {
        "name": "SEC Division of Enforcement",
        "email": "enforcement@sec.gov",
        "method": "TCR Form + supplemental email",
    },
    "sec_whistleblower": {
        "name": "SEC Office of the Whistleblower",
        "email": "whistleblower@sec.gov",
        "method": "Form TCR submission",
    },
    "doj_fraud": {
        "name": "DOJ Fraud Section",
        "email": "fraud.section@usdoj.gov",
        "method": "Criminal referral letter",
    },
    "iss_governance": {
        "name": "ISS Governance Research",
        "email": "governance@issgovernance.com",
        "method": "Engagement letter",
    },
}


# ═══════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════

@tool(
    "submission_list_targets",
    "List all pre-approved regulatory submission targets.",
    {}
)
async def submission_list_targets(args):
    return {"content": [{"type": "text", "text": json.dumps(APPROVED_TARGETS, indent=2)}]}


@tool(
    "submission_draft",
    "Create a draft submission email. Does NOT send — must be reviewed by human first. "
    "Returns a draft_id for reference in the approval step.",
    {
        "target_id": str,          # Key from APPROVED_TARGETS
        "subject": str,            # Email subject line
        "body": str,               # Email body text
        "attachment_paths": list,   # List of file paths to attach
    }
)
async def submission_draft(args):
    target = APPROVED_TARGETS.get(args["target_id"])
    if not target:
        return {"content": [{"type": "text",
                "text": f"ERROR: Unknown target '{args['target_id']}'. Use submission_list_targets to see options."}]}

    # Generate draft ID
    draft_id = f"DRAFT-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{args['target_id']}"

    # Validate attachments exist
    attachments_valid = []
    for path in args.get("attachment_paths", []):
        p = Path(path)
        if p.exists():
            attachments_valid.append({"path": str(p), "name": p.name, "size_kb": p.stat().st_size // 1024})
        else:
            attachments_valid.append({"path": str(p), "name": p.name, "status": "FILE NOT FOUND"})

    # Save draft to disk
    draft = {
        "draft_id": draft_id,
        "target": target,
        "from": PROTON_EMAIL,
        "to": target["email"],
        "subject": args["subject"],
        "body": args["body"],
        "attachments": attachments_valid,
        "created_at": datetime.now().isoformat(),
        "status": "PENDING_HUMAN_REVIEW",
        "sent_at": None,
        "human_approved": False,
    }

    draft_file = SUBMISSION_DIR / f"{draft_id}.json"
    with open(draft_file, "w") as f:
        json.dump(draft, f, indent=2)

    return {"content": [{"type": "text", "text": json.dumps({
        "status": "DRAFT CREATED — AWAITING HUMAN REVIEW",
        "draft_id": draft_id,
        "to": target["email"],
        "subject": args["subject"],
        "attachments": len(attachments_valid),
        "IMPORTANT": "This draft will NOT be sent until you call submission_send with human approval.",
        "review_file": str(draft_file),
    }, indent=2)}]}


@tool(
    "submission_review",
    "Display a draft for human review. Returns the full draft content for inspection.",
    {"draft_id": str}
)
async def submission_review(args):
    draft_file = SUBMISSION_DIR / f"{args['draft_id']}.json"
    if not draft_file.exists():
        return {"content": [{"type": "text", "text": f"Draft {args['draft_id']} not found."}]}

    with open(draft_file) as f:
        draft = json.load(f)

    review_text = f"""
╔══════════════════════════════════════════════════════════════╗
║  SUBMISSION DRAFT — HUMAN REVIEW REQUIRED                    ║
╠══════════════════════════════════════════════════════════════╣
║  Draft ID:  {draft['draft_id']}
║  Target:    {draft['target']['name']}
║  To:        {draft['to']}
║  From:      {draft['from']}
║  Subject:   {draft['subject']}
║  Created:   {draft['created_at']}
║  Status:    {draft['status']}
║  Attachments: {len(draft['attachments'])} files
╠══════════════════════════════════════════════════════════════╣
║  BODY:
║  {draft['body'][:500]}{'...' if len(draft['body']) > 500 else ''}
╠══════════════════════════════════════════════════════════════╣
║  ATTACHMENTS:
"""
    for att in draft["attachments"]:
        review_text += f"║    - {att['name']} ({att.get('size_kb', '?')} KB)\n"

    review_text += """╠══════════════════════════════════════════════════════════════╣
║  TO APPROVE: Call submission_send with this draft_id         ║
║  and human_approved=true                                     ║
║                                                              ║
║  TO REJECT:  No action needed. Draft remains in PENDING.     ║
╚══════════════════════════════════════════════════════════════╝
"""
    return {"content": [{"type": "text", "text": review_text}]}


@tool(
    "submission_send",
    "Send an approved draft via Proton Bridge SMTP. "
    "REQUIRES human_approved=true. Will REFUSE to send without explicit approval.",
    {
        "draft_id": str,
        "human_approved": bool,  # MUST be True
    }
)
async def submission_send(args):
    if not args.get("human_approved"):
        return {"content": [{"type": "text",
                "text": "BLOCKED: human_approved must be explicitly set to true. "
                        "This is a mandatory safety gate. No regulatory submission "
                        "may be sent without human review and approval."}]}

    draft_file = SUBMISSION_DIR / f"{args['draft_id']}.json"
    if not draft_file.exists():
        return {"content": [{"type": "text", "text": f"Draft {args['draft_id']} not found."}]}

    with open(draft_file) as f:
        draft = json.load(f)

    if draft["status"] == "SENT":
        return {"content": [{"type": "text", "text": f"Draft {args['draft_id']} was already sent."}]}

    try:
        # Build email
        msg = MIMEMultipart()
        msg["From"] = draft["from"]
        msg["To"] = draft["to"]
        msg["Subject"] = draft["subject"]
        msg.attach(MIMEText(draft["body"], "plain"))

        # Attach files
        for att in draft["attachments"]:
            filepath = Path(att["path"])
            if filepath.exists():
                with open(filepath, "rb") as f:
                    part = MIMEApplication(f.read(), Name=filepath.name)
                part["Content-Disposition"] = f'attachment; filename="{filepath.name}"'
                msg.attach(part)

        # Send via Proton Bridge
        with smtplib.SMTP(PROTON_HOST, PROTON_SMTP) as server:
            server.starttls()
            server.login(PROTON_EMAIL, PROTON_PASS)
            server.sendmail(draft["from"], [draft["to"]], msg.as_string())

        # Update draft status
        draft["status"] = "SENT"
        draft["sent_at"] = datetime.now().isoformat()
        draft["human_approved"] = True
        with open(draft_file, "w") as f:
            json.dump(draft, f, indent=2)

        return {"content": [{"type": "text", "text": json.dumps({
            "status": "SENT SUCCESSFULLY",
            "draft_id": args["draft_id"],
            "to": draft["to"],
            "sent_at": draft["sent_at"],
        }, indent=2)}]}

    except Exception as e:
        draft["status"] = f"SEND_FAILED: {str(e)}"
        with open(draft_file, "w") as f:
            json.dump(draft, f, indent=2)
        return {"content": [{"type": "text", "text": f"SEND FAILED: {str(e)}"}]}


@tool(
    "submission_check_inbox",
    "Check Proton inbox for regulatory responses. Classifies responses by type.",
    {"since_days": int}  # Check emails from last N days
)
async def submission_check_inbox(args):
    try:
        mail = imaplib.IMAP4(PROTON_HOST, PROTON_IMAP)
        mail.starttls()
        mail.login(PROTON_EMAIL, PROTON_PASS)
        mail.select("INBOX")

        # Search for recent emails
        since_date = (datetime.now() - __import__("datetime").timedelta(days=args["since_days"])).strftime("%d-%b-%Y")
        _, message_ids = mail.search(None, f'(SINCE "{since_date}")')

        responses = []
        for msg_id in message_ids[0].split():
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            sender = msg["From"]
            subject = msg["Subject"]

            # Classify response
            classification = "GENERAL"
            sender_lower = sender.lower() if sender else ""
            if "sec.gov" in sender_lower:
                classification = "SEC_RESPONSE"
            elif "usdoj.gov" in sender_lower:
                classification = "DOJ_RESPONSE"
            elif "issgovernance" in sender_lower:
                classification = "ISS_RESPONSE"

            responses.append({
                "from": sender,
                "subject": subject,
                "date": msg["Date"],
                "classification": classification,
            })

        mail.logout()
        return {"content": [{"type": "text", "text": json.dumps({
            "checked_at": datetime.now().isoformat(),
            "since_days": args["since_days"],
            "count": len(responses),
            "responses": responses,
        }, indent=2)}]}

    except Exception as e:
        return {"content": [{"type": "text", "text": f"INBOX CHECK FAILED: {str(e)}"}]}


@tool(
    "submission_log",
    "Get the complete submission log — all drafts, sent items, and responses.",
    {}
)
async def submission_log(args):
    logs = []
    for f in sorted(SUBMISSION_DIR.glob("DRAFT-*.json")):
        with open(f) as fh:
            logs.append(json.load(fh))
    return {"content": [{"type": "text", "text": json.dumps({
        "total_drafts": len(logs),
        "sent": len([l for l in logs if l["status"] == "SENT"]),
        "pending": len([l for l in logs if l["status"] == "PENDING_HUMAN_REVIEW"]),
        "failed": len([l for l in logs if "FAILED" in l["status"]]),
        "submissions": logs,
    }, indent=2)}]}


# ═══════════════════════════════════════════════
# SERVER INITIALIZATION
# ═══════════════════════════════════════════════

server = create_sdk_mcp_server(
    name="submission_mcp",
    version="1.0.0",
    tools=[
        submission_list_targets,
        submission_draft,
        submission_review,
        submission_send,
        submission_check_inbox,
        submission_log,
    ]
)

if __name__ == "__main__":
    server.run()
