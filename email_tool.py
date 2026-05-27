#!/usr/bin/env python3
"""
email_tool.py — Claude Code Email Skill Backend
Supports: send, list, read, reply, search, delete
Config:   EMAIL_USER, EMAIL_PASS, EMAIL_SMTP, EMAIL_IMAP env vars
          or email_config.json in same directory
"""

import os
import sys
import json
import smtplib
import imaplib
import email as emaillib
import argparse
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.header import decode_header
from datetime import datetime
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / "email_config.json"

# ── Provider presets ──────────────────────────────────────────────────────────
PROVIDERS = {
    "gmail":   {"smtp": "smtp.gmail.com",   "smtp_port": 587, "imap": "imap.gmail.com",   "imap_port": 993},
    "outlook": {"smtp": "smtp.office365.com","smtp_port": 587, "imap": "outlook.office365.com","imap_port": 993},
    "yahoo":   {"smtp": "smtp.mail.yahoo.com","smtp_port": 587,"imap": "imap.mail.yahoo.com","imap_port": 993},
    "icloud":  {"smtp": "smtp.mail.me.com",  "smtp_port": 587, "imap": "imap.mail.me.com",  "imap_port": 993},
}


# ── Config loading ────────────────────────────────────────────────────────────
def load_config() -> dict:
    cfg = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    cfg["user"]      = os.getenv("EMAIL_USER",     cfg.get("user", ""))
    cfg["password"]  = os.getenv("EMAIL_PASS",     cfg.get("password", ""))
    cfg["smtp_host"] = os.getenv("EMAIL_SMTP",     cfg.get("smtp_host", ""))
    cfg["imap_host"] = os.getenv("EMAIL_IMAP",     cfg.get("imap_host", ""))
    cfg["smtp_port"] = int(os.getenv("EMAIL_SMTP_PORT", cfg.get("smtp_port", 587)))
    cfg["imap_port"] = int(os.getenv("EMAIL_IMAP_PORT", cfg.get("imap_port", 993)))

    # Auto-detect provider from email domain
    if cfg["user"] and not cfg["smtp_host"]:
        domain = cfg["user"].split("@")[-1].lower()
        for name, preset in PROVIDERS.items():
            if name in domain:
                cfg["smtp_host"] = preset["smtp"]
                cfg["smtp_port"] = preset["smtp_port"]
                cfg["imap_host"] = preset["imap"]
                cfg["imap_port"] = preset["imap_port"]
                break
    return cfg


def save_config(user: str, password: str, provider: str = None,
                smtp: str = None, imap: str = None):
    cfg = {"user": user, "password": password}
    if provider and provider in PROVIDERS:
        p = PROVIDERS[provider]
        cfg["smtp_host"] = p["smtp"]
        cfg["smtp_port"] = p["smtp_port"]
        cfg["imap_host"] = p["imap"]
        cfg["imap_port"] = p["imap_port"]
    else:
        if smtp: cfg["smtp_host"] = smtp
        if imap: cfg["imap_host"] = imap
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)
    print(f"✅ Config saved to {CONFIG_FILE}")


# ── Helpers ───────────────────────────────────────────────────────────────────
def decode_str(s) -> str:
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def get_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                return part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace")
        # fallback: html
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/html" and "attachment" not in cd:
                return "[HTML]\n" + part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace")
    else:
        return msg.get_payload(decode=True).decode(
            msg.get_content_charset() or "utf-8", errors="replace")
    return ""


def imap_connect(cfg: dict):
    mail = imaplib.IMAP4_SSL(cfg["imap_host"], cfg["imap_port"])
    mail.login(cfg["user"], cfg["password"])
    return mail


def smtp_connect(cfg: dict):
    server = smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"])
    server.ehlo()
    server.starttls()
    server.login(cfg["user"], cfg["password"])
    return server


