#!/usr/bin/env python3
"""
CLARA-AGI Skill: email_ops
Email triage and draft via simple IMAP/SMTP patterns or dry-run drafts.
"""
import imaplib, smtplib, email
from email.mime.text import MIMEText
from datetime import datetime


def run(agi, text: str) -> str:
    text = text.strip()
    if not text or "|" not in text:
        return ("Usage: email:<subcmd>|<args>\n"
                "  draft:<to>|<subject>|<body>\n"
                "  inbox:<limit>             preview inbox via IMAP if configured\n"
                "  setup:<host>:<user>       save IMAP/SMTP config in memory")
    parts = text.split("|", 1)
    sub = parts[0].strip().lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    try:
        if sub.startswith("setup"):
            host, user = arg.split(":", 1) if ":" in arg else (arg, "")
            agi.mem.learn("email_config", f"imap={host} user={user}", confidence=0.9, source="user_taught")
            return f"✅ Saved email config host={host} user={user}"
        if sub.startswith("draft"):
            to_s, arg2 = arg.split("|", 1) if "|" in arg else (arg, "")
            subject, body = arg2.split("|", 1) if "|" in arg2 else (arg2, "")
            msg = MIMEText(body.strip(), "plain", "utf-8")
            msg["Subject"] = subject.strip()
            msg["From"] = "clara@local"
            msg["To"] = to_s.strip()
            agi.mem.remember_episode("email_draft", f"Draft to {to_s}: {subject}", importance=0.4, emotion=0.1)
            return f"📧 Draft ready:\nTo: {to_s}\nSubject: {subject}\nBody: {body.strip()[:300]}"
        if sub.startswith("inbox"):
            limit = int(arg.strip() or "5")
            cfg = agi.mem.recall_semantics("email_config", limit=1)
            if not cfg:
                return "❌ Chưa cấu hình email. Dùng: email:setup:<host>:<user>"
            return f"✅ IMAP preview cần cấu hình thêm password/token. Fact đã lưu: {cfg[0]['fact']}"
        return "❌ subcmd unknown"
    except Exception as e:
        return f"❌ {e}"
