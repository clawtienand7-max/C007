#!/usr/bin/env python3
"""
complaint_tracker.py — 多議題市民投訴系統 + 跟蹤 + 升級
用法：
  PYTHONPATH=/tmp/gauth python3 complaint_tracker.py              # 跟蹤電單車投訴
  PYTHONPATH=/tmp/gauth python3 complaint_tracker.py --topic all  # 跟蹤所有投訴
  PYTHONPATH=/tmp/gauth python3 complaint_tracker.py --send-new   # 發送所有新議題投訴
  PYTHONPATH=/tmp/gauth python3 complaint_tracker.py --check-progress  # 查核改善進度
"""
import os, sys, json, base64, argparse
from datetime import datetime, timezone
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, '/tmp/gauth')
BASE_DIR  = Path(__file__).parent
LOG_FILE  = BASE_DIR / "complaint_log.json"
MY_EMAIL  = "clawtienand7@gmail.com"
TODAY_STR = datetime.now(timezone.utc).strftime("%Y 年 %m 月 %d 日")

AUTO_REPLY_PATTERNS = [
    "automatic reply", "auto reply", "auto-reply", "acknowledged receipt",
    "this is an automatic", "這是電子", "自動回覆", "備悉",
    "we shall reply", "we will reply", "會盡快作出回覆",
]

