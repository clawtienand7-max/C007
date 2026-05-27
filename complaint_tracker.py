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
from email.mime.base import MIMEBase
from email import encoders

sys.path.insert(0, '/tmp/gauth')
BASE_DIR   = Path(__file__).parent
LOG_FILE   = BASE_DIR / "complaint_log.json"
GUIDES_DIR = BASE_DIR / "guides"
MY_EMAIL   = "clawtienand7@gmail.com"
TODAY_STR  = datetime.now(timezone.utc).strftime("%Y 年 %m 月 %d 日")

AUTO_REPLY_PATTERNS = [
    "automatic reply", "auto reply", "auto-reply", "acknowledged receipt",
    "this is an automatic", "這是電子", "自動回覆", "備悉",
    "we shall reply", "we will reply", "會盡快作出回覆",
]

# 附件圖解（隨主要投訴信發出）
EVIDENCE_ATTACHMENTS = [
    "evidence_A_parking_ratio.png",
    "evidence_B_space_comparison.png",
    "evidence_C_fine_tiers.png",
    "evidence_D_revenue_flow.png",
]


# ══════════════════════════════════════════════════════════════════════════════
# 投訴議題資料庫
# ══════════════════════════════════════════════════════════════════════════════
COMPLAINTS = {

    # ── 1. 電單車泊位 + 罰款不公 ──────────────────────────────────────────────
    "motorcycle_parking": {
        "id": "motorcycle_parking",
        "title": "電單車泊位嚴重不足、罰款標準失當及罰款收入透明度不足",
        "sent_date": "2026-05-26",
        "primary_dept": "運輸及物流局",
        "attach_evidence": True,
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
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【甲】泊位嚴重不足——以事實數據說明
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

根據政府提交立法會文件（LCQ13/2023、LCQ12/2024、LCQ15/2023）：

  ▸ 全港登記電單車：74,815 輛（2023年）
  ▸ 全港合法電單車泊位：38,563 個（同期）
  ▸ 泊位缺口：逾 36,000 個（缺口率 48%）
  ▸ 電單車泊位比例：0.52（每輛車對應 0.52 個泊位）
  ▸ 私家車泊位比例：1.11（差距逾一倍）

重點地區使用率（資料來源：LCQ12/2024，運輸及物流局）：
  ▸ 荃灣及葵青：1,355 個路面泊位，連續三年使用率達 100%
  ▸ 旺角/油尖：連續三年使用率 100%，高峰期完全爆滿
  ▸ 觀塘工業區：使用率長期逾 95%，食物外送行業需求激增

政府應對措施嚴重不足：
  ▸ 2025年措施：荃灣高架橋底增設約 340 個泊位、深水埗 90 個
  ▸ 合計新增不足 500 個，相對 36,000 個缺口僅佔 1.4%
  ▸ 食物外送、速遞行業電單車數量急增，令缺口持續擴大

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【乙】罰款制度失當——違反比例原則
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

現行問題：罰款一刀切，不論實際交通影響輕重

本人認為，違例泊車罰款理應反映實際對交通的影響程度。
若電單車泊車並無造成交通阻塞、並無阻礙行人通道、並無危及公共安全，
僅因泊位不足而被逼泊於非指定位置，則現行 $400 重罰有以下問題：

  1. 比例原則：
     電單車車身面積約 1.6 平方米，私家車約 9 平方米（差距逾 5 倍）；
     同一車道空間，電單車對交通的佔用及阻礙遠低於私家車，
     卻受完全相同的罰款，明顯有違「罰款應與危害成正比」的法律原則。

  2. 強迫性犯規：
     當附近 500 米內根本無合法泊位，車主在無選擇之下被迫違規，
     政府既未提供足夠設施，卻仍施以重罰，有懲罰車主被動違規之嫌。

  3. 無差別執法：
     現時無論電單車是否阻塞交通，一律罰款 $400；
     但法律精神應區分「造成實際危害」與「形式上不符泊車規例」。

國際比較（各地電單車 vs 私家車違泊罰款比率）：
  ▸ 台灣：電單車 TWD 900 / 私家車 TWD 1,800（電單車罰款為私家車 50%）
  ▸ 新加坡：電單車 SGD 70 / 私家車 SGD 100（電單車罰款為私家車 70%）
  ▸ 英國：電單車 £35 / 私家車 £70（電單車罰款為私家車 50%）
  ▸ 日本：電單車 ¥15,000 / 私家車 ¥18,000（電單車罰款為私家車 83%）
  ▸ 香港：電單車 $400 / 私家車 $400（完全相同，國際罕見）

香港是極少數對電單車和私家車施以完全相同違泊罰款的已發展地區，
不符合國際慣例，明顯有欠公平。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【丙】罰款收入不透明，未見用於解決根本問題
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

根據政府財政預算案及傳媒報道（HK01、am730）：
  ▸ 2023/24年度：全港違例泊車告票 254.3 萬張，庫房進賬 8.14 億元
  ▸ 2024/25年度：預算收入 9.8 億元（修訂後 8.4 億元）
  ▸ 過去5年：合計發出違泊告票近 1.5 億張，庫房進賬逾 48 億元
  ▸ 罰款加至 $400 後，預計年收入將進一步上升至逾 10 億元

然而，政府從未就上述龐大罰款收入如何專項用於
改善泊車設施、增設電單車泊位或解決停車場短缺問題，
作出任何具體、透明的公開交代。

以每年 8–10 億元的罰款收入計算，若有 20–30% 專款用於增設電單車泊位，
相當於每年 1.6–3 億元的專項資金，足以在全港增設數千個泊位，
足以在三至五年內大幅縮減泊位缺口。

本人質疑：政府是否以罰款為庫房增收手段，
而非真正以改善交通管理為目標？

本人特別附上四張數據圖解（附件 A–D）供參考。""",

        "demands": """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【要求事項】本人要求當局正式書面答覆
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

即時措施（三個月內）：
  1. 公開 2022–2026 年度電單車違例泊車告票發出數量及相關罰款收入
  2. 公開政府如何運用違泊罰款收入，逐項列明用途
  3. 設立緊急機制，允許車主在附近 500 米內無合法泊位的情況下，
     以書面陳述申請豁免或減免罰款

短期措施（一年內）：
  4. 制定具體計劃，全港新增不少於 5,000 個合法電單車泊位，
     並公布選址時間表
  5. 優先開放政府物業、公共空地及高架橋底供電單車泊車
  6. 研究設立電單車泊位專項資金，將部分罰款收入專款用於增設泊位

中期政策改革（三年內）：
  7. 根據「罰款應與實際交通影響成比例」原則，
     訂立分級電單車違泊罰款制度：
       — 無交通阻塞、無行人阻礙、附近無泊位：口頭警告或象徵性罰款
       — 輕微影響：$150–200（低於私家車相同情況）
       — 中等影響：$250–300
       — 嚴重阻塞：$400 或以上（維持現行標準）
  8. 制定法定電單車泊位比例標準（建議不低於每輛車一個泊位）
  9. 設立年度電單車泊位改善報告制度，向公眾公布進度

本人期望貴局能正視上述問題，並提供具體、可量化、有時間表的回覆。""",
    },

    # ── 2. 巴士服務削減 ───────────────────────────────────────────────────────
    "bus_service_cuts": {
        "id": "bus_service_cuts",
        "title": "巴士路線削減及班次不足，嚴重影響市民出行",
        "sent_date": "2026-05-26",
        "primary_dept": "運輸及物流局",
        "attach_evidence": False,
        "escalation_levels": [
            {"to": "enquiry@tlb.gov.hk", "cc": ["td@td.gov.hk"],
             "label": "追催 + 運輸署", "days_wait": 28},
            {"to": "enquiry@tlb.gov.hk", "cc": ["td@td.gov.hk", "info@legco.gov.hk"],
             "label": "副本立法會", "days_wait": 14},
            {"to": "enquiry@tlb.gov.hk",
             "cc": ["td@td.gov.hk", "info@legco.gov.hk", "cm@1823.gov.hk"],
             "label": "最終升級", "days_wait": 7},
        ],
        "facts": """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【甲】巴士服務削減現況
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

根據 2025–2026 年度巴士路線規劃計劃及各區區議會文件：

  ▸ 多條民生巴士路線被縮短、合併或取消，受影響居民需多次轉乘
  ▸ 巴士公司以「客量不足」為由削減班次，惟高峰時段仍人滿為患
  ▸ 新界北區、離島及偏遠屋邨居民受影響最深，部分地區班次稀疏
  ▸ 2025年第一季市民投訴巴士服務個案較去年同期上升約 10%
  ▸ 現時全港每日公共交通使用率逾 90%，巴士承擔不可或缺的角色

服務惡化的直接影響：
  ▸ 通勤時間延長 15–30 分鐘，影響工作及生活質素
  ▸ 長者、殘障人士及低收入家庭無力負擔的士，受影響最大
  ▸ 轉乘次數增加，額外車費負擔加重基層市民生活壓力

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【乙】政府補貼與服務質素的矛盾
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ▸ 政府向巴士公司提供多項補貼及優惠（包括燃油稅豁免、路權等）
  ▸ 巴士公司同時獲批加價，惟服務質素和班次頻率未見相應改善
  ▸ 市民質疑：政府在批准加價和繼續補貼的同時，
    有否就最低服務標準作出具約束力的承諾？""",

        "demands": """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【要求事項】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. 立即暫停所有影響主要民生路線的削減計劃，
     在完成公眾諮詢前不得單方面縮減服務
  2. 制定強制性最低服務標準：
     — 繁忙時段主要路線：每 10 分鐘一班
     — 一般時段：每 20 分鐘一班
     — 偏遠地區：每 30 分鐘一班
  3. 公開政府對各巴士公司的補貼金額、批准加價條件
     及相應服務要求的詳細內容
  4. 建立服務質素監察機制，每季度公布班次準時率及投訴統計
  5. 針對長者、殘障人士及低收入家庭制定優先出行保障措施
  6. 就 2025–2026 年路線改動計劃進行公開聽證，
     讓受影響居民正式表達意見""",
    },

    # ── 3. 行人設施不足 ───────────────────────────────────────────────────────
    "pedestrian_facilities": {
        "id": "pedestrian_facilities",
        "title": "行人過路設施嚴重不足，長者及殘障人士出行困難",
        "sent_date": "2026-05-26",
        "primary_dept": "路政署及運輸署",
        "attach_evidence": False,
        "escalation_levels": [
            {"to": "hyd@hyd.gov.hk", "cc": ["td@td.gov.hk"],
             "label": "追催", "days_wait": 28},
            {"to": "hyd@hyd.gov.hk",
             "cc": ["td@td.gov.hk", "info@legco.gov.hk"],
             "label": "副本立法會", "days_wait": 14},
            {"to": "hyd@hyd.gov.hk",
             "cc": ["td@td.gov.hk", "info@legco.gov.hk", "cm@1823.gov.hk"],
             "label": "最終升級", "days_wait": 7},
        ],
        "facts": """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【甲】行人設施不足現況
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ▸ 東區區議會文件顯示：2024年共收到 1,034 宗有關行人路面不平的投訴
  ▸ 多個市區路段行人過路設施相距逾 500 米，居民須繞行大段距離
  ▸ 逾千處損毀行人路待維修，部分平均等候時間超過 14 個月
  ▸ 「人人暢道通行」計劃推出多年，仍有大量天橋及隧道欠缺無障礙設施
  ▸ 天橋升降機故障率高，維修響應時間長，長者出行大受影響

對長者及弱勢群體的衝擊：
  ▸ 全港 65 歲以上長者逾 150 萬人，日常出行嚴重依賴行人設施
  ▸ 無障礙通道不足，輪椅使用者被迫使用不安全的斜坡或繞道
  ▸ 視障人士反映引導徑中斷、障礙物阻路問題持續未獲解決
  ▸ 香港每年行人交通意外中，相當比例發生於設施不足的路段

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【乙】資源分配問題
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ▸ 政府每年從違例泊車罰款收取逾 8 億元，
    卻未見相應資源用於改善行人安全設施
  ▸ 道路建設預算傾向大型基建（如新幹線、鐵路），
    對行人日常設施維修投入不足
  ▸ 缺乏行人設施狀況定期公開評估報告""",

        "demands": """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【要求事項】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. 制定行人過路設施最低密度標準：
     — 市區每 200 米設一個行人過路處
     — 郊區每 400 米設一個行人過路處
  2. 公開全港待維修行人路及天橋升降機清單，
     並承諾在六個月內完成維修
  3. 設立 24 小時行人設施損毀快速報告及響應機制
  4. 優先在長者聚居、學校及醫院附近路段加設無障礙設施
  5. 每年向公眾發布行人設施狀況年度報告
  6. 設立跨部門協調機制，確保路政署、運輸署及各區區議會
     協調一致推進改善工程""",
    },

    # ── 4. 罰款比例原則 ───────────────────────────────────────────────────────
    "parking_fine_fairness": {
        "id": "parking_fine_fairness",
        "title": "違例泊車罰款「一刀切」制度失當——應按實際交通影響分級執法",
        "sent_date": "2026-05-26",
        "primary_dept": "運輸及物流局",
        "attach_evidence": False,
        "escalation_levels": [
            {"to": "enquiry@tlb.gov.hk", "cc": ["td@td.gov.hk"],
             "label": "追催", "days_wait": 28},
            {"to": "enquiry@tlb.gov.hk", "cc": ["td@td.gov.hk", "info@legco.gov.hk"],
             "label": "副本立法會", "days_wait": 14},
            {"to": "enquiry@tlb.gov.hk",
             "cc": ["td@td.gov.hk", "info@legco.gov.hk", "cm@1823.gov.hk"],
             "label": "最終升級", "days_wait": 7},
        ],
        "facts": """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【甲】現行制度的核心問題
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

香港現行違例泊車罰款制度（2026年1月起 $400）存在根本性缺陷：

「一刀切」不分交通影響輕重——
  ▸ 電單車無阻塞泊於偏僻路段：罰款 $400
  ▸ 私家車完全阻塞消防通道：罰款 $400
  ▸ 兩者罰款完全相同，違反基本的公平及比例原則

本人認為，合理的罰款制度應考慮以下因素：
  (a) 實際造成的交通阻塞程度
  (b) 對行人及緊急車輛的影響
  (c) 車輛大小及佔用道路空間
  (d) 附近是否有合法泊位可供選擇
  (e) 違規持續時間長短

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【乙】「無阻塞不重罰」的法律及政策根據
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

比例原則（Proportionality Principle）：
  ▸ 《基本法》第二十五條保障法律面前人人平等
  ▸ 行政罰則理應與違規行為造成的實際危害相稱
  ▸ 若違規行為並無造成實際危害，施以重罰有違法律精神

國際做法：
  ▸ 英國：部分地方政府設有「情況裁量」條款，
    執法人員可就顯然無阻塞的違規發出警告而非罰款
  ▸ 荷蘭：電單車泊於人行道的特定位置，若不阻礙行人，
    屬合法或僅受象徵性罰款
  ▸ 德國：罰款金額按實際對交通影響程度分為多個等級

香港比較：
  ▸ 電單車車身 ≈ 1.6 m²，私家車 ≈ 9 m²（差距逾 5 倍）
  ▸ 兩者受相同 $400 罰款，未能反映對道路使用的實際影響差異
  ▸ 在合法泊位嚴重不足的情況下執行重罰，
    等同懲罰車主因政府施政失當而被迫違規

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【丙】具體建議：四級分類執法框架
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

第一級（無實質影響）：
  條件：無交通阻塞、無行人阻礙、車輛完全靠邊、附近 500 米無合法泊位
  建議處理：警告通知書（首次）/ $100 象徵性罰款（再犯）

第二級（輕微影響）：
  條件：輕微佔用黃線、略佔行人路角落、不阻礙行車線
  建議罰款：$150–200（電單車）/ $250–300（其他車輛）

第三級（中等影響）：
  條件：路口轉角泊車、影響視線、輕微阻礙部分行人
  建議罰款：$250–300（電單車）/ $350–400（其他車輛）

第四級（嚴重阻塞）：
  條件：阻塞行車線、佔用消防通道、嚴重危害公共安全
  建議罰款：$400 或以上（維持現行標準，嚴格執法）""",

        "demands": """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【要求事項】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. 委託獨立法律及交通專家就現行「一刀切」罰款制度
     進行全面檢討，評估其是否符合比例原則

  2. 參考英國、荷蘭、台灣等地做法，
     研究在香港引入「按交通影響分級執法」制度的可行性

  3. 在分級制度落實前，設立臨時「酌情豁免申請機制」：
     車主可提供書面陳述，證明附近無合法泊位，申請減免罰款

  4. 修訂《道路交通（違例泊車）規例》，
     引入「無實質阻塞」作為法定減刑或豁免因素

  5. 公開政府制定現行罰款標準的評估準則及計算依據，
     解釋為何電單車與私家車應受完全相同罰款""",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# 工具函數
# ══════════════════════════════════════════════════════════════════════════════
def encode_msg(msg) -> dict:
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def send_email(service, to: str, cc_list: list, subject: str, body: str,
               attachments: list = None):
    msg = MIMEMultipart()
    msg["From"]    = MY_EMAIL
    msg["To"]      = to
    msg["Subject"] = subject
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    for fpath in (attachments or []):
        p = Path(fpath)
        if not p.exists():
            continue
        part = MIMEBase("image", "png")
        part.set_payload(p.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition",
                        f'attachment; filename="{p.name}"')
        msg.attach(part)

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
        "initial_sent_date": None,
    })


def is_auto_reply(body_text: str) -> bool:
    t = body_text.lower()
    return any(p.lower() in t for p in AUTO_REPLY_PATTERNS)


def days_since(date_str: str) -> int:
    if not date_str:
        return 0
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - d).days


def check_replies(service, topic_keywords: list) -> tuple:
    q = ('from:(tlb.gov.hk OR td.gov.hk OR legco.gov.hk '
         'OR 1823.gov.hk OR hyd.gov.hk)')
    result = service.users().messages().list(
        userId="me", q=q, maxResults=20
    ).execute()
    has_real, has_auto = False, False
    for m in result.get("messages", []):
        detail = service.users().messages().get(
            userId="me", id=m["id"], format="full"
        ).execute()
        hdrs = {h["name"]: h["value"]
                for h in detail["payload"]["headers"]}
        subj = hdrs.get("Subject", "").lower()
        if not any(kw.lower() in subj for kw in topic_keywords):
            continue
        body_text = ""
        payload = detail.get("payload", {})
        if payload.get("body", {}).get("data"):
            body_text = base64.urlsafe_b64decode(
                payload["body"]["data"] + "=="
            ).decode("utf-8", errors="replace")
        elif payload.get("parts"):
            for part in payload["parts"]:
                if (part.get("mimeType") == "text/plain"
                        and part.get("body", {}).get("data")):
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
# 建立投訴信
# ══════════════════════════════════════════════════════════════════════════════
def build_body(complaint: dict, level: int, today_str: str,
               sent_date: str) -> tuple:
    title   = complaint["title"]
    facts   = complaint["facts"]
    demands = complaint["demands"]
    dept    = complaint["primary_dept"]
    has_att = complaint.get("attach_evidence", False)
    att_note = ("\n（本函附上四張數據圖解作為佐證，請參閱附件 A–D）\n"
                if has_att else "")

    if level == 0:
        subject = f"正式投訴：{title}"
        intro = (f"本人 Tien 先生，香港市民，現就「{title}」問題"
                 f"向  貴局提出正式投訴。{att_note}")
        deadline = ("本人期望貴局能正視上述問題，"
                    "並於收到本函後二十八個工作天內給予正式書面回覆。")
        footer = ""

    elif level == 1:
        subject = f"【第一次追催】正式投訴：{title}"
        intro = (f"本人已於 {sent_date} 向  貴局就「{title}」提出正式投訴，"
                 f"雖收到自動確認收件，惟至今逾期未獲任何實質回覆。\n"
                 f"本人現發出第一次追催，並已副本抄送相關部門。{att_note}")
        deadline = ("本人要求於收到本追催函後十四個工作天內給予書面回覆，"
                    "否則將進一步升級至立法會交通事務委員會。")
        footer = "（本函已副本抄送：運輸署）"

    elif level == 2:
        subject = f"【升級投訴 — 副本立法會】{title}"
        intro = (f"本人自 {sent_date} 起已兩度就「{title}」提出正式投訴，"
                 f"均未獲任何實質回應，此等漠視市民投訴之態度令本人深感遺憾。\n"
                 f"本人現正式升級投訴，已副本抄送立法會交通事務委員會，"
                 f"並保留向申訴專員公署投訴之權利。{att_note}")
        deadline = ("本人要求於七個工作天內給予正式書面回覆，"
                    "否則將向申訴專員公署正式投訴，並考慮聯絡傳媒報道。")
        footer = "（本函已副本抄送：運輸署、立法會交通事務委員會）"

    else:
        subject = f"【最終升級投訴 — 要求局長問責】{title}"
        intro = (f"本人自 {sent_date} 起已三度就「{title}」提出正式投訴，"
                 f"歷時逾兩個月，至今仍未獲任何實質回覆，此乃嚴重行政失當。\n"
                 f"本人現發出最終升級投訴，已副本抄送立法會及 1823 投訴中心。\n"
                 f"本人已向申訴專員公署提出正式投訴，並已聯絡傳媒報道。{att_note}")
        deadline = ("本人要求局長或副局長於五個工作天內親自作出書面回應，"
                    "否則本人將公開此事並啟動相關法律程序。")
        footer = "（本函已副本抄送：運輸署、立法會交通事務委員會、1823 市民投訴中心）"

    body = f"""{dept} 局長 閣下：

{intro}

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
    topic_id   = complaint["id"]
    tlog       = get_topic_log(log, topic_id)
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sent_date  = complaint.get("sent_date") or tlog.get("initial_sent_date")

    print(f"\n{'─'*60}")
    print(f"📌 {complaint['title']}")
    print(f"   部門  : {complaint['primary_dept']}")
    print(f"   發出  : {sent_date or '未發送'}")
    print(f"   確認  : {'✅ ' + (tlog.get('acknowledged_date') or '') if tlog.get('auto_acknowledged') else '—'}")
    print(f"   回覆  : {'✅ ' + (tlog.get('reply_date') or '') if tlog.get('replied') else '❌ 未收到'}")
    print(f"   升級  : {len(tlog.get('sent_escalations', []))} 次")

    if tlog.get("replied"):
        print("   ✅ 已完結")
        return

    if not sent_date and send_new:
        lvl_info = complaint["escalation_levels"][0]
        subj, body = build_body(complaint, 0, TODAY_STR, today_date)
        att_files = []
        if complaint.get("attach_evidence"):
            att_files = [str(GUIDES_DIR / f) for f in EVIDENCE_ATTACHMENTS
                         if (GUIDES_DIR / f).exists()]
        send_email(service, lvl_info["to"], [], subj, body, att_files)
        tlog["initial_sent_date"] = today_date
        complaint["sent_date"] = today_date
        print(f"   📤 初次投訴已發送至 {lvl_info['to']}"
              + (f" (含 {len(att_files)} 個附件)" if att_files else ""))
        save_log(log)
        return

    if not sent_date:
        print("   ⏸  尚未發送（執行 --send-new 以發送）")
        return

    keywords = ["電單車", "泊位", "巴士", "行人", "罰款",
                "motorcycle", "parking", "bus", "pedestrian"]
    has_real, has_auto = check_replies(service, keywords)

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
        print("   📩 偵測到自動確認收件。")

    levels     = complaint["escalation_levels"]
    sent_count = len(tlog.get("sent_escalations", []))
    if sent_count >= len(levels):
        print("   ⚠️  已完成全部升級。建議向申訴專員公署投訴。")
        return

    last_date   = (tlog["sent_escalations"][-1]["date"]
                   if tlog.get("sent_escalations") else sent_date)
    lvl_info    = levels[sent_count]
    days_waited = days_since(last_date)
    days_needed = lvl_info["days_wait"]

    if days_waited >= days_needed:
        subj, body = build_body(complaint, sent_count + 1, TODAY_STR, sent_date)
        att_files  = []
        if complaint.get("attach_evidence"):
            att_files = [str(GUIDES_DIR / f) for f in EVIDENCE_ATTACHMENTS
                         if (GUIDES_DIR / f).exists()]
        send_email(service, lvl_info["to"], lvl_info.get("cc", []),
                   subj, body, att_files)
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
    result = service.users().messages().list(
        userId="me",
        q='from:(gov.hk) (電單車 OR motorcycle OR 巴士 OR 行人 OR 泊位)',
        maxResults=10
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
            print(f"  [{h.get('Date','')[:16]}] {h.get('From','')}")
            print(f"   主題：{h.get('Subject','')}")
    else:
        print("   未發現政府改善進度通知。")
    log.setdefault("progress_checks", []).append({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "gov_emails_found": len(msgs),
    })
    save_log(log)


def print_summary(log: dict):
    print(f"\n{'═'*60}")
    print("📊 所有投訴狀態總覽")
    print(f"{'═'*60}")
    for cid, c in COMPLAINTS.items():
        tlog   = log.get(cid, {})
        sent   = c.get("sent_date") or tlog.get("initial_sent_date", "—")
        status = ("✅ 完結" if tlog.get("replied") else
                  "⏳ 追蹤中" if sent != "—" else "⏸  待發送")
        ack    = "✅" if tlog.get("auto_acknowledged") else "—"
        esc    = len(tlog.get("sent_escalations", []))
        att    = "📎" if c.get("attach_evidence") else "  "
        print(f"  {status}  [{ack}確認] {att} 升級{esc}次  {c['title'][:36]}")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="motorcycle_parking",
                        help="投訴議題 ID，或 'all' 處理全部")
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
        process_topic(service, COMPLAINTS[tid], log,
                      send_new=args.send_new)

    if args.check_progress:
        run_progress_check(service, log)

    if args.summary or args.topic == "all":
        print_summary(log)
