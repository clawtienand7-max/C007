"""
製作投訴附件用視覺證據圖解：
  evidence_A_parking_ratio.png   — 泊位比例對比
  evidence_B_space_comparison.png — 車身面積對比
  evidence_C_fine_tiers.png      — 建議分級罰款框架
  evidence_D_revenue_flow.png    — 罰款收入流向分析
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
from make_guide import (
    load_font, OUT_DIR, shadow_rect, warn_box, success_box, arrow,
    BG, CARD_BG, TITLE_COL, BODY_COL, STEP_CIRCLE, BTN_GREEN, BTN_RED,
    TITLE_COL as DARK,
)
from PIL import Image, ImageDraw

W = 960
PAD = 30
WHITE  = (255, 255, 255)
RED    = (234,  67,  53)
GREEN  = ( 52, 168,  83)
BLUE   = ( 66, 133, 244)
ORANGE = (251, 140,   0)
GREY   = (149, 157, 165)
YELLOW = (251, 192,  45)
PURPLE = (142,  36, 170)
TEAL   = (  0, 150, 136)
LIGHT  = (241, 243, 244)


def txt(draw, x, y, text, size=16, color=DARK, bold=False, align="left"):
    f = load_font(size, bold=bold)
    bb = draw.textbbox((0, 0), text, font=f)
    tw = bb[2] - bb[0]
    if align == "center": x = x - tw // 2
    elif align == "right": x = x - tw
    draw.text((x, y), text, font=f, fill=color)
    return bb[3] - bb[1]


def hdr(img, draw, title, subtitle, color=BLUE):
    draw.rectangle((0, 0, W, 72), fill=color)
    txt(draw, W//2, 10, title, 26, WHITE, bold=True, align="center")
    txt(draw, W//2, 46, subtitle, 15, (210, 225, 255), align="center")


def card(draw, x, y, w, h, fill=CARD_BG, border=None, radius=10):
    shadow_rect(draw, (x, y, x+w, y+h), fill, radius=radius, shadow_offset=3)
    if border:
        draw.rounded_rectangle((x, y, x+w, y+h), radius=radius,
                                fill=fill, outline=border, width=2)


def bar(draw, x, y, w, h, fill, label_top="", label_bot="", pct_label=""):
    draw.rounded_rectangle((x, y, x+w, y+h), radius=4, fill=fill)
    if label_top:
        txt(draw, x+w//2, y-22, label_top, 13, DARK, bold=True, align="center")
    if label_bot:
        txt(draw, x+w//2, y+h+6, label_bot, 12, GREY, align="center")
    if pct_label:
        txt(draw, x+w//2, y+h//2-10, pct_label, 18, WHITE, bold=True, align="center")


# ══════════════════════════════════════════════════════════════════════════════
# A: 泊位比例對比
# ══════════════════════════════════════════════════════════════════════════════
def make_evidence_A():
    H = 700
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    hdr(img, draw,
        "證據 A：香港電單車泊位嚴重不足——數據對比",
        "數據來源：立法會文件 LCQ12 (2024)、LCQ13 (2023)、LCQ15 (2023)  ·  運輸及物流局")

    y = 90

    # ── 大數字摘要 ────────────────────────────────────────────────────────────
    stats = [
        ("74,815", "全港登記電單車數目\n（2023年）", RED),
        ("38,563", "合法電單車泊位總數\n（2023年）", ORANGE),
        ("36,252", "泊位缺口\n（差距輛數）", RED),
        ("0.52", "電單車泊位比\n（每輛車對應泊位）", RED),
        ("1.11", "私家車泊位比\n（同期對比）", GREEN),
    ]
    sw = (W - PAD*2) // len(stats)
    for i, (num, label, col) in enumerate(stats):
        sx = PAD + i*sw
        card(draw, sx+4, y, sw-8, 110, WHITE)
        txt(draw, sx+sw//2, y+12, num, 28, col, bold=True, align="center")
        for li, line in enumerate(label.split("\n")):
            txt(draw, sx+sw//2, y+52+li*20, line, 13, GREY, align="center")
    y += 130

    # ── 橫向比較條形圖 ────────────────────────────────────────────────────────
    txt(draw, PAD, y, "電單車 vs 私家車 泊位比率對比（愈高愈好）", 18, DARK, bold=True)
    y += 32

    chart_h = 180
    chart_x = PAD + 120
    chart_w = W - PAD*2 - 120
    max_ratio = 1.4

    vehicles = [
        ("電單車", 0.52, RED,   "0.52  ❌ 嚴重不足"),
        ("私家車", 1.11, GREEN, "1.11  ✅ 達標"),
    ]
    row_h = chart_h // len(vehicles)
    for i, (name, ratio, col, note) in enumerate(vehicles):
        ry = y + i*row_h + 10
        bar_w = int(chart_w * ratio / max_ratio)
        draw.rounded_rectangle((chart_x, ry, chart_x+bar_w, ry+row_h-20),
                                radius=4, fill=col)
        txt(draw, PAD, ry+10, name, 15, DARK, bold=True)
        txt(draw, chart_x+bar_w+10, ry+10, note, 14, col, bold=True)

    # reference line at 1.0
    ref_x = chart_x + int(chart_w * 1.0 / max_ratio)
    draw.line((ref_x, y, ref_x, y+chart_h), fill=DARK, width=1)
    txt(draw, ref_x-20, y+chart_h+2, "1.0 基準線", 11, DARK)
    y += chart_h + 30

    # ── 地區數據 ─────────────────────────────────────────────────────────────
    txt(draw, PAD, y, "重點地區：使用率長期爆滿", 18, DARK, bold=True)
    y += 32

    districts = [
        ("荃灣 & 葵青", 1355, 100, "連續3年使用率達 100%", RED),
        ("觀塘", 980, 98, "幾乎全日爆滿", ORANGE),
        ("深水埗", 742, 95, "高峰期無位可泊", ORANGE),
        ("旺角/油尖", 612, 100, "連續3年使用率達 100%", RED),
    ]
    dw = (W - PAD*2) // len(districts)
    for i, (dist, spaces, util, note, col) in enumerate(districts):
        dx = PAD + i*dw
        card(draw, dx+4, y, dw-8, 120, WHITE, border=col)
        txt(draw, dx+dw//2, y+10, dist, 14, DARK, bold=True, align="center")
        txt(draw, dx+dw//2, y+34, f"{spaces} 個泊位", 13, GREY, align="center")
        # usage circle
        cx, cy = dx+dw//2, y+78
        draw.ellipse((cx-26, cy-26, cx+26, cy+26), fill=col)
        txt(draw, cx, cy-12, f"{util}%", 16, WHITE, bold=True, align="center")
        txt(draw, cx, cy+8, "使用率", 11, WHITE, align="center")
        txt(draw, dx+dw//2, y+105, note, 11, col, align="center")
    y += 140

    # source note
    txt(draw, PAD, y, "資料來源：立法會文件 LCQ12/2024、LCQ13/2023、LCQ15/2023，運輸及物流局", 11, GREY)

    path = os.path.join(OUT_DIR, "evidence_A_parking_ratio.png")
    img.save(path, dpi=(144, 144))
    print(f"Saved: {path}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
# B: 車身面積 + 不阻塞交通論證
# ══════════════════════════════════════════════════════════════════════════════
def make_evidence_B():
    H = 800
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    hdr(img, draw,
        "證據 B：電單車不等同私家車——面積、影響、罰款均應有別",
        "核心論點：佔用空間少、無阻塞交通，不應與私家車同等重罰",
        color=TEAL)

    y = 90

    # ── 車位面積視覺對比 ──────────────────────────────────────────────────────
    txt(draw, PAD, y, "① 車身面積對比（等比例示意）", 18, DARK, bold=True)
    y += 36

    # 私家車：2.0m × 4.5m = 9 m²  → 顯示為 180×405 px（縮小50倍）
    # 電單車：0.8m × 2.0m = 1.6 m² → 顯示為 72×180 px
    scale = 38  # 1 metre = 38px

    # private car box
    pc_w, pc_h = int(2.0*scale), int(4.5*scale)
    pc_x, pc_y = PAD+60, y
    draw.rounded_rectangle((pc_x, pc_y, pc_x+pc_w, pc_y+pc_h),
                            radius=6, fill=(200,210,230), outline=BLUE, width=2)
    txt(draw, pc_x+pc_w//2, pc_y+pc_h//2-20, "私家車", 16, BLUE, bold=True, align="center")
    txt(draw, pc_x+pc_w//2, pc_y+pc_h//2+4, "≈ 9 m²", 14, BLUE, align="center")

    # motorcycle boxes (how many fit in the same space)
    mc_w, mc_h = int(0.8*scale), int(2.0*scale)
    mc_start_x = pc_x + pc_w + 60
    count = 0
    cols = int(pc_w / mc_w)
    rows = int(pc_h / mc_h)
    for r in range(rows):
        for c in range(cols):
            mx = mc_start_x + c*(mc_w+4)
            my = pc_y + r*(mc_h+4)
            draw.rounded_rectangle((mx, my, mx+mc_w, my+mc_h),
                                    radius=4, fill=(200,240,210), outline=GREEN, width=2)
            count += 1

    arrow(draw, pc_x+pc_w+10, pc_y+pc_h//2, mc_start_x-8, pc_y+pc_h//2, ORANGE, 3)
    txt(draw, mc_start_x + cols*(mc_w+4) + 12, pc_y + 10,
        f"同一空間\n可泊 {count} 輛\n電單車", 14, GREEN, bold=True)
    txt(draw, mc_start_x, pc_y+pc_h+8, "每輛電單車 ≈ 1.6 m²", 12, GREEN)

    # dimension labels
    txt(draw, pc_x-55, pc_y+pc_h//2, "4.5m", 12, BLUE, align="center")
    draw.line((pc_x-30, pc_y, pc_x-30, pc_y+pc_h), fill=BLUE, width=1)
    txt(draw, pc_x+pc_w//2, pc_y+pc_h+8, "2.0m", 12, BLUE, align="center")

    y += pc_h + 50

    # ── 不阻塞交通論點 ────────────────────────────────────────────────────────
    txt(draw, PAD, y, "② 電單車違泊的實際交通影響分析", 18, DARK, bold=True)
    y += 36

    situations = [
        {
            "title": "情況一：泊於指定範圍外，但無阻塞交通、無阻礙行人",
            "impact": "實際交通影響：極微",
            "current": "現時罰款：$400（與最嚴重情況相同）",
            "proposed": "建議：口頭警告或$100象徵性罰款",
            "color": GREEN,
            "icon": "✅",
        },
        {
            "title": "情況二：泊於路邊黃線，未阻塞行車線，只佔行人路小角落",
            "impact": "實際交通影響：輕微",
            "current": "現時罰款：$400",
            "proposed": "建議：$150–200（低於私家車同等情況）",
            "color": ORANGE,
            "icon": "⚠️",
        },
        {
            "title": "情況三：泊於路口轉角，略影響視線，或輕微阻礙行人",
            "impact": "實際交通影響：中等",
            "current": "現時罰款：$400",
            "proposed": "建議：$250（仍低於私家車$400）",
            "color": ORANGE,
            "icon": "⚠️",
        },
        {
            "title": "情況四：泊於行車線、消防通道或嚴重阻塞交通",
            "impact": "實際交通影響：嚴重",
            "current": "現時罰款：$400",
            "proposed": "建議：$400或以上（嚴格執法，此乃合理）",
            "color": RED,
            "icon": "❌",
        },
    ]

    for sit in situations:
        col = sit["color"]
        card(draw, PAD, y, W-PAD*2, 90, WHITE, border=col)
        txt(draw, PAD+14, y+10, sit["icon"] + "  " + sit["title"], 14, DARK, bold=True)
        txt(draw, PAD+14, y+34, sit["impact"], 13, col)
        txt(draw, PAD+14, y+54, sit["current"] + "   →   " + sit["proposed"], 13, col, bold=True)
        y += 100

    warn_box(draw, PAD, y, W-PAD*2,
             "核心原則：罰款應與實際危害成正比。在泊位嚴重不足的情況下，"
             "對無阻塞交通的電單車施以與大型私家車相同的重罰，"
             "既不公平，亦有違比例原則及《基本法》第二十五條。", icon="⚠️ ")

    path = os.path.join(OUT_DIR, "evidence_B_space_comparison.png")
    img.save(path, dpi=(144, 144))
    print(f"Saved: {path}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
# C: 建議分級罰款制度 + 國際比較
# ══════════════════════════════════════════════════════════════════════════════
def make_evidence_C():
    H = 820
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    hdr(img, draw,
        "證據 C：建議分級罰款制度  ＋  國際比較",
        "以實際交通影響為量刑標準，設立合比例的電單車違泊罰款制度",
        color=PURPLE)

    y = 90

    # ── 建議分級制度 ──────────────────────────────────────────────────────────
    txt(draw, PAD, y, "① 建議：電單車違泊四級罰款制度", 18, DARK, bold=True)
    y += 36

    tiers = [
        ("第一級", "無阻塞、無危險\n附近500米內無合法泊位",
         "警告通知書\n（首次）/ $100",
         GREEN, "● 無交通阻塞\n● 無行人阻礙\n● 附近無泊位\n● 車輛完全靠邊"),
        ("第二級", "輕微不當泊車\n未造成實際阻塞",
         "$150–200",
         ORANGE, "● 黃線輕微違規\n● 略佔行人路角落\n● 無阻行車線\n● 能正常通行"),
        ("第三級", "造成中度不便\n影響視線或輕阻行人",
         "$250–300",
         ORANGE, "● 路口轉角泊車\n● 阻礙部分行人\n● 需繞道而行"),
        ("第四級", "嚴重阻塞交通\n或泊於危險位置",
         "$400 或以上\n（現行標準）",
         RED, "● 阻塞行車線\n● 消防通道違泊\n● 嚴重影響交通\n● 危及公共安全"),
    ]

    tw = (W - PAD*2) // len(tiers)
    for i, (tier, cond, fine, col, criteria) in enumerate(tiers):
        tx = PAD + i*tw
        card(draw, tx+3, y, tw-6, 240, WHITE, border=col)
        # tier header
        draw.rounded_rectangle((tx+3, y, tx+tw-3, y+36), radius=10, fill=col)
        txt(draw, tx+tw//2, y+8, tier, 16, WHITE, bold=True, align="center")
        txt(draw, tx+tw//2, y+56, fine, 17, col, bold=True, align="center")
        draw.line((tx+16, y+86, tx+tw-16, y+86), fill=(220,220,220), width=1)
        txt(draw, tx+8, y+94, "條件：", 11, GREY, bold=True)
        for li, line in enumerate(criteria.split("\n")):
            txt(draw, tx+8, y+112+li*18, line, 12, DARK)
    y += 258

    # ── 國際比較表 ────────────────────────────────────────────────────────────
    txt(draw, PAD, y, "② 國際比較：各地電單車 vs 私家車罰款比率", 18, DARK, bold=True)
    y += 36

    comparisons = [
        ("台灣",     "TWD 900",  "TWD 1,800", 50,  GREEN,  "差一倍"),
        ("新加坡",   "SGD 70",   "SGD 100",   70,  GREEN,  "差43%"),
        ("日本",     "¥15,000",  "¥18,000",   83,  ORANGE, "差20%"),
        ("英國",     "£35",      "£70",       50,  GREEN,  "差一倍"),
        ("香港",     "HKD 400",  "HKD 400",   100, RED,    "完全相同 ❌"),
    ]

    col_x = [PAD, PAD+110, PAD+280, PAD+430, PAD+560, PAD+680]
    headers = ["地區", "電單車罰款", "私家車罰款", "電單車\n佔私家車%", "比率", "說明"]
    for ci, (hd, cx) in enumerate(zip(headers, col_x)):
        for li, line in enumerate(hd.split("\n")):
            txt(draw, cx, y+li*16, line, 12, GREY, bold=True)
    y += 36
    draw.line((PAD, y, W-PAD, y), fill=(200,200,200), width=1)
    y += 8

    for region, mc_fine, car_fine, pct, col, note in comparisons:
        bg = (255,235,235) if col == RED else (235,255,240) if col == GREEN else (255,245,225)
        draw.rectangle((PAD-4, y-2, W-PAD+4, y+30), fill=bg)
        txt(draw, col_x[0], y+6, region, 14, DARK, bold=(region=="香港"))
        txt(draw, col_x[1], y+6, mc_fine, 13, DARK)
        txt(draw, col_x[2], y+6, car_fine, 13, DARK)
        # percentage bar
        bw = int(120 * pct / 100)
        draw.rounded_rectangle((col_x[3], y+4, col_x[3]+bw, y+24), radius=3, fill=col)
        txt(draw, col_x[3]+bw+6, y+6, f"{pct}%", 13, col, bold=True)
        txt(draw, col_x[5], y+6, note, 13, col, bold=(region=="香港"))
        y += 34

    y += 10
    success_box(draw, PAD, y, W-PAD*2,
                "結論：香港是極少數對電單車和私家車施以完全相同違泊罰款的已發展地區，"
                "不符合國際慣例，亦有違比例原則。")

    path = os.path.join(OUT_DIR, "evidence_C_fine_tiers.png")
    img.save(path, dpi=(144, 144))
    print(f"Saved: {path}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
# D: 罰款收入流向 + 改善建議
# ══════════════════════════════════════════════════════════════════════════════
def make_evidence_D():
    H = 780
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    hdr(img, draw,
        "證據 D：罰款收入流向分析  ＋  建議改善方案",
        "數據來源：香港財政預算案 2025、am730、HK01、政府憲報",
        color=RED)

    y = 90

    # ── 收入數字 ─────────────────────────────────────────────────────────────
    txt(draw, PAD, y, "① 違例泊車罰款收入（全車種）", 18, DARK, bold=True)
    y += 36

    revenue_data = [
        ("2022/23", 7.8, RED),
        ("2023/24", 8.1, RED),
        ("2024/25", 8.4, ORANGE),
        ("2025/26\n（預算）", 9.8, ORANGE),
        ("2026/27\n（估計）", 12.0, RED),
    ]

    max_rev = 13.0
    chart_base = y + 160
    bar_w = 100
    gap = (W - PAD*2 - len(revenue_data)*bar_w) // (len(revenue_data)+1)
    for i, (yr, rev, col) in enumerate(revenue_data):
        bx = PAD + gap + i*(bar_w+gap)
        bh = int(140 * rev / max_rev)
        by = chart_base - bh
        draw.rounded_rectangle((bx, by, bx+bar_w, chart_base), radius=4, fill=col)
        txt(draw, bx+bar_w//2, by-22, f"${rev}億", 14, col, bold=True, align="center")
        for li, line in enumerate(yr.split("\n")):
            txt(draw, bx+bar_w//2, chart_base+8+li*16, line, 12, GREY, align="center")
    draw.line((PAD, chart_base, W-PAD, chart_base), fill=DARK, width=1)
    txt(draw, PAD, chart_base+44, "* 2026/27估計值：按$400罰款及預算發出量推算  |  單位：港幣億元", 11, GREY)
    y = chart_base + 72

    # ── 資金流向（現況 vs 建議）──────────────────────────────────────────────
    txt(draw, PAD, y, "② 資金流向對比：現況 vs 建議改革", 18, DARK, bold=True)
    y += 36

    half = (W - PAD*3) // 2

    # 現況
    card(draw, PAD, y, half, 220, (255,235,235), border=RED)
    txt(draw, PAD+half//2, y+12, "❌ 現況（問題所在）", 16, RED, bold=True, align="center")
    current_items = [
        "收取違泊罰款 → 全數入庫房",
        "電單車泊位供應：幾乎零增長",
        "車主被逼違泊 → 再被罰款",
        "政府收入增加 但問題無改善",
        "循環剝削，欠缺解決根本問題",
    ]
    for li, item in enumerate(current_items):
        txt(draw, PAD+16, y+46+li*30, "• " + item, 13, RED)

    # 建議
    card(draw, PAD*2+half, y, half, 220, (232,245,233), border=GREEN)
    txt(draw, PAD*2+half+half//2, y+12, "✅ 建議改革方案", 16, GREEN, bold=True, align="center")
    proposed_items = [
        "罰款收入設立專項基金",
        "30%專款用於增設電單車泊位",
        "20%用於維修現有設施",
        "20%用於研究智能泊車方案",
        "剩餘30%才歸入一般庫房",
    ]
    for li, item in enumerate(proposed_items):
        txt(draw, PAD*2+half+16, y+46+li*30, "✓ " + item, 13, GREEN)

    y += 238

    # ── 短中長期方案 ─────────────────────────────────────────────────────────
    txt(draw, PAD, y, "③ 建議改善方案時間表", 18, DARK, bold=True)
    y += 36

    phases = [
        ("即時\n（3個月內）", BLUE, [
            "暫緩對無阻塞電單車違泊發票",
            "公布罰款收入詳細用途報告",
            "設立緊急泊位投訴快速通道",
        ]),
        ("短期\n（1年內）", GREEN, [
            "全港新增5,000個電單車泊位",
            "優先利用高架橋底、政府用地",
            "推出智能電單車泊位App",
        ]),
        ("中期\n（3年內）", ORANGE, [
            "制定電單車泊位法定比例標準",
            "訂立差別罰款制度立法建議",
            "設立泊位專項資金機制",
        ]),
        ("長期\n（5年內）", PURPLE, [
            "消除電單車泊位缺口36,252個",
            "全面實施分級罰款制度",
            "定期向公眾公布改善成效",
        ]),
    ]

    pw = (W - PAD*2) // len(phases)
    for i, (phase, col, items) in enumerate(phases):
        px = PAD + i*pw
        card(draw, px+3, y, pw-6, 190, WHITE, border=col)
        draw.rounded_rectangle((px+3, y, px+pw-3, y+40), radius=8, fill=col)
        for li, line in enumerate(phase.split("\n")):
            txt(draw, px+pw//2, y+6+li*18, line, 14, WHITE, bold=True, align="center")
        for li, item in enumerate(items):
            txt(draw, px+10, y+50+li*38, "▸ " + item, 12, DARK)

    path = os.path.join(OUT_DIR, "evidence_D_revenue_flow.png")
    img.save(path, dpi=(144, 144))
    print(f"Saved: {path}")
    return path


if __name__ == "__main__":
    paths = [
        make_evidence_A(),
        make_evidence_B(),
        make_evidence_C(),
        make_evidence_D(),
    ]
    print(f"\n✅ 全部 {len(paths)} 張證據圖解已儲存至 guides/")