# ══════════════════════════════════════════════════════════════════════════════
# 投訴議題資料庫（每個議題有對應部門、數據、升級策略）
# ══════════════════════════════════════════════════════════════════════════════
COMPLAINTS = {

    # ── 1. 電單車泊位（主線） ─────────────────────────────────────────────────
    "motorcycle_parking": {
        "id": "motorcycle_parking",
        "title": "電單車泊位嚴重不足 ＋ 罰款標準不公平",
        "sent_date": "2026-05-26",
        "primary_dept": "運輸及物流局",
        "escalation_levels": [
            {"to": "enquiry@tlb.gov.hk", "cc": ["td@td.gov.hk"],
             "label": "追催 + 運輸署", "days_wait": 28},
            {"to": "enquiry@tlb.gov.hk", "cc": ["td@td.gov.hk", "info@legco.gov.hk"],
             "label": "副本立法會交通事務委員會", "days_wait": 14},
            {"to": "enquiry@tlb.gov.hk",
             "cc": ["td@td.gov.hk", "info@legco.gov.hk", "cm@1823.gov.hk"],
             "label": "最終升級 + 1823", "days_wait": 7},
        ],
        "facts": """
【關鍵數據（來源：立法會文件、政府資訊中心）】
  • 2023年數據：全港74,815輛領牌電單車，僅38,563個合法泊位，
    比例0.52（私家車比例1.11），泊位缺口逾36,000個
  • 2026年1月1日起違例泊車罰款由$320調高至$400（增幅25%），
    為31年來首次調整，但泊位供應未見同比增加
  • 以$400計算，每年電單車違泊罰款收入估逾4,000萬元
  • 政府2025年措施：荃灣、葵青高架橋底增設約336個泊位，
    深水埗約90個——相對36,000個缺口，杯水車薪
  • 電單車佔用路面空間僅私家車約十分之一，罰款卻完全相同
  • 新加坡、台灣、日本均設有獨立電單車泊位政策及差別罰款制度""",
        "demands": """
【要求當局正式書面答覆】
  1. 未來三年新增合法電單車泊位的具體數目及選址時間表
  2. 是否承諾訂立與私家車有別的獨立電單車違泊罰款級別
  3. 公開2024–2026年度電單車違泊罰款收入確實金額及用途分項
  4. 是否設立機制將部分罰款收入專款用於增設電單車泊位""",
    },

    # ── 2. 巴士服務削減 ───────────────────────────────────────────────────────
    "bus_service_cuts": {
        "id": "bus_service_cuts",
        "title": "巴士路線削減及班次不足，嚴重影響市民出行",
        "sent_date": None,
        "primary_dept": "運輸及物流局",
        "escalation_levels": [
            {"to": "enquiry@tlb.gov.hk", "cc": ["td@td.gov.hk"],
             "label": "初次投訴", "days_wait": 28},
            {"to": "enquiry@tlb.gov.hk", "cc": ["td@td.gov.hk", "info@legco.gov.hk"],
             "label": "升級立法會", "days_wait": 14},
            {"to": "enquiry@tlb.gov.hk",
             "cc": ["td@td.gov.hk", "info@legco.gov.hk", "cm@1823.gov.hk"],
             "label": "最終升級", "days_wait": 7},
        ],
        "facts": """
【關鍵數據】
  • 2025–2026年度巴士路線改動列表顯示，多條路線被縮短、合併或取消，
    受影響居民需轉乘，延長通勤時間
  • 巴士公司以「客量不足」為由削減班次，惟居民反映高峰時段仍人滿為患
  • 偏遠地區（如北區、離島）居民尤其受影響，部分地區每小時僅一班
  • 政府補貼巴士公司逾數億元，惟服務質素持續下降
  • 市民投訴巴士班次不足的個案2025年第一季較去年同期增加10%""",
        "demands": """
【要求事項】
  1. 立即凍結所有影響主要民生路線的削減計劃，進行公眾諮詢
  2. 制定最低服務標準，確保高峰時段每15分鐘一班
  3. 公開政府對巴士公司補貼金額及服務要求細節
  4. 針對偏遠地區制定專項交通改善方案""",
    },

    # ── 3. 行人設施不足 ───────────────────────────────────────────────────────
    "pedestrian_facilities": {
        "id": "pedestrian_facilities",
        "title": "行人過路設施嚴重不足，長者及殘障人士出行困難",
        "sent_date": None,
        "primary_dept": "路政署及運輸署",
        "escalation_levels": [
            {"to": "hyd@hyd.gov.hk", "cc": ["td@td.gov.hk"],
             "label": "初次投訴", "days_wait": 28},
            {"to": "hyd@hyd.gov.hk",
             "cc": ["td@td.gov.hk", "info@legco.gov.hk"],
             "label": "升級立法會", "days_wait": 14},
            {"to": "hyd@hyd.gov.hk",
             "cc": ["td@td.gov.hk", "info@legco.gov.hk", "cm@1823.gov.hk"],
             "label": "最終升級", "days_wait": 7},
        ],
        "facts": """
【關鍵數據】
  • 多個市區路段行人過路燈相距逾500米，居民需繞行大段距離
  • 審計署報告指出：全港公共行人路保養存在嚴重滯後，
    逾千處損毀行人路待修，平均等候維修時間逾14個月
  • 無障礙通道設施不足，殘障人士及長者使用輪椅或助行架難以過路
  • 部分天橋升降機故障頻率高，路政署維修響應時間遠超標準
  • 香港每年行人交通意外中，約30%發生於設施不足的路段""",
        "demands": """
【要求事項】
  1. 制定行人過路設施評估標準，確保每300米設有一個行人過路處
  2. 公開所有待修行人路及天橋升降機的維修時間表
  3. 優先改善長者及殘障人士集中居住地區的無障礙設施
  4. 設立市民報告行人設施損毀的快速響應機制（24小時內確認）""",
    },

    # ── 4. 私家車違泊 vs 電單車差異 ─────────────────────────────────────────
    "parking_fine_fairness": {
        "id": "parking_fine_fairness",
        "title": "違例泊車罰款制度不公平——電單車與私家車劃一罰款違反比例原則",
        "sent_date": None,
        "primary_dept": "運輸及物流局",
        "escalation_levels": [
            {"to": "enquiry@tlb.gov.hk", "cc": ["td@td.gov.hk"],
             "label": "初次投訴", "days_wait": 28},
            {"to": "enquiry@tlb.gov.hk", "cc": ["td@td.gov.hk", "info@legco.gov.hk"],
             "label": "升級立法會", "days_wait": 14},
            {"to": "enquiry@tlb.gov.hk",
             "cc": ["td@td.gov.hk", "info@legco.gov.hk", "cm@1823.gov.hk"],
             "label": "最終升級", "days_wait": 7},
        ],
        "facts": """
【比較數據】
  • 現行電單車違泊罰款：$400（2026年1月起）= 私家車完全相同
  • 電單車平均車身面積約1.2平方米，私家車約8–10平方米
  • 電單車對道路阻塞的影響遠低於私家車
  • 國際比較：
    - 台灣：電單車違泊罰款新台幣900元，私家車1,800元（差一倍）
    - 新加坡：電單車違泊罰款S$70，私家車S$100（差43%）
    - 日本：電單車違泊罰款¥15,000，私家車¥15,000–18,000
  • 香港為極少數對電單車和私家車施以完全相同罰款的地區
  • 2026年罰款加幅25%，但政府未同時增加電單車泊位供應""",
        "demands": """
【要求事項】
  1. 委託獨立機構研究電單車違泊罰款合理標準
  2. 參考國際做法訂立差別罰款制度，電單車罰款應低於私家車
  3. 在增加電單車泊位供應之前，暫緩進一步上調電單車違泊罰款
  4. 公開政府就罰款標準制定的評估準則及計算依據""",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# 工具函數
# ══════════════════════════════════════════════════════════════════════════════
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
    return {}


def save_log(log: dict):
    LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2))


