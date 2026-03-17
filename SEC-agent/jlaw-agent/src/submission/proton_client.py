"""
JLAW Proton Bridge Client
Provides SMTP send and IMAP receive via Proton Bridge localhost.

Proton Bridge must be installed and running locally.
SMTP: localhost:1025 (default)
IMAP: localhost:1143 (default)

This client handles:
- Email composition (MIME multipart with attachments)
- TLS connection to Proton Bridge
- Send via SMTP
- Receive/search via IMAP
- Connection health checks

SECURITY: All credentials are loaded from environment variables.
Never hardcode credentials.
"""

import os
import smtplib
import imaplib
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class ProtonBridgeClient:
    """Client for Proton Bridge SMTP/IMAP integration."""

    def __init__(self):
        self.host = os.environ.get("PROTON_BRIDGE_HOST", "127.0.0.1")
        self.smtp_port = int(os.environ.get("PROTON_BRIDGE_SMTP_PORT", "1025"))
        self.imap_port = int(os.environ.get("PROTON_BRIDGE_IMAP_PORT", "1143"))
        self.email_address = os.environ.get("PROTON_EMAIL", "")
        self.password = os.environ.get("PROTON_PASSWORD", "")

    def _validate_config(self):
        """Validate that all required configuration is present."""
        if not self.email_address:
            raise ValueError(
                "PROTON_EMAIL not set. Configure in .env file."
            )
        if not self.password:
            raise ValueError(
                "PROTON_PASSWORD not set. Configure in .env file."
            )

    def check_health(self) -> Dict:
        """
        Check connectivity to Proton Bridge.
        Returns status dict with SMTP and IMAP health.
        """
        result = {
            "host": self.host,
            "smtp_port": self.smtp_port,
            "imap_port": self.imap_port,
            "email": self.email_address[:5] + "***" if self.email_address else "NOT SET",
            "smtp_ok": False,
            "imap_ok": False,
            "checked_at": datetime.now().isoformat(),
        }

        # Test SMTP
        try:
            with smtplib.SMTP(self.host, self.smtp_port, timeout=5) as server:
                server.ehlo()
                result["smtp_ok"] = True
        except Exception as e:
            result["smtp_error"] = str(e)

        # Test IMAP
        try:
            mail = imaplib.IMAP4(self.host, self.imap_port)
            mail.logout()
            result["imap_ok"] = True
        except Exception as e:
            result["imap_error"] = str(e)

        return result

    def send_email(self, to_email: str, subject: str, body: str,
                   attachment_paths: List[str] = None,
                   cc: str = None, bcc: str = None) -> Dict:
        """
        Send an email via Proton Bridge SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            body: Plain text email body
            attachment_paths: List of file paths to attach
            cc: CC recipient(s)
            bcc: BCC recipient(s)

        Returns:
            Dict with send result metadata

        Raises:
            ValueError: If configuration is missing
            smtplib.SMTPException: If send fails
        """
        self._validate_config()

        # Build MIME message
        msg = MIMEMultipart()
        msg["From"] = self.email_address
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)

        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc

        # Body
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Attachments
        attached_files = []
        for path_str in (attachment_paths or []):
            filepath = Path(path_str)
            if filepath.exists():
                with open(filepath, "rb") as f:
                    part = MIMEApplication(f.read(), Name=filepath.name)
                part["Content-Disposition"] = f'attachment; filename="{filepath.name}"'
                msg.attach(part)
                attached_files.append({
                    "name": filepath.name,
                    "size_bytes": filepath.stat().st_size,
                })

        # Collect all recipients
        recipients = [to_email]
        if cc:
            recipients.extend(cc.split(","))
        if bcc:
            recipients.extend(bcc.split(","))

        # Send
        with smtplib.SMTP(self.host, self.smtp_port) as server:
            server.starttls()
            server.login(self.email_address, self.password)
            server.sendmail(self.email_address, recipients, msg.as_string())

        return {
            "status": "SENT",
            "from": self.email_address,
            "to": to_email,
            "subject": subject,
            "attachments": attached_files,
            "sent_at": datetime.now().isoformat(),
        }

    def fetch_inbox(self, since_days: int = 7, folder: str = "INBOX") -> List[Dict]:
        """
        Fetch emails from Proton inbox via IMAP.

        Args:
            since_days: Fetch emails from last N days
            folder: IMAP folder to search

        Returns:
            List of email metadata dicts
        """
        self._validate_config()

        mail = imaplib.IMAP4(self.host, self.imap_port)
        try:
            mail.starttls()
            mail.login(self.email_address, self.password)
            mail.select(folder)

            since_date = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
            _, message_ids = mail.search(None, f'(SINCE "{since_date}")')

            messages = []
            for msg_id in message_ids[0].split():
                if not msg_id:
                    continue
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                if msg_data and msg_data[0] and isinstance(msg_data[0], tuple):
                    msg = email.message_from_bytes(msg_data[0][1])
                    messages.append({
                        "message_id": msg.get("Message-ID", ""),
                        "from": msg.get("From", ""),
                        "to": msg.get("To", ""),
                        "subject": msg.get("Subject", ""),
                        "date": msg.get("Date", ""),
                        "has_attachments": msg.is_multipart(),
                    })

            return messages
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    def fetch_sent(self, since_days: int = 30) -> List[Dict]:
        """Fetch sent items for audit trail."""
        return self.fetch_inbox(since_days, folder="Sent")
