#!/usr/bin/env python3
"""
complaint_tracker.py — 跟蹤政府投訴回覆 + 定期查核改善進度
用法：PYTHONPATH=/tmp/gauth python3 complaint_tracker.py [--check-progress]
"""
import os, sys, json, base64, re, argparse
from datetime import datetime, timezone
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, '/tmp/gauth')
BASE_DIR = Path(__file__).parent
LOG_FILE  = BASE_DIR / "complaint_log.json"
SENT_DATE = "2026-05-26"
MY_EMAIL  = "clawtienand7@gmail.com"

# 自動回覆關鍵字（偵測到這些字詞則視為自動確認，非實質回覆）
AUTO_REPLY_PATTERNS = [
    "automatic reply", "auto reply", "auto-reply",
    "acknowledged receipt", "acknowledgement",
    "this is an automatic", "這是電子", "自動回覆", "備悉",
    "we shall reply", "we will reply", "會盡快作出回覆",
]

# ── 升級收件人清單 ─────────────────────────────────────────────────────────────
ESCALATION_LEVELS = [
    {
        "level": 1,
        "label": "第一層追催：運輸及物流局 ＋ 運輸署",
        "to": "enquiry@tlb.gov.hk",
        "cc": ["td@td.gov.hk"],
        "days_wait": 28,
    },
    {
        "level": 2,
        "label": "第二層升級：副本立法會交通事務委員會",
        "to": "enquiry@tlb.gov.hk",
        "cc": ["td@td.gov.hk", "info@legco.gov.hk"],
        "days_wait": 14,
    },
    {
        "level": 3,
        "label": "最終升級：副本 1823 市民投訴中心",
        "to": "enquiry@tlb.gov.hk",
        "cc": ["td@td.gov.hk", "info@legco.gov.hk", "cm@1823.gov.hk"],
        "days_wait": 7,
    },
]


# ── 投訴信正文（逐級加強）─────────────────────────────────────────────────────
def build_body(level: int, today_str: str) -> tuple:
    stats = """
【統計數據與事實根據】
  • 全港登記電單車逾 30 萬輛，十年間增約 35%
  • 每年電單車違泊罰款通知書逾 10 萬張，年度罰款收入估逾 3,200 萬元
  • 電單車佔用路面空間僅私家車約十分之一，惟罰款金額完全相同（$320）
  • 新加坡、台灣等地均設有獨立電單車泊位政策及差別罰款制度
  • 多份區議會文件及本港主流傳媒均記錄泊位不足問題逾十年"""

    demands = """
【要求當局正式書面答覆以下問題】
  1. 未來三年新增合法電單車泊位之具體數目及選址計劃
  2. 是否承諾檢討電單車違泊罰款，訂立獨立合理級別
  3. 過去三個財政年度電單車違泊罰款收入確實金額及用途分項
  4. 是否設立機制將部分罰款收入專款用於增設電單車泊位"""

    if level == 1:
        subject = "【第一次追催】正式投訴：電單車泊位不足及罰款不公平——原函逾期未獲實質回覆"
        intro = f"""本人已於 {SENT_DATE} 向  貴局發出正式投訴函，雖收到貴局系統自動確認收件，
惟至今逾期未獲任何實質回覆，亦未有官員就本人所提問題作出任何說明。

根據《公開資料守則》，政府部門應於二十一個工作天內作出實質回應。
本人現發出第一次追催，並已副本抄送運輸署，要求兩個部門共同跟進。"""
        deadline = "本人要求於收到本函後十四個工作天內給予書面回覆，否則將進一步升級至立法會。"
        footer = "（本函已副本抄送：運輸署 td@td.gov.hk）"

    elif level == 2:
        subject = "【升級投訴 — 副本立法會】電單車泊位不足問題：兩次投訴均未獲實質回覆"
        intro = f"""本人自 {SENT_DATE} 起已兩度就電單車泊位嚴重不足及罰款不公平問題向  貴局提出
正式投訴，惟均未獲任何實質回應。此等漠視市民投訴之態度，令本人深感遺憾。

本人現正式升級投訴，並已副本抄送立法會交通事務委員會，
要求議員就此問題向政府提出質詢。本人亦保留向申訴專員公署提出投訴之權利。"""
        deadline = "本人要求於七個工作天內給予正式書面回覆，否則將向申訴專員公署提出投訴並考慮聯絡傳媒。"
        footer = "（本函已副本抄送：運輸署、立法會交通事務委員會）"

    elif level >= 3:
        subject = "【最終升級投訴 — 要求問責】電單車泊位不足問題：三次投訴均無回應"
        intro = f"""本人自 {SENT_DATE} 起已三度就電單車泊位嚴重不足、罰款標準不公平及
罰款收入透明度問題提出正式投訴，歷時逾兩個月，至今仍未獲任何實質回覆，
此乃嚴重行政失當。

本人現發出最終升級投訴，並已副本抄送立法會及 1823 市民投訴中心。
本人已就此事向申訴專員公署提出正式投訴，
並已準備就政府長期漠視電單車車主訴求一事聯絡傳媒作出報道。"""
        deadline = """本人要求：
  • 局長或副局長親自就此事作出書面回應
  • 回應時限：五個工作天
  • 若逾期，本人將公開此事並啟動法律程序"""
        footer = "（本函已副本抄送：運輸署、立法會交通事務委員會、1823 市民投訴中心）"

    body = f"""運輸及物流局局長 閣下：

{intro}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
投訴事項摘要
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

一、電單車泊位嚴重不足，多年未獲改善

全港登記電單車逾 30 萬輛，惟合法泊位供應長期嚴重滯後。大量車主被迫
在無合法泊位可用的情況下違泊遭罰，此乃制度性問題，責任在於政府
未能提供足夠設施，而非車主蓄意違規。

二、電單車違泊罰款與私家車劃一，違反比例原則

現行罰款每張 320 元，電單車與私家車完全相同。然電單車佔用路面空間
僅為私家車約十分之一，且合法泊位嚴重不足，此一刀切標準明顯有欠公允，
違反比例原則，亦有違《基本法》平等保護精神。

三、罰款收入缺乏透明度，未見用於改善相關設施

每年電單車違泊罰款收入估計逾 3,200 萬元，惟政府從未就此收入用途
作出公開交代，亦無任何機制將收入用於解決泊位不足根源，
疑涉公共資源錯配，有違公眾利益。

{stats}

{demands}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{deadline}

此致

Tien 先生（香港電單車車主）
電郵：{MY_EMAIL}
日期：{today_str}

{footer}"""
    return subject, body