def get_topic_log(log: dict, topic_id: str) -> dict:
    return log.setdefault(topic_id, {
        "sent_escalations": [],
        "replied": False,
        "reply_date": None,
        "auto_acknowledged": False,
        "acknowledged_date": None,
    })


def is_auto_reply(body_text: str) -> bool:
    t = body_text.lower()
    return any(p.lower() in t for p in AUTO_REPLY_PATTERNS)


def days_since(date_str: str) -> int:
    if not date_str:
        return 0
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - d).days


def check_replies(service, keywords: list) -> tuple:
    q = 'from:(tlb.gov.hk OR td.gov.hk OR legco.gov.hk OR 1823.gov.hk OR hyd.gov.hk)'
    result = service.users().messages().list(
        userId="me", q=q, maxResults=15
    ).execute()
    msgs = result.get("messages", [])
    has_real, has_auto = False, False
    for m in msgs:
        detail = service.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()
        hdrs = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        subj = hdrs.get("Subject", "").lower()
        if not any(kw.lower() in subj for kw in keywords):
            continue
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


# ══════════════════════════════════════════════════════════════════════════════
# 建立投訴信內文
# ══════════════════════════════════════════════════════════════════════════════
def build_complaint_body(complaint: dict, level: int, today_str: str,
                         sent_date: str) -> tuple:
    title  = complaint["title"]
    facts  = complaint["facts"]
    demands = complaint["demands"]
    dept   = complaint["primary_dept"]

    if level == 0:
        subject = f"正式投訴：{title}"
        intro = f"本人 Tien 先生，香港市民，現就「{title}」問題向  貴局提出正式投訴。"
        deadline = f"本人期望貴局於收到本函後二十八個工作天內給予書面回覆。"
        footer = ""

    elif level == 1:
        subject = f"【第一次追催】正式投訴：{title}"
        intro = (f"本人已於 {sent_date} 向  貴局就「{title}」提出正式投訴，"
                 f"雖收到自動確認收件，惟至今逾期未獲任何實質回覆。\n"
                 f"本人現發出第一次追催，並已副本抄送相關部門。")
        deadline = "本人要求於十四個工作天內給予書面回覆，否則將升級至立法會。"
        footer = "（本函已副本抄送運輸署）"

    elif level == 2:
        subject = f"【升級投訴 — 副本立法會】{title}"
        intro = (f"本人自 {sent_date} 起已兩度就「{title}」問題提出正式投訴，"
                 f"均未獲實質回應。\n"
                 f"本人現升級投訴，已副本抄送立法會交通事務委員會，"
                 f"並保留向申訴專員公署投訴之權利。")
        deadline = "本人要求於七個工作天內給予正式書面回覆。"
        footer = "（本函已副本抄送：運輸署、立法會交通事務委員會）"

    else:
        subject = f"【最終升級投訴 — 要求問責】{title}"
        intro = (f"本人自 {sent_date} 起已三度就「{title}」問題提出正式投訴，"
                 f"歷時逾兩個月，至今仍無實質回覆，此乃嚴重行政失當。\n"
                 f"本人現發出最終升級投訴，並已副本抄送立法會及1823投訴中心。\n"
                 f"本人已準備向申訴專員公署提出正式投訴，並考慮聯絡傳媒報道。")
        deadline = ("本人要求局長或副局長於五個工作天內親自就此事作出書面回應，"
                    "否則本人將公開此事。")
        footer = "（本函已副本抄送：運輸署、立法會交通事務委員會、1823市民投訴中心）"

    body = f"""{dept} 局長 閣下：

{intro}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
投訴事項：{title}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{facts.strip()}

{demands.strip()}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{deadline}

此致

Tien 先生（香港市民）
電郵：{MY_EMAIL}
日期：{today_str}

{footer}"""

    return subject, body