# ── Commands ──────────────────────────────────────────────────────────────────
def cmd_send(args, cfg):
    msg = MIMEMultipart()
    msg["From"]    = cfg["user"]
    msg["To"]      = args.to
    msg["Subject"] = args.subject
    if args.cc:  msg["Cc"]  = args.cc
    if args.bcc: msg["Bcc"] = args.bcc

    body = args.body or ""
    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    msg.attach(MIMEText(body, "html" if args.html else "plain", "utf-8"))

    for fpath in (args.attach or []):
        p = Path(fpath)
        part = MIMEBase("application", "octet-stream")
        part.set_payload(p.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{p.name}"')
        msg.attach(part)

    recipients = [args.to]
    if args.cc:  recipients += [a.strip() for a in args.cc.split(",")]
    if args.bcc: recipients += [a.strip() for a in args.bcc.split(",")]

    server = smtp_connect(cfg)
    server.sendmail(cfg["user"], recipients, msg.as_string())
    server.quit()
    print(f"✅ Email sent to {args.to}")
    return {"status": "sent", "to": args.to, "subject": args.subject}


def cmd_list(args, cfg):
    mail = imap_connect(cfg)
    folder = args.folder or "INBOX"
    mail.select(folder)

    search = args.search or "ALL"
    _, data = mail.search(None, search)
    ids = data[0].split()
    if not ids:
        print("📭 No messages found.")
        mail.logout()
        return []

    # Most recent first, limit
    ids = ids[-args.limit:][::-1]
    results = []
    for uid in ids:
        _, msg_data = mail.fetch(uid, "(RFC822.SIZE RFC822.HEADER)")
        raw = msg_data[0][1]
        msg = emaillib.message_from_bytes(raw)
        results.append({
            "id":      uid.decode(),
            "from":    decode_str(msg.get("From")),
            "to":      decode_str(msg.get("To")),
            "subject": decode_str(msg.get("Subject")),
            "date":    msg.get("Date", ""),
        })

    mail.logout()
    print(f"\n📬 {folder} — {len(results)} message(s)\n")
    print(f"{'ID':<6} {'Date':<28} {'From':<35} Subject")
    print("─" * 100)
    for m in results:
        date_str = m["date"][:25] if m["date"] else "—"
        from_str = m["from"][:33]
        subj_str = m["subject"][:50]
        print(f"{m['id']:<6} {date_str:<28} {from_str:<35} {subj_str}")
    return results


def cmd_read(args, cfg):
    mail = imap_connect(cfg)
    folder = args.folder or "INBOX"
    mail.select(folder)
    _, msg_data = mail.fetch(args.id, "(RFC822)")
    mail.logout()

    raw = msg_data[0][1]
    msg = emaillib.message_from_bytes(raw)
    body = get_body(msg)

    info = {
        "id":      args.id,
        "from":    decode_str(msg.get("From")),
        "to":      decode_str(msg.get("To")),
        "cc":      decode_str(msg.get("Cc")),
        "subject": decode_str(msg.get("Subject")),
        "date":    msg.get("Date", ""),
        "body":    body,
    }

    print(f"\n{'─'*60}")
    print(f"From    : {info['from']}")
    print(f"To      : {info['to']}")
    if info["cc"]: print(f"CC      : {info['cc']}")
    print(f"Subject : {info['subject']}")
    print(f"Date    : {info['date']}")
    print(f"{'─'*60}")
    print(textwrap.fill(body.strip(), width=80))
    print(f"{'─'*60}\n")
    return info


def cmd_reply(args, cfg):
    # Read original
    mail = imap_connect(cfg)
    folder = args.folder or "INBOX"
    mail.select(folder)
    _, msg_data = mail.fetch(args.id, "(RFC822)")
    mail.logout()

    orig = emaillib.message_from_bytes(msg_data[0][1])
    orig_from    = decode_str(orig.get("From"))
    orig_subject = decode_str(orig.get("Subject"))
    orig_body    = get_body(orig)
    orig_msgid   = orig.get("Message-ID", "")

    reply_to = orig_from
    subject  = orig_subject if orig_subject.lower().startswith("re:") \
               else "Re: " + orig_subject

    quoted = "\n".join(f"> {line}" for line in orig_body.splitlines())
    body = (args.body or "") + f"\n\n--- Original ---\n{quoted}"

    msg = MIMEMultipart()
    msg["From"]       = cfg["user"]
    msg["To"]         = reply_to
    msg["Subject"]    = subject
    msg["In-Reply-To"]= orig_msgid
    msg["References"] = orig_msgid
    msg.attach(MIMEText(body, "plain", "utf-8"))

    server = smtp_connect(cfg)
    server.sendmail(cfg["user"], [reply_to], msg.as_string())
    server.quit()
    print(f"✅ Reply sent to {reply_to}")
    return {"status": "replied", "to": reply_to, "subject": subject}


def cmd_search(args, cfg):
    mail = imap_connect(cfg)
    mail.select(args.folder or "INBOX")

    criteria = []
    if args.from_addr: criteria.append(f'FROM "{args.from_addr}"')
    if args.subject:   criteria.append(f'SUBJECT "{args.subject}"')
    if args.since:     criteria.append(f'SINCE "{args.since}"')
    if args.body:      criteria.append(f'BODY "{args.body}"')
    if args.unread:    criteria.append("UNSEEN")
    query = " ".join(criteria) if criteria else "ALL"

    _, data = mail.search(None, query)
    ids = data[0].split()
    mail.logout()

    if not ids:
        print(f"🔍 No results for: {query}")
        return []

    # Reuse list with found IDs
    class FakeArgs:
        folder = args.folder or "INBOX"
        limit  = min(len(ids), args.limit or 20)
        search = query
    return cmd_list(FakeArgs(), cfg)


def cmd_delete(args, cfg):
    mail = imap_connect(cfg)
    mail.select(args.folder or "INBOX")
    mail.store(args.id, "+FLAGS", "\\Deleted")
    mail.expunge()
    mail.logout()
    print(f"🗑️  Message {args.id} deleted.")
    return {"status": "deleted", "id": args.id}


def cmd_folders(args, cfg):
    mail = imap_connect(cfg)
    _, folders = mail.list()
    mail.logout()
    print("\n📁 Available folders:")
    for f in folders:
        parts = f.decode().split('"/"')
        name = parts[-1].strip().strip('"')
        print(f"  {name}")


def cmd_setup(args, cfg):
    print("\n⚙️  Email Tool Setup")
    print("─" * 40)
    user     = input("Email address: ").strip()
    password = input("App password (Gmail: 16-char app pwd): ").strip()

    print("\nProviders: gmail, outlook, yahoo, icloud, custom")
    provider = input("Provider [gmail]: ").strip() or "gmail"

    if provider == "custom":
        smtp = input("SMTP host: ").strip()
        imap = input("IMAP host: ").strip()
        save_config(user, password, smtp=smtp, imap=imap)
    else:
        save_config(user, password, provider=provider)

    # Test connection
    try:
        cfg = load_config()
        s = smtp_connect(cfg)
        s.quit()
        print("✅ SMTP connection OK")
        m = imap_connect(cfg)
        m.logout()
        print("✅ IMAP connection OK")
    except Exception as e:
        print(f"⚠️  Connection test failed: {e}")
        print("   Check credentials and ensure App Password is used for Gmail.")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="email_tool",
        description="Claude Code Email Tool — send, receive, search emails"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # setup
    sub.add_parser("setup", help="Configure email credentials")

    # send
    s = sub.add_parser("send", help="Send an email")
    s.add_argument("--to",        required=True)
    s.add_argument("--subject",   required=True)
    s.add_argument("--body",      default="")
    s.add_argument("--body-file", dest="body_file")
    s.add_argument("--cc")
    s.add_argument("--bcc")
    s.add_argument("--attach",    nargs="*")
    s.add_argument("--html",      action="store_true")

    # list
    l = sub.add_parser("list", help="List emails")
    l.add_argument("--folder",  default="INBOX")
    l.add_argument("--limit",   type=int, default=20)
    l.add_argument("--search",  default="ALL",
                   help='IMAP search, e.g. "UNSEEN" or "FROM someone@x.com"')

    # read
    r = sub.add_parser("read", help="Read an email by ID")
    r.add_argument("id")
    r.add_argument("--folder", default="INBOX")

    # reply
    rp = sub.add_parser("reply", help="Reply to an email")
    rp.add_argument("id")
    rp.add_argument("--body",   required=True)
    rp.add_argument("--folder", default="INBOX")

    # search
    sr = sub.add_parser("search", help="Search emails")
    sr.add_argument("--from-addr", dest="from_addr")
    sr.add_argument("--subject")
    sr.add_argument("--body")
    sr.add_argument("--since",  help="e.g. 01-Jan-2026")
    sr.add_argument("--unread", action="store_true")
    sr.add_argument("--folder", default="INBOX")
    sr.add_argument("--limit",  type=int, default=20)

    # delete
    d = sub.add_parser("delete", help="Delete an email by ID")
    d.add_argument("id")
    d.add_argument("--folder", default="INBOX")

    # folders
    sub.add_parser("folders", help="List all folders/labels")

    args = parser.parse_args()
    cfg  = load_config()

    if args.command == "setup":
        cmd_setup(args, cfg)
        return

    if not cfg.get("user") or not cfg.get("password"):
        print("❌ No credentials found. Run:  python3 email_tool.py setup")
        sys.exit(1)

    dispatch = {
        "send":    cmd_send,
        "list":    cmd_list,
        "read":    cmd_read,
        "reply":   cmd_reply,
        "search":  cmd_search,
        "delete":  cmd_delete,
        "folders": cmd_folders,
    }
    dispatch[args.command](args, cfg)


if __name__ == "__main__":
    main()
