"""
Generates two visual guides:
  05a_fix_consent_screen.png  — rename app from "SSSS" to real name
  05b_get_auth_code.png       — open URL, click Allow, copy code from address bar
"""
import os, sys, math, textwrap
sys.path.insert(0, os.path.dirname(__file__))
from make_guide import (
    load_font, OUT_DIR, shadow_rect, warn_box, success_box,
    arrow, button, url_bar, step_circle, highlight_box,
    BG, CARD_BG, TITLE_COL, BODY_COL, STEP_CIRCLE,
    BTN_BLUE, BTN_GREEN, BTN_RED, ARROW_COL, WARN_BG, WARN_BORDER, WARN_TEXT,
    SUCCESS_BG, SUCCESS_BD, SUCCESS_T, HIGHLIGHT, TITLE_COL as DARK,
)
from PIL import Image, ImageDraw

W = 960
PAD = 28

# ── colour extras ─────────────────────────────────────────────────────────────
GREY_LIGHT = (241, 243, 244)
GREY_MID   = (189, 193, 198)
GREY_DARK  = (95,  99, 104)
RED        = (234,  67,  53)
GREEN      = ( 52, 168,  83)
BLUE       = ( 66, 133, 244)
ORANGE     = (251, 140,   0)
WHITE      = (255, 255, 255)
BLOCKED    = (255, 235, 238)
BLOCKED_B  = (239,  83,  80)
SIDEBAR_BG = (32,  33,  36)
MENU_HOVER = (66, 133, 244)


# ── helpers ───────────────────────────────────────────────────────────────────
def txt(draw, x, y, text, size=16, color=DARK, bold=False, align="left"):
    f = load_font(size, bold=bold)
    bb = draw.textbbox((0, 0), text, font=f)
    tw = bb[2] - bb[0]
    if align == "center":
        x = x - tw // 2
    elif align == "right":
        x = x - tw
    draw.text((x, y), text, font=f, fill=color)
    return bb[3] - bb[1]


def card(draw, x, y, w, h, fill=CARD_BG, border=None, radius=12, bw=2):
    shadow_rect(draw, (x, y, x+w, y+h), fill, radius=radius, shadow_offset=4)
    if border:
        draw.rounded_rectangle((x, y, x+w, y+h), radius=radius,
                                fill=fill, outline=border, width=bw)


