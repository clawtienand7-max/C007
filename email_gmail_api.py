#!/usr/bin/env python3
"""
email_gmail_api.py — Gmail via Google API (HTTPS port 443)
Works in cloud/sandboxed environments where SMTP/IMAP ports are blocked.

Setup: python3 email_gmail_api.py setup
       Follow the URL shown → paste the auth code back
"""

import os, sys, json, base64, textwrap, argparse
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Google API
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BASE_DIR    = Path(__file__).parent
TOKEN_FILE  = BASE_DIR / "gmail_token.json"
CREDS_FILE  = BASE_DIR / "gmail_credentials.json"
SCOPES      = ["https://mail.google.com/"]


# ── Auth ──────────────────────────────────────────────────────────────────────
def get_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                print("❌ gmail_credentials.json not found.")
                print("   Run:  python3 email_gmail_api.py setup")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDS_FILE), SCOPES,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob"
            )
            auth_url, _ = flow.authorization_url(prompt="consent")
            print("\n" + "═"*60)
            print("請在瀏覽器打開以下網址：")
            print()
            print(auth_url)
            print()
            print("登入後，複製網頁顯示的授權碼，貼到下方：")
            print("═"*60)
            code = input("授權碼: ").strip()
            flow.fetch_token(code=code)
            creds = flow.credentials
        TOKEN_FILE.write_text(creds.to_json())
        os.chmod(TOKEN_FILE, 0o600)
    return build("gmail", "v1", credentials=creds)


def get_my_email(service) -> str:
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def encode_message(msg) -> dict:
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def decode_b64(s: str) -> str:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s).decode("utf-8", errors="replace")


def parse_headers(hdrs: list, name: str) -> str:
    for h in hdrs:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def get_body_from_payload(payload) -> str:
    def extract(part):
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            data = part.get("body", {}).get("data", "")
            return decode_b64(data) if data else ""
        if mime == "text/html" and not part.get("parts"):
            data = part.get("body", {}).get("data", "")
            return "[HTML]\n" + decode_b64(data) if data else ""
        if "parts" in part:
            for p in part["parts"]:
                result = extract(p)
                if result:
                    return result
        return ""
    return extract(payload)


# ── Commands ──────────────────────────────────────────────────────────────────
def cmd_setup(args):
    print("\n⚙️  Gmail API Setup")
    print("─"*50)
    if CREDS_FILE.exists():
        print(f"✅ 已找到 {CREDS_FILE.name}")
        print("   測試連線中...")
        try:
            svc = get_service()
            email = get_my_email(svc)
            print(f"✅ 成功連線！已登入帳號：{email}")
        except Exception as e:
            print(f"❌ 連線失敗：{e}")
    else:
        print(f"❌ 找不到 {CREDS_FILE.name}")
        print()
        print("請按以下步驟操作：")
        print("  1. 前往 console.cloud.google.com")
        print("  2. 建立專案 → 啟用 Gmail API")
        print("  3. 建立 OAuth 2.0 憑證 → 下載 JSON")
        print(f"  4. 將下載的 JSON 重命名為 gmail_credentials.json")
        print(f"     放入目錄：{BASE_DIR}")
        print()
        print("詳細圖解請參考 guides/02_gmail_api_setup.png")


def cmd_send(args):
    service = get_service()
    me = get_my_email(service)

    msg = MIMEMultipart()
    msg["From"]    = me
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

    service.users().messages().send(
        userId="me", body=encode_message(msg)
    ).execute()
    print(f"✅ 電郵已發送至 {args.to}")


def cmd_list(args):
    service = get_service()
    q = args.search or ""
    if args.unread: q = ("LABEL:UNREAD " + q).strip()

    result = service.users().messages().list(
        userId="me", labelIds=[args.folder or "INBOX"],
        maxResults=args.limit or 20, q=q
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        print("📭 收件箱沒有郵件。")
        return []

    rows = []
    for m in messages:
        msg = service.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["From","Subject","Date"]
        ).execute()
        hdrs = msg["payload"]["headers"]
        rows.append({
            "id":      m["id"],
            "from":    parse_headers(hdrs, "From"),
            "subject": parse_headers(hdrs, "Subject"),
            "date":    parse_headers(hdrs, "Date"),
        })

    print(f"\n📬 {args.folder or 'INBOX'} — {len(rows)} 封郵件\n")
    print(f"{'ID':<20} {'日期':<28} {'寄件人':<35} 主題")
    print("─" * 105)
    for r in rows:
        print(f"{r['id'][:18]:<20} {r['date'][:25]:<28} {r['from'][:33]:<35} {r['subject'][:45]}")
    return rows


