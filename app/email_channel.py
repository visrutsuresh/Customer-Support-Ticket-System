import email
import imaplib
import os
import smtplib
from email.header import decode_header
from email.message import EmailMessage
from email.utils import parseaddr


def _creds():
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")
    if not user or not password:
        raise RuntimeError("EMAIL_USER/EMAIL_PASSWORD missing from .env")
    return user, password


def _decode(value):
    # MIME-encoded subjects arrive in chunks; glue them into one readable string
    out = ""
    for text, charset in decode_header(value or ""):
        out += text.decode(charset or "utf-8", errors="replace") if isinstance(text, bytes) else text
    return out


def _body_text(msg):
    # keep the first plain-text part; ignore HTML and attachments
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(msg.get_content_charset() or "utf-8", errors="replace") if payload else ""


AUTOMATED_SENDERS = ("no-reply", "noreply", "do-not-reply", "donotreply", "mailer-daemon", "postmaster", "notification")


def _is_automated(msg, addr):
    # machine mail: bounce daemons, no-reply senders, bulk/list mail
    local = addr.split("@")[0].lower() if addr else ""
    if any(p in local for p in AUTOMATED_SENDERS):
        return True
    if (msg.get("Auto-Submitted") or "no").lower() != "no":
        return True
    if (msg.get("Precedence") or "").lower() in ("bulk", "list", "junk"):
        return True
    if msg.get("List-Id"):
        return True
    return False


def fetch_unread() -> tuple[list[dict], int]:
    user, password = _creds()
    host = os.getenv("IMAP_HOST", "imap.gmail.com")
    with imaplib.IMAP4_SSL(host) as imap:
        imap.login(user, password)
        imap.select("INBOX")
        _, data = imap.search(None, "UNSEEN")
        tickets, skipped = [], 0
        for num in data[0].split():
            _, msg_data = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            name, addr = parseaddr(msg.get("From", ""))
            if _is_automated(msg, addr):
                skipped += 1
            else:
                tickets.append(
                    {
                        "subject": _decode(msg.get("Subject")) or "(no subject)",
                        "body": _body_text(msg).strip(),
                        "source": "email",
                        "name": name or None,
                        "email": addr or None,
                        "message_id": msg.get("Message-ID"),
                    }
                )
            imap.store(num, "+FLAGS", "\\Seen")  # ponytail: the read-flag IS the dedupe
        return tickets, skipped


def send_email(to: str, subject: str, body: str) -> None:
    user, password = _creds()
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "465"))
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL(host, port) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