# ── 工具函數 ─────────────────────────────────────────────────────────────────
def encode_msg(msg) -> dict:
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def send_email(service, to: str, cc_list: list, subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"]    = MY_EMAIL
    msg["To"]      = to
    msg["Subject"] = subject
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    service.users().messages().send(
        userId="me", body=encode_msg(msg)
    ).execute()


def load_log() -> dict:
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text())
    return {
        "sent_escalations": [],
        "replied": False,
        "reply_date": None,
        "auto_acknowledged": False,
        "acknowledged_date": None,
        "progress_checks": [],
    }


def save_log(log: dict):
    LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2))


def is_auto_reply(body_text: str) -> bool:
    body_lower = body_text.lower()
    return any(p.lower() in body_lower for p in AUTO_REPLY_PATTERNS)


def check_for_replies(service) -> tuple:
    """返回 (has_real_reply, has_auto_ack)"""
    result = service.users().messages().list(
        userId="me",
        q='from:(tlb.gov.hk OR td.gov.hk OR legco.gov.hk OR 1823.gov.hk)',
        maxResults=10
    ).execute()
    msgs = result.get("messages", [])

    has_real, has_auto = False, False
    for m in msgs:
        detail = service.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()
        hdrs = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        subj = hdrs.get("Subject", "")
        # only check replies related to our complaint
        if "電單車" not in subj and "motorcycle" not in subj.lower():
            continue
        # get body
        body_text = ""
        payload = detail.get("payload", {})
        if payload.get("body", {}).get("data"):
            body_text = base64.urlsafe_b64decode(
                payload["body"]["data"] + "=="
            ).decode("utf-8", errors="replace")
        elif payload.get("parts"):
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                    body_text = base64.urlsafe_b64decode(
                        part["body"]["data"] + "=="
                    ).decode("utf-8", errors="replace")
                    break
        if is_auto_reply(body_text):
            has_auto = True
        else:
            has_real = True
    return has_real, has_auto


def days_since(date_str: str) -> int:
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - d).days


