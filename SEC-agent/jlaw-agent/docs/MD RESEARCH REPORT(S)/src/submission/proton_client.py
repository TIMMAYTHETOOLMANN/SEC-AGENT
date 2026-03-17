"""
JLAW Proton Bridge Client
Provides SMTP send and IMAP fetch capabilities via Proton Bridge.
Includes health checks and connection validation.
"""

import smtplib
import imaplib
import email
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class ProtonClient:
    """Client for Proton Bridge SMTP and IMAP operations."""

    def __init__(
        self,
        host: str = None,
        smtp_port: int = None,
        imap_port: int = None,
        email_addr: str = None,
        password: str = None,
    ):
        self.host = host or os.environ.get("PROTON_BRIDGE_HOST", "127.0.0.1")
        self.smtp_port = smtp_port or int(os.environ.get("PROTON_BRIDGE_SMTP_PORT", "1025"))
        self.imap_port = imap_port or int(os.environ.get("PROTON_BRIDGE_IMAP_PORT", "1143"))
        self.email_addr = email_addr or os.environ.get("PROTON_EMAIL", "")
        self.password = password or os.environ.get("PROTON_PASSWORD", "")

    def health_check(self) -> Dict:
        """Check connectivity to Proton Bridge SMTP and IMAP."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "host": self.host,
            "smtp": {"port": self.smtp_port, "status": "UNKNOWN"},
            "imap": {"port": self.imap_port, "status": "UNKNOWN"},
        }

        # Test SMTP
        try:
            with smtplib.SMTP(self.host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.email_addr, self.password)
                results["smtp"]["status"] = "OK"
        except Exception as e:
            results["smtp"]["status"] = f"FAILED: {str(e)}"

        # Test IMAP
        try:
            mail = imaplib.IMAP4(self.host, self.imap_port)
            mail.starttls()
            mail.login(self.email_addr, self.password)
            mail.logout()
            results["imap"]["status"] = "OK"
        except Exception as e:
            results["imap"]["status"] = f"FAILED: {str(e)}"

        results["healthy"] = (
            results["smtp"]["status"] == "OK" and
            results["imap"]["status"] == "OK"
        )
        return results

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: List[Path] = None,
        cc: str = None,
    ) -> Dict:
        """Send an email via Proton Bridge SMTP."""
        msg = MIMEMultipart()
        msg["From"] = self.email_addr
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc

        msg.attach(MIMEText(body, "plain"))

        # Attach files
        attached = []
        for filepath in (attachments or []):
            p = Path(filepath)
            if p.exists():
                with open(p, "rb") as f:
                    part = MIMEApplication(f.read(), Name=p.name)
                part["Content-Disposition"] = f'attachment; filename="{p.name}"'
                msg.attach(part)
                attached.append({"name": p.name, "size_kb": p.stat().st_size // 1024})

        recipients = [to]
        if cc:
            recipients.append(cc)

        try:
            with smtplib.SMTP(self.host, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_addr, self.password)
                server.sendmail(self.email_addr, recipients, msg.as_string())

            return {
                "status": "SENT",
                "to": to,
                "subject": subject,
                "attachments": attached,
                "sent_at": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": str(e),
                "to": to,
                "subject": subject,
            }

    def fetch_inbox(self, since_days: int = 7, folder: str = "INBOX") -> List[Dict]:
        """Fetch recent emails from Proton inbox via IMAP."""
        messages = []
        try:
            mail = imaplib.IMAP4(self.host, self.imap_port)
            mail.starttls()
            mail.login(self.email_addr, self.password)
            mail.select(folder)

            since = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
            _, msg_ids = mail.search(None, f'(SINCE "{since}")')

            for msg_id in msg_ids[0].split():
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                if msg_data[0] is None:
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                messages.append({
                    "from": msg.get("From", ""),
                    "to": msg.get("To", ""),
                    "subject": msg.get("Subject", ""),
                    "date": msg.get("Date", ""),
                    "message_id": msg.get("Message-ID", ""),
                })

            mail.logout()
        except Exception as e:
            return [{"error": str(e)}]

        return messages