def cmd_read(args):
    service = get_service()
    msg = service.users().messages().get(
        userId="me", id=args.id, format="full"
    ).execute()
    hdrs = msg["payload"]["headers"]
    body = get_body_from_payload(msg["payload"])

    print(f"\n{'─'*60}")
    print(f"寄件人  : {parse_headers(hdrs,'From')}")
    print(f"收件人  : {parse_headers(hdrs,'To')}")
    cc = parse_headers(hdrs,'Cc')
    if cc: print(f"副本    : {cc}")
    print(f"主題    : {parse_headers(hdrs,'Subject')}")
    print(f"日期    : {parse_headers(hdrs,'Date')}")
    print(f"{'─'*60}")
    print(textwrap.fill(body.strip(), width=80))
    print(f"{'─'*60}\n")


def cmd_reply(args):
    service = get_service()
    me = get_my_email(service)

    orig = service.users().messages().get(
        userId="me", id=args.id, format="full"
    ).execute()
    hdrs = orig["payload"]["headers"]
    orig_from    = parse_headers(hdrs, "From")
    orig_subject = parse_headers(hdrs, "Subject")
    orig_body    = get_body_from_payload(orig["payload"])
    orig_msgid   = parse_headers(hdrs, "Message-ID")
    thread_id    = orig.get("threadId")

    subject = orig_subject if orig_subject.lower().startswith("re:") \
              else "Re: " + orig_subject
    quoted  = "\n".join(f"> {l}" for l in orig_body.splitlines())
    body    = (args.body or "") + f"\n\n--- 原始郵件 ---\n{quoted}"

    msg = MIMEMultipart()
    msg["From"]        = me
    msg["To"]          = orig_from
    msg["Subject"]     = subject
    msg["In-Reply-To"] = orig_msgid
    msg["References"]  = orig_msgid
    msg.attach(MIMEText(body, "plain", "utf-8"))

    raw = encode_message(msg)
    raw["threadId"] = thread_id
    service.users().messages().send(userId="me", body=raw).execute()
    print(f"✅ 回覆已發送至 {orig_from}")


def cmd_search(args):
    q_parts = []
    if args.from_addr: q_parts.append(f"from:{args.from_addr}")
    if args.subject:   q_parts.append(f"subject:{args.subject}")
    if args.since:     q_parts.append(f"after:{args.since}")
    if args.body:      q_parts.append(args.body)
    if args.unread:    q_parts.append("is:unread")

    class FA:
        folder = args.folder or "INBOX"
        limit  = args.limit or 20
        search = " ".join(q_parts)
        unread = False
    cmd_list(FA())


def cmd_delete(args):
    service = get_service()
    service.users().messages().trash(userId="me", id=args.id).execute()
    print(f"🗑️  郵件 {args.id} 已移至垃圾桶。")


def cmd_folders(args):
    service = get_service()
    result = service.users().labels().list(userId="me").execute()
    print("\n📁 Gmail 標籤/資料夾：")
    for lbl in result.get("labels", []):
        print(f"  {lbl['name']}")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(prog="email_gmail_api",
        description="Gmail API Email Tool (HTTPS only — works in cloud)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="設定 Gmail API 憑證 / 測試連線")

    s = sub.add_parser("send")
    s.add_argument("--to",        required=True)
    s.add_argument("--subject",   required=True)
    s.add_argument("--body",      default="")
    s.add_argument("--body-file", dest="body_file")
    s.add_argument("--cc"); s.add_argument("--bcc")
    s.add_argument("--attach", nargs="*")
    s.add_argument("--html", action="store_true")

    l = sub.add_parser("list")
    l.add_argument("--folder",  default="INBOX")
    l.add_argument("--limit",   type=int, default=20)
    l.add_argument("--search",  default="")
    l.add_argument("--unread",  action="store_true")

    r = sub.add_parser("read")
    r.add_argument("id")

    rp = sub.add_parser("reply")
    rp.add_argument("id")
    rp.add_argument("--body", required=True)

    sr = sub.add_parser("search")
    sr.add_argument("--from-addr", dest="from_addr")
    sr.add_argument("--subject")
    sr.add_argument("--body")
    sr.add_argument("--since")
    sr.add_argument("--unread", action="store_true")
    sr.add_argument("--folder", default="INBOX")
    sr.add_argument("--limit",  type=int, default=20)

    d = sub.add_parser("delete"); d.add_argument("id")
    sub.add_parser("folders")

    args = p.parse_args()
    dispatch = {
        "setup":   cmd_setup,
        "send":    cmd_send,
        "list":    cmd_list,
        "read":    cmd_read,
        "reply":   cmd_reply,
        "search":  cmd_search,
        "delete":  cmd_delete,
        "folders": cmd_folders,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