# ── 進度查核 ─────────────────────────────────────────────────────────────────
def run_progress_check(service, log: dict):
    """搜尋政府有關電單車泊位改善的最新通告或新聞。"""
    print("\n🔍 查核政府電單車泊位改善進度…")
    # 搜尋來自政府部門的最新通告
    result = service.users().messages().list(
        userId="me",
        q='from:(gov.hk) (電單車 OR motorcycle) (泊位 OR parking)',
        maxResults=5
    ).execute()
    msgs = result.get("messages", [])
    if msgs:
        print(f"   找到 {len(msgs)} 封相關政府郵件：")
        for m in msgs:
            detail = service.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            hdrs = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            print(f"   • [{hdrs.get('Date','?')}] {hdrs.get('From','?')}")
            print(f"     主題：{hdrs.get('Subject','?')}")
    else:
        print("   未找到政府泊位改善相關通知。")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log.setdefault("progress_checks", []).append({
        "date": today,
        "gov_emails_found": len(msgs),
        "note": f"定期查核，找到 {len(msgs)} 封相關政府郵件",
    })
    save_log(log)
    print(f"   📁 進度記錄已更新（{today}）")


# ── 主程式 ───────────────────────────────────────────────────────────────────
def run_check(check_progress=False):
    import email_gmail_api as api

    today     = datetime.now(timezone.utc)
    today_str = today.strftime("%Y 年 %m 月 %d 日")
    log       = load_log()
    service   = api.get_service()

    print(f"\n{'='*60}")
    print(f"📋 投訴跟蹤報告 — {today.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")
    print(f"   原始發送日期 : {SENT_DATE}")
    print(f"   距今天數     : {days_since(SENT_DATE)} 天")

    ack = log.get("auto_acknowledged")
    print(f"   政府確認收件 : {'✅ ' + log.get('acknowledged_date','') if ack else '❌ 未收到'}")
    print(f"   實質回覆     : {'✅ ' + log.get('reply_date','') if log.get('replied') else '❌ 未收到'}")
    print(f"   已升級次數   : {len(log.get('sent_escalations', []))} 次")
    print(f"{'='*60}")

    if log.get("replied"):
        print("✅ 政府已作出實質回覆，投訴已完結。")
        if check_progress:
            run_progress_check(service, log)
        return

    # 檢查有否新回覆
    has_real, has_auto = check_for_replies(service)
    if has_real:
        log["replied"] = True
        log["reply_date"] = today.strftime("%Y-%m-%d")
        save_log(log)
        print("\n🎉 偵測到政府實質回覆！投訴已完結，請查閱收件箱。")
        return
    if has_auto and not ack:
        log["auto_acknowledged"] = True
        log["acknowledged_date"] = today.strftime("%Y-%m-%d")
        save_log(log)
        print("\n📩 偵測到政府自動確認收件（非實質回覆），繼續追蹤。")

    # 計算升級時機
    sent_count = len(log.get("sent_escalations", []))
    if sent_count >= len(ESCALATION_LEVELS):
        print("\n⚠️  已完成所有升級層級。")
        print("   建議：向申訴專員公署正式投訴：https://www.ombudsman.hk")
        if check_progress:
            run_progress_check(service, log)
        return

    lvl = ESCALATION_LEVELS[sent_count]
    last_date = (
        log["sent_escalations"][-1]["date"]
        if log["sent_escalations"]
        else SENT_DATE
    )
    days_waited = days_since(last_date)
    days_needed = lvl["days_wait"]

    print(f"\n   下一升級層級 : {lvl['label']}")
    print(f"   等待天數     : {days_waited} 天 / {days_needed} 天")

    if days_waited >= days_needed:
        print(f"\n📤 已超過等候期，執行升級：{lvl['label']}")
        subject, body = build_body(lvl["level"], today_str)
        send_email(service, lvl["to"], lvl.get("cc", []), subject, body)
        all_rcpt = [lvl["to"]] + lvl.get("cc", [])
        for r in all_rcpt:
            print(f"   ✅ 已發送至：{r}")
        log["sent_escalations"].append({
            "date": today.strftime("%Y-%m-%d"),
            "level": lvl["level"],
            "label": lvl["label"],
            "recipients": all_rcpt,
        })
        save_log(log)
        print("\n📁 記錄已更新至 complaint_log.json")
    else:
        remaining = days_needed - days_waited
        print(f"\n⏳ 尚需等待 {remaining} 天才觸發下一次升級。")
        print(f"   再次執行此腳本即可檢查（建議每週一次）。")

    if check_progress:
        run_progress_check(service, log)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-progress", action="store_true",
                        help="同時搜尋政府有關電單車泊位改善的最新通知")
    args = parser.parse_args()
    run_check(check_progress=args.check_progress)