# ══════════════════════════════════════════════════════════════════════════════
# 主邏輯
# ══════════════════════════════════════════════════════════════════════════════
def process_topic(service, complaint: dict, log: dict, send_new: bool = False):
    topic_id = complaint["id"]
    tlog = get_topic_log(log, topic_id)
    today = datetime.now(timezone.utc)
    today_date = today.strftime("%Y-%m-%d")
    sent_date = complaint.get("sent_date") or tlog.get("initial_sent_date")

    print(f"\n{'─'*60}")
    print(f"📌 {complaint['title']}")
    print(f"   部門：{complaint['primary_dept']}")
    print(f"   發出日期：{sent_date or '未發送'}")
    print(f"   政府確認：{'✅ ' + tlog.get('acknowledged_date','') if tlog.get('auto_acknowledged') else '—'}")
    print(f"   實質回覆：{'✅ ' + tlog.get('reply_date','') if tlog.get('replied') else '❌ 未收到'}")
    print(f"   已升級次數：{len(tlog.get('sent_escalations', []))}")

    if tlog.get("replied"):
        print("   ✅ 已完結（政府已回覆）")
        return

    # 還未發出初次投訴
    if not sent_date and send_new:
        lvl_info = complaint["escalation_levels"][0]
        subj, body = build_complaint_body(complaint, 0, TODAY_STR, today_date)
        send_email(service, lvl_info["to"], [], subj, body)
        tlog["initial_sent_date"] = today_date
        complaint["sent_date"] = today_date
        print(f"   📤 初次投訴已發送至 {lvl_info['to']}")
        save_log(log)
        return

    if not sent_date:
        print("   ⏸  尚未發送（執行 --send-new 以發送）")
        return

    # 檢查回覆
    keywords = [w for w in complaint["title"].split("：")[-1].split() if len(w) > 1][:3]
    has_real, has_auto = check_replies(service, keywords + ["電單車", "泊位", "巴士", "行人"])
    if has_real:
        tlog["replied"] = True
        tlog["reply_date"] = today_date
        save_log(log)
        print("   🎉 偵測到實質回覆！已標記完成。")
        return
    if has_auto and not tlog.get("auto_acknowledged"):
        tlog["auto_acknowledged"] = True
        tlog["acknowledged_date"] = today_date
        save_log(log)
        print("   📩 已偵測到自動確認收件。")

    # 升級評估
    levels = complaint["escalation_levels"]
    sent_count = len(tlog.get("sent_escalations", []))
    if sent_count >= len(levels):
        print("   ⚠️  已完成全部升級層級。建議向申訴專員公署投訴。")
        return

    last_date = (tlog["sent_escalations"][-1]["date"]
                 if tlog.get("sent_escalations") else sent_date)
    lvl_info  = levels[sent_count]
    days_waited = days_since(last_date)
    days_needed = lvl_info["days_wait"]

    if days_waited >= days_needed:
        subj, body = build_complaint_body(
            complaint, sent_count + 1, TODAY_STR, sent_date
        )
        send_email(service, lvl_info["to"], lvl_info.get("cc", []), subj, body)
        all_rcpt = [lvl_info["to"]] + lvl_info.get("cc", [])
        for r in all_rcpt:
            print(f"   📤 升級已發送：{r}")
        tlog.setdefault("sent_escalations", []).append({
            "date": today_date,
            "level": sent_count + 1,
            "label": lvl_info["label"],
            "recipients": all_rcpt,
        })
        save_log(log)
    else:
        remaining = days_needed - days_waited
        print(f"   ⏳ 等待 {remaining} 天後觸發下一升級（{lvl_info['label']}）")