def header_bar(img, draw, title, subtitle, color=STEP_CIRCLE):
    draw.rectangle((0, 0, W, 75), fill=color)
    txt(draw, W//2, 12, title, 28, WHITE, bold=True, align="center")
    txt(draw, W//2, 48, subtitle, 16, (200, 220, 255), align="center")


def section_label(draw, x, y, text):
    txt(draw, x, y, text, 19, DARK, bold=True)
    draw.line((x, y+28, x+W-x*2, y+28), fill=GREY_MID, width=1)


def gcloud_chrome_chrome(draw, x, y, w, h, url_text):
    """Draw a mini Chrome window mock with address bar."""
    # window frame
    draw.rounded_rectangle((x, y, x+w, y+h), radius=8, fill=(235,237,240),
                            outline=GREY_MID, width=1)
    # tab bar
    draw.rectangle((x, y, x+w, y+28), fill=(218,220,224))
    draw.rounded_rectangle((x+8, y+4, x+200, y+26), radius=4, fill=WHITE)
    txt(draw, x+18, y+7, "Google Cloud Console", 11, GREY_DARK)
    # close/min/max dots
    for ix, col in enumerate([(234,67,53),(251,188,4),(52,168,83)]):
        draw.ellipse((x+w-18-ix*20, y+10, x+w-8-ix*20, y+20), fill=col)
    # address bar
    draw.rounded_rectangle((x+80, y+32, x+w-40, y+56), radius=4,
                            fill=WHITE, outline=GREY_MID, width=1)
    # lock
    draw.ellipse((x+90, y+40, x+100, y+50), outline=GREEN, width=1)
    draw.rectangle((x+92, y+45, x+98, y+50), fill=GREEN)
    txt(draw, x+108, y+38, url_text, 13, BLUE)


def sidebar_item(draw, x, y, w, label, icon="", active=False):
    if active:
        draw.rounded_rectangle((x, y, x+w, y+34), radius=6, fill=MENU_HOVER)
        txt(draw, x+12, y+8, icon + " " + label, 15, WHITE, bold=True)
    else:
        txt(draw, x+12, y+8, icon + " " + label, 15, (180, 190, 200))


def input_field(draw, x, y, w, value, placeholder="", filled=False):
    fill = WHITE if filled else GREY_LIGHT
    border = BLUE if filled else GREY_MID
    bw = 2 if filled else 1
    draw.rounded_rectangle((x, y, x+w, y+36), radius=6,
                            fill=fill, outline=border, width=bw)
    col = DARK if filled else (160, 165, 170)
    txt(draw, x+10, y+9, value or placeholder, 15, col)
    if filled:
        # blinking cursor simulation
        f = load_font(15)
        bb = draw.textbbox((0, 0), value, font=f)
        cx = x + 10 + (bb[2]-bb[0]) + 3
        draw.line((cx, y+8, cx, y+28), fill=BLUE, width=2)


def badge(draw, x, y, text, color=GREEN):
    f = load_font(13, bold=True)
    bb = draw.textbbox((0, 0), text, font=f)
    w = bb[2]-bb[0]+16
    h = 22
    draw.rounded_rectangle((x, y, x+w, y+h), radius=11, fill=color)
    draw.text((x+8, y+4), text, font=f, fill=WHITE)
    return w


def number_badge(draw, cx, cy, n, r=18, color=STEP_CIRCLE):
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=color)
    f = load_font(18, bold=True)
    s = str(n)
    bb = draw.textbbox((0,0), s, font=f)
    draw.text((cx-(bb[2]-bb[0])//2, cy-(bb[3]-bb[1])//2-1), s, font=f, fill=WHITE)


# ══════════════════════════════════════════════════════════════════════════════
# GUIDE A: Fix consent screen name
# ══════════════════════════════════════════════════════════════════════════════
def make_consent_screen_guide():
    H = 1480
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    header_bar(img, draw,
               "步驟 A：修改 OAuth 同意畫面名稱",
               "將錯誤的「SSSS」改為正確的應用程式名稱  ·  預計 3 分鐘")

    y = 90

    # ── STEP 1 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "① 打開 Google Cloud Console")
    y += 40

    card(draw, PAD, y, W-PAD*2, 180)
    gcloud_chrome_chrome(draw, PAD+20, y+15, W-PAD*2-40, 155,
                         "console.cloud.google.com")
    # arrow + instruction
    txt(draw, PAD+20, y+145, "在瀏覽器輸入上方網址，然後按 Enter", 15, GREY_DARK)
    y += 200

    # ── STEP 2 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "② 選擇正確的專案")
    y += 40

    card(draw, PAD, y, W-PAD*2, 130)
    # project selector mock
    draw.rounded_rectangle((PAD+20, y+20, PAD+380, y+56), radius=6,
                            fill=GREY_LIGHT, outline=BLUE, width=2)
    txt(draw, PAD+30, y+30, "aerial-optics-489214-j7", 15, DARK)
    txt(draw, PAD+330, y+30, "▼", 15, BLUE)
    arrow(draw, PAD+395, y+38, PAD+460, y+38, ARROW_COL, 3)
    txt(draw, PAD+470, y+30, "確認這個專案已被選中", 15, GREY_DARK)
    badge(draw, PAD+20, y+75, "✓ 正確的專案")
    y += 150

    # ── STEP 3 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "③ 點擊左側選單：APIs & Services")
    y += 40

    card(draw, PAD, y, W-PAD*2, 250)
    # sidebar mock
    draw.rounded_rectangle((PAD+20, y+15, PAD+240, y+235), radius=8,
                            fill=SIDEBAR_BG)
    menu_items = [
        ("Dashboard",         "⊞", False),
        ("APIs & Services",   "◈", False),
        ("  → OAuth consent", "  ", True),
        ("IAM & Admin",       "⚙", False),
        ("Billing",           "$", False),
    ]
    my = y + 30
    for label, icon, active in menu_items:
        sidebar_item(draw, PAD+28, my, 225, label, icon, active)
        my += 38

    # arrow pointing to the active item
    arrow(draw, PAD+270, y+98, PAD+265, y+118, ARROW_COL, 3)
    txt(draw, PAD+275, y+110, "點擊「APIs & Services」", 15, GREY_DARK)
    txt(draw, PAD+275, y+135, "然後點擊「OAuth consent screen」", 15, GREY_DARK)

    # zoom highlight
    draw.rounded_rectangle((PAD+20, y+148, PAD+240, y+182), radius=6,
                            fill=MENU_HOVER, outline=BLUE, width=2)
    txt(draw, PAD+28, y+158, "  OAuth consent screen  ←", 15, WHITE, bold=True)
    y += 270

    # ── STEP 4 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "④ 點擊「Edit App」按鈕")
    y += 40

    card(draw, PAD, y, W-PAD*2, 200)
    # page mock
    txt(draw, PAD+30, y+20, "OAuth consent screen", 18, DARK, bold=True)
    draw.line((PAD+20, y+48, W-PAD-20, y+48), fill=GREY_MID, width=1)

    # app info row
    draw.rounded_rectangle((PAD+20, y+60, W-PAD-120, y+110), radius=6,
                            fill=GREY_LIGHT, outline=GREY_MID, width=1)
    txt(draw, PAD+35, y+68, "App name:", 14, GREY_DARK)
    txt(draw, PAD+160, y+68, "SSSS", 18, RED, bold=True)  # the wrong name
    draw.line((PAD+155, y+88, PAD+240, y+90), fill=RED, width=3)  # red underline

    # Edit App button
    bw = button(draw, W-PAD-140, y+70, "Edit App", BTN_BLUE, h=36)
    arrow(draw, W-PAD-160, y+88, W-PAD-148, y+88, ARROW_COL, 3)

    warn_box(draw, PAD+20, y+125, W-PAD*2-40,
             "App name 顯示「SSSS」是因為之前設定時沒有輸入正確名稱，現在需要修改")
    y += 220

    # ── STEP 5 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "⑤ 修改 App name → 儲存")
    y += 40

    card(draw, PAD, y, W-PAD*2, 220)
    txt(draw, PAD+30, y+20, "Edit app registration", 18, DARK, bold=True)

    # App name field - before
    txt(draw, PAD+30, y+55, "App name *", 14, GREY_DARK)
    draw.rounded_rectangle((PAD+30, y+75, PAD+480, y+111), radius=6,
                            fill=BLOCKED, outline=RED, width=2)
    txt(draw, PAD+42, y+85, "SSSS", 16, RED)
    txt(draw, PAD+500, y+85, "← 刪除這個", 14, RED)

    # arrow down
    arrow(draw, PAD+255, y+115, PAD+255, y+135, GREEN, 3)

    # App name field - after
    draw.rounded_rectangle((PAD+30, y+138, PAD+480, y+174), radius=6,
                            fill=(232,245,233), outline=GREEN, width=2)
    txt(draw, PAD+42, y+148, "Claude Email Project", 16, GREEN, bold=True)
    txt(draw, PAD+500, y+148, "← 輸入這個", 14, GREEN, bold=True)

    button(draw, W-PAD-170, y+175, "Save and Continue", BTN_GREEN, h=36)
    y += 240

    # ── STEP 6 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "⑥ 一直點 Save and Continue 直至完成")
    y += 40

    card(draw, PAD, y, W-PAD*2, 120)
    steps_flow = ["App information", "Scopes", "Test users", "Summary"]
    sw = (W-PAD*2-40) // len(steps_flow)
    for fi, fs in enumerate(steps_flow):
        fx = PAD+20 + fi*sw
        col = GREEN if fi < 2 else BLUE if fi == 2 else GREY_MID
        draw.ellipse((fx+sw//2-16, y+18, fx+sw//2+16, y+50), fill=col)
        txt(draw, fx+sw//2, y+56+2, fs, 12, DARK, align="center")
        if fi < len(steps_flow)-1:
            draw.line((fx+sw//2+20, y+34, fx+sw+sw//2-20, y+34),
                      fill=GREY_MID, width=2)
    success_box(draw, PAD+20, y+85, W-PAD*2-40, "全部頁面都點 Save and Continue 即完成！")
    y += 140

    path = os.path.join(OUT_DIR, "05a_fix_consent_screen.png")
    img = img.crop((0, 0, W, y + PAD))
    img.save(path, dpi=(144, 144))
    print(f"Saved: {path}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
# GUIDE B: Get the auth code from browser
# ══════════════════════════════════════════════════════════════════════════════
def make_auth_code_guide():
    H = 1600
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    header_bar(img, draw,
               "步驟 B：完成 Gmail 授權，取得授權碼",
               "打開授權網址 → 點擊允許 → 複製網址列的 code  ·  預計 2 分鐘",
               color=(52, 168, 83))

    y = 90

    AUTH_URL = ("https://accounts.google.com/o/oauth2/auth?response_type=code"
                "&client_id=518155116135-341us3s96u6vc3egvmqm1i91gcs3jhh8..."
                "&redirect_uri=http%3A%2F%2Flocalhost&scope=...&access_type=offline")

    # ── STEP 1 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "① 複製以下授權網址，在瀏覽器打開")
    y += 40

    card(draw, PAD, y, W-PAD*2, 150)
    # URL display box
    draw.rounded_rectangle((PAD+20, y+18, W-PAD-20, y+72), radius=8,
                            fill=(232, 240, 255), outline=BLUE, width=2)
    txt(draw, PAD+30, y+22, "完整授權網址（複製此網址）:", 13, GREY_DARK)
    full_url = ("https://accounts.google.com/o/oauth2/auth?response_type=code"
                "&client_id=518155116135-341us3s96u6vc3egvmqm1i91gcs3jhh8"
                ".apps.googleusercontent.com&redirect_uri=http%3A%2F%2Flocalhost"
                "&scope=https%3A%2F%2Fmail.google.com%2F&access_type=offline&prompt=consent")
    # truncated display
    disp = full_url[:90] + "..."
    txt(draw, PAD+30, y+40, disp, 12, BLUE)
    badge(draw, PAD+20, y+85, "Ctrl+C / Cmd+C 複製")
    txt(draw, PAD+180, y+88, "然後在瀏覽器網址列貼上，按 Enter", 14, GREY_DARK)
    y += 170

    # ── STEP 2 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "② 登入 Google 帳號")
    y += 40

    card(draw, PAD, y, W-PAD*2, 240)
    # Google login mock
    cx = W // 2
    # google logo text
    txt(draw, cx, y+20, "Google", 30, BLUE, bold=True, align="center")

    # email field
    txt(draw, PAD+160, y+72, "電郵地址或電話號碼", 14, GREY_DARK)
    input_field(draw, PAD+160, y+95, W-PAD*2-320, "clawtienand7@gmail.com", filled=True)
    txt(draw, PAD+160, y+140, "密碼", 14, GREY_DARK)
    draw.rounded_rectangle((PAD+160, y+162, W-PAD*2-160, y+198), radius=6,
                            fill=GREY_LIGHT, outline=GREY_MID, width=1)
    txt(draw, PAD+170, y+171, "●●●●●●●●", 16, GREY_DARK)

    # next button
    button(draw, W-PAD-170, y+205, "下一步 →", BTN_BLUE, h=36)
    y += 260

    # ── STEP 3 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "③ 點擊「允許 (Allow)」按鈕")
    y += 40

    card(draw, PAD, y, W-PAD*2, 310)
    cx = W // 2

    # OAuth consent page mock
    draw.rounded_rectangle((cx-180, y+15, cx+180, y+295), radius=10,
                            fill=WHITE, outline=GREY_MID, width=1)
    # App requesting
    txt(draw, cx, y+30, "Claude Email Project", 18, DARK, bold=True, align="center")
    txt(draw, cx, y+56, "想要存取你的 Google 帳號", 14, GREY_DARK, align="center")
    txt(draw, cx, y+78, "clawtienand7@gmail.com", 14, BLUE, align="center")
    draw.line((cx-160, y+100, cx+160, y+100), fill=GREY_LIGHT, width=1)

    # Permissions
    perms = [
        ("✉", "讀取、撰寫及傳送電郵"),
        ("📁", "管理你的郵箱"),
    ]
    py = y + 112
    for icon, perm in perms:
        txt(draw, cx-155, py, icon, 16, BLUE)
        txt(draw, cx-130, py, perm, 14, DARK)
        py += 28

    draw.line((cx-160, py+8, cx+160, py+8), fill=GREY_LIGHT, width=1)

    # Buttons
    button(draw, cx-165, py+20, "取消", (120,120,120), w=130, h=40)
    button(draw, cx+35, py+20, "允許", BTN_BLUE, w=130, h=40)

    # Arrow pointing to Allow
    arrow(draw, cx+200, py+40, cx+175, py+40, ARROW_COL, 4)
    txt(draw, cx+205, py+32, "← 點這裡！", 15, RED, bold=True)
    y += 330

    # ── STEP 4 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "④ 瀏覽器跳到 localhost（連線失敗是正常的！）")
    y += 40

    card(draw, PAD, y, W-PAD*2, 210)

    # Chrome window with error page
    gcloud_chrome_chrome(draw, PAD+20, y+15, W-PAD*2-40, 185,
                         "localhost/?code=4/0AX4XfWj...")

    # Highlight the URL bar with code
    draw.rounded_rectangle((PAD+38+80-2, y+30, W-PAD-62, y+56+2),
                            radius=5, fill=None, outline=ORANGE, width=3)

    # Error page content area
    draw.rectangle((PAD+20, y+62, W-PAD-20, y+190), fill=(248,249,250))
    txt(draw, PAD+80, y+80, "ERR_CONNECTION_REFUSED", 22, RED, bold=True)
    txt(draw, PAD+80, y+112, "此網站無法連線", 16, GREY_DARK)
    txt(draw, PAD+80, y+136, "localhost 拒絕了連線。", 14, GREY_DARK)

    # Arrow pointing to URL bar
    arrow(draw, PAD+500, y+190, PAD+400, y+48, ORANGE, 4)
    warn_box(draw, PAD+380, y+190, W-PAD-400,
             "不要按返回！注意看網址列！")
    y += 230

    # ── STEP 5 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "⑤ 複製網址列的完整網址")
    y += 40

    card(draw, PAD, y, W-PAD*2, 240)

    # Address bar zoom in
    txt(draw, PAD+20, y+18, "放大看網址列：", 15, DARK, bold=True)
    # outer bar
    draw.rounded_rectangle((PAD+20, y+42, W-PAD-20, y+90), radius=8,
                            fill=WHITE, outline=ORANGE, width=3)
    # lock icon
    draw.ellipse((PAD+34, y+55, PAD+46, y+77), outline=GREEN, width=2)
    draw.rectangle((PAD+37, y+65, PAD+43, y+77), fill=GREEN)
    full_url_example = "localhost/?code=4/0AX4XfWjGxxxxxx&scope=https%3A%2F%2Fmail.google.com%2F"
    txt(draw, PAD+54, y+54, full_url_example, 14, BLUE)

    # Highlight code part
    f14 = load_font(14)
    prefix = "localhost/?code="
    bb_prefix = draw.textbbox((0,0), prefix, font=f14)
    prefix_w = bb_prefix[2]-bb_prefix[0]
    code_part = "4/0AX4XfWjGxxxxxx"
    bb_code = draw.textbbox((0,0), code_part, font=f14)
    code_w = bb_code[2]-bb_code[0]
    hx = PAD+54 + prefix_w
    draw.rounded_rectangle((hx-3, y+50, hx+code_w+3, y+72),
                            radius=3, fill=HIGHLIGHT, outline=WARN_BORDER, width=1)
    txt(draw, hx, y+54, code_part, 14, (80, 50, 0))

    # Select all instruction
    txt(draw, PAD+20, y+105, "操作方法：", 15, DARK, bold=True)
    steps_inline = [
        ("1.", "點擊瀏覽器網址列"),
        ("2.", "按 Ctrl+A (Windows) 或 Cmd+A (Mac) 全選"),
        ("3.", "按 Ctrl+C 或 Cmd+C 複製"),
    ]
    for si, (num, step) in enumerate(steps_inline):
        txt(draw, PAD+30, y+130+si*30, num, 15, BLUE, bold=True)
        txt(draw, PAD+55, y+130+si*30, step, 15, DARK)

    success_box(draw, PAD+20, y+225, W-PAD*2-40,
                "整條網址應以 http://localhost/?code=4/0AX... 開頭")
    y += 260

    # ── STEP 6 ────────────────────────────────────────────────────────────────
    section_label(draw, PAD, y, "⑥ 貼回對話框完成授權")
    y += 40

    card(draw, PAD, y, W-PAD*2, 180)
    # chat input mock
    draw.rounded_rectangle((PAD+20, y+20, W-PAD-20, y+80), radius=8,
                            fill=(40,44,52), outline=GREY_MID, width=1)
    txt(draw, PAD+30, y+25, "你 (Claude Code 對話框):", 13, (150,150,150))
    txt(draw, PAD+30, y+46, "http://localhost/?code=4/0AX4XfWj...", 14,
        (97,175,239))

    txt(draw, PAD+20, y+100, "貼上完整的 localhost 網址（不只是 code 部份），", 15, DARK)
    txt(draw, PAD+20, y+122, "系統會自動提取授權碼並完成設定。", 15, DARK)

    success_box(draw, PAD+20, y+148, W-PAD*2-40,
                "授權完成後，gmail_token.json 會自動儲存，以後無需再授權！")
    y += 200

    path = os.path.join(OUT_DIR, "05b_get_auth_code.png")
    img = img.crop((0, 0, W, y + PAD))
    img.save(path, dpi=(144, 144))
    print(f"Saved: {path}")
    return path


if __name__ == "__main__":
    p1 = make_consent_screen_guide()
    p2 = make_auth_code_guide()
    print(f"\n✅ 兩張圖解已儲存到 guides/")