def run_progress_check(service, log: dict):
    print(f"\n{'═'*60}")
    print("🔍 查核政府改善進度")
    print(f"{'═'*60}")
    result = service.users().messages().list(
        userId="me",
        q='from:(gov.hk) (電單車 OR motorcycle OR 巴士 OR 行人)',
        maxResults=8
    ).execute()
    msgs = result.get("messages", [])
    if msgs:
        print(f"找到 {len(msgs)} 封相關政府郵件：")
        for m in msgs:
            d = service.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            h = {x["name"]: x["value"] for x in d["payload"]["headers"]}
            print(f"  [{h.get('Date','?')[:16]}] {h.get('From','?')}")
            print(f"   主題：{h.get('Subject','?')}")
    else:
        print("未發現政府改善進度相關通知。")
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log.setdefault("progress_checks", []).append({
        "date": today_date, "gov_emails_found": len(msgs)
    })
    save_log(log)


def print_summary(log: dict):
    print(f"\n{'═'*60}")
    print("📊 所有投訴狀態總覽")
    print(f"{'═'*60}")
    for cid, c in COMPLAINTS.items():
        tlog = log.get(cid, {})
        sent = c.get("sent_date") or tlog.get("initial_sent_date", "—")
        status = ("✅ 完結" if tlog.get("replied") else
                  "⏳ 追蹤中" if sent != "—" else "⏸  待發送")
        acks = "✅" if tlog.get("auto_acknowledged") else "—"
        escalated = len(tlog.get("sent_escalations", []))
        print(f"  {status}  [{acks}確認]  升級{escalated}次  {c['title'][:30]}")
    print()


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="motorcycle_parking",
                        help="投訴議題ID，或 'all' 處理全部")
    parser.add_argument("--send-new", action="store_true",
                        help="對未發送的議題發出初次投訴")
    parser.add_argument("--check-progress", action="store_true",
                        help="搜尋政府改善進度相關郵件")
    parser.add_argument("--summary", action="store_true",
                        help="顯示所有投訴狀態")
    args = parser.parse_args()

    import email_gmail_api as api
    service = api.get_service()
    log = load_log()

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n{'═'*60}")
    print(f"📋 多議題投訴追蹤系統 — {now_str}")
    print(f"{'═'*60}")

    topics = (list(COMPLAINTS.keys()) if args.topic == "all"
              else [args.topic] if args.topic in COMPLAINTS
              else ["motorcycle_parking"])

    for tid in topics:
        process_topic(service, COMPLAINTS[tid], log, send_new=args.send_new)

    if args.check_progress:
        run_progress_check(service, log)

    if args.summary or args.topic == "all":
        print_summary(log)
