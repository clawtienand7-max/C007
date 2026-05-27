"""
Google Cloud Console OAuth credential setup — visual step-by-step guide.
Generates guide images to guides/04_gcloud_*.png
"""
from PIL import Image, ImageDraw
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from make_guide import (load_font, OUT_DIR, shadow_rect, arrow,
                        BG, CARD_BG, STEP_CIRCLE, TITLE_COL as DARK, BODY_COL,
                        HIGHLIGHT, WARN_BORDER, ARROW_COL,
                        BTN_GREEN, BTN_BLUE, BTN_RED, BTN_TEXT, CARD_SHADOW)

W = 1000

# ── colour helpers ────────────────────────────────────────────────────────────
WHITE  = (255,255,255)
GREY   = (149,157,165)
LGREY  = (241,243,244)
DGREY  = ( 60, 64, 67)
BLUE   = ( 66,133,244)
GREEN  = ( 52,168, 83)
RED    = (234, 67, 53)
YELLOW = (251,188,  4)
NAV_BG = ( 32, 33, 36)
SIDEBAR= ( 40, 44, 52)
ORANGE = (251,140,  0)

def lbl(draw, x, y, text, size=15, color=DARK, bold=False, center=False):
    f = load_font(size, bold=bold)
    bb = draw.textbbox((0,0), text, font=f)
    tw = bb[2]-bb[0]
    if center: x -= tw//2
    draw.text((x, y), text, font=f, fill=color)
    return bb[3]-bb[1]+2

def box(draw, x, y, w, h, fill, border=None, radius=8, bw=2):
    kw = dict(radius=radius, fill=fill)
    if border: kw["outline"], kw["width"] = border, bw
    draw.rounded_rectangle((x,y,x+w,y+h), **kw)

def btn(draw, x, y, text, color=BLUE, h=36, w=None):
    f = load_font(15, bold=True)
    bb = draw.textbbox((0,0), text, font=f)
    tw = bb[2]-bb[0]
    bw = w or tw+32
    box(draw, x, y, bw, h, color, radius=6)
    lbl(draw, x+(bw-tw)//2, y+(h-(bb[3]-bb[1]))//2, text, 15, WHITE, bold=True)
    return bw

def chip(draw, x, y, text, color=BLUE):
    f = load_font(13)
    bb = draw.textbbox((0,0), text, font=f)
    tw = bb[2]-bb[0]; th = bb[3]-bb[1]
    box(draw, x, y, tw+16, th+10, color+(40,) if len(color)==3 else color,
        border=color, radius=12, bw=1)
    draw.text((x+8, y+5), text, font=f, fill=color)

def google_topbar(draw, y, title=""):
    draw.rectangle((0,y,W,y+56), fill=WHITE)
    draw.rectangle((0,y+55,W,y+56), fill=(218,220,224))
    # hamburger
    for i in range(3):
        draw.rectangle((16,y+18+i*9,34,y+22+i*9), fill=DGREY)
    # Google logo colours
    for i,(c,t) in enumerate([(BLUE,'G'),(RED,'o'),(YELLOW,'o'),(BLUE,'g'),(GREEN,'l'),(RED,'e')]):
        lbl(draw, 48+i*14, y+16, t, 20, c, bold=True)
    lbl(draw, 104, y+16, " Cloud", 20, DGREY, bold=False)
    # project selector
    box(draw, 200, y+12, 220, 32, LGREY, (218,220,224), radius=6)
    lbl(draw, 212, y+20, "My Project ▾", 14, DGREY)
    # search bar
    box(draw, 440, y+12, 340, 32, LGREY, (218,220,224), radius=16)
    lbl(draw, 460, y+20, "🔍  搜尋產品和資源", 13, GREY)
    # title
    if title:
        lbl(draw, W//2, y+18, title, 16, DGREY, center=True)

def sidebar_item(draw, x, y, text, active=False, icon=""):
    if active:
        box(draw, x, y, 220, 36, (232,240,254), radius=6)
        lbl(draw, x+38, y+10, text, 14, BLUE, bold=True)
    else:
        lbl(draw, x+38, y+10, text, 14, (189,193,198))
    if icon:
        lbl(draw, x+10, y+10, icon, 14, BLUE if active else GREY)

def step_header(draw, num, title, subtitle="", y_off=0):
    """Draw a full-width step header bar."""
    draw.rectangle((0, y_off, W, y_off+72), fill=BLUE)
    # Circle
    cx = 52
    draw.ellipse((cx-26, y_off+10, cx+26, y_off+62), fill=WHITE)
    lbl(draw, cx, y_off+22, str(num), 26, BLUE, bold=True, center=True)
    lbl(draw, 96, y_off+12, title,    24, WHITE, bold=True)
    if subtitle:
        lbl(draw, 96, y_off+46, subtitle, 15, (200,220,255))

def highlight_ring(draw, x, y, w, h, color=RED, width=3):
    draw.rounded_rectangle((x-width, y-width, x+w+width, y+h+width),
                            radius=10, outline=color, width=width)
    # arrow pointing to top-left
    arrow(draw, x+w+width+30, y-20, x+w+width+4, y-4, color, 3)

def callout(draw, x, y, text, color=RED):
    f = load_font(14, bold=True)
    bb = draw.textbbox((0,0), text, font=f)
    tw = bb[2]-bb[0]; th = bb[3]-bb[1]
    box(draw, x, y, tw+20, th+12, color, radius=6)
    draw.text((x+10, y+6), text, font=f, fill=WHITE)


# ═══════════════════════════════════════════════════════════════════════════════
# Step 1 – Open console and create project
# ═══════════════════════════════════════════════════════════════════════════════
def step1():
    H = 560
    img = Image.new("RGB", (W,H), BG)
    d   = ImageDraw.Draw(img)

    step_header(d, 1, "打開 Google Cloud Console，建立新專案",
                "瀏覽器輸入網址 → 建立專案")

    # browser bar
    box(d, 20, 84, W-40, 42, WHITE, (218,220,224), radius=6)
    box(d, 28, 90, 20, 30, LGREY, radius=4)   # back btn
    box(d, 54, 90, 20, 30, LGREY, radius=4)   # fwd btn
    box(d, 80, 90, 640, 30, LGREY, (180,182,186), radius=15)
    lbl(d, 96, 97, "🔒  console.cloud.google.com", 14, (26,115,232))
    highlight_ring(d, 80, 90, 640, 30, RED, 3)
    callout(d, 740, 88, "① 輸入此網址")

    # Google Cloud topbar
    google_topbar(d, 136)

    # New project dialog mock
    box(d, 150, 205, 680, 320, WHITE, (218,220,224), radius=12)
    lbl(d, 480, 218, "新增專案", 20, DARK, bold=True, center=True)
    d.line((150,248,830,248), fill=(218,220,224), width=1)

    lbl(d, 175, 262, "專案名稱 *", 14, DGREY)
    box(d, 175, 284, 460, 38, LGREY, (66,133,244), radius=6, bw=2)
    lbl(d, 185, 293, "Claude Email Project", 15, DARK)
    highlight_ring(d, 175, 284, 460, 38, BLUE, 2)
    callout(d, 650, 280, "② 輸入專案名稱")

    lbl(d, 175, 338, "機構", 14, DGREY)
    box(d, 175, 358, 460, 38, LGREY, (218,220,224), radius=6)
    lbl(d, 185, 367, "無機構", 14, GREY)

    d.line((150,408,830,408), fill=(218,220,224), width=1)
    btn(d, 620, 420, "建立", GREEN, h=36)
    highlight_ring(d, 620, 420, 64, 36, GREEN, 3)
    callout(d, 700, 416, "③ 按「建立」")
    btn(d, 530, 420, "取消", (150,150,150), h=36)

    path = os.path.join(OUT_DIR, "04a_step1_create_project.png")
    img.save(path, dpi=(144,144)); print(f"Saved: {path}"); return path


# ═══════════════════════════════════════════════════════════════════════════════
# Step 2 – Enable Gmail API
# ═══════════════════════════════════════════════════════════════════════════════
def step2():
    H = 580
    img = Image.new("RGB", (W,H), BG)
    d   = ImageDraw.Draw(img)

    step_header(d, 2, "啟用 Gmail API",
                "API 和服務 → 程式庫 → 搜尋 Gmail → 啟用")

    google_topbar(d, 80)

    # sidebar
    box(d, 0, 136, 240, H-136, (248,249,250), radius=0)
    sidebar_item(d, 10, 148, "首頁",      icon="🏠")
    sidebar_item(d, 10, 188, "API 和服務", icon="🔧", active=True)
    sidebar_item(d, 10, 228, "IAM 和管理員", icon="👤")
    sidebar_item(d, 10, 268, "結算",       icon="💳")

    # API Library page
    box(d, 250, 136, W-260, H-146, WHITE, (218,220,224), radius=8)
    lbl(d, 280, 150, "API 程式庫", 20, DARK, bold=True)

    # Search bar
    box(d, 280, 182, 500, 42, LGREY, (66,133,244), radius=20, bw=2)
    lbl(d, 300, 194, "🔍  Gmail API", 15, DARK)
    highlight_ring(d, 280, 182, 500, 42, RED, 3)
    callout(d, 800, 180, "① 搜尋 Gmail")

    # Result card
    box(d, 280, 245, 320, 160, WHITE, (218,220,224), radius=10)
    box(d, 295, 258, 40, 40, (234,67,53), radius=8)
    lbl(d, 315, 270, "G", 22, WHITE, bold=True)
    lbl(d, 345, 262, "Gmail API", 16, DARK, bold=True)
    lbl(d, 345, 286, "Google", 13, GREY)
    lbl(d, 295, 312, "使用 Gmail REST API 讀取、", 12, GREY)
    lbl(d, 295, 330, "撰寫和傳送電子郵件。", 12, GREY)
    btn(d, 295, 360, "選取", BLUE, h=32)
    highlight_ring(d, 280, 245, 320, 160, BLUE, 2)
    callout(d, 620, 310, "② 點擊 Gmail API 卡片")

    # Enable button (next screen)
    box(d, 640, 245, 290, 200, WHITE, (218,220,224), radius=10)
    lbl(d, 660, 262, "Gmail API", 17, DARK, bold=True)
    lbl(d, 660, 288, "Google LLC", 13, GREY)
    d.line((640,310,930,310), fill=(218,220,224))
    lbl(d, 660, 322, "狀態：未啟用", 13, GREY)
    btn(d, 660, 360, "  啟用  ", GREEN, h=38)
    highlight_ring(d, 660, 360, 80, 38, GREEN, 3)
    callout(d, 760, 355, "③ 按「啟用」")

    path = os.path.join(OUT_DIR, "04b_step2_enable_api.png")
    img.save(path, dpi=(144,144)); print(f"Saved: {path}"); return path


# ═══════════════════════════════════════════════════════════════════════════════
# Step 3 – OAuth Consent Screen
# ═══════════════════════════════════════════════════════════════════════════════
def step3():
    H = 600
    img = Image.new("RGB", (W,H), BG)
    d   = ImageDraw.Draw(img)

    step_header(d, 3, "設定 OAuth 同意畫面",
                "API 和服務 → OAuth 同意畫面 → 選「外部」→ 建立")

    google_topbar(d, 80)

    # sidebar
    box(d, 0, 136, 240, H-136, (248,249,250))
    sidebar_item(d, 10, 148, "已啟用的 API",  icon="✅")
    sidebar_item(d, 10, 188, "憑證",          icon="🔑")
    sidebar_item(d, 10, 228, "OAuth 同意畫面",icon="📋", active=True)
    highlight_ring(d, 10, 228, 220, 36, RED, 2)
    callout(d, 12, 272, "① 點此")

    # main area
    box(d, 250, 136, W-260, H-146, WHITE, (218,220,224), radius=8)
    lbl(d, 280, 155, "OAuth 同意畫面", 20, DARK, bold=True)
    lbl(d, 280, 185, "User Type", 15, DGREY, bold=True)

    # radio buttons
    for i,(label_t,desc,active) in enumerate([
        ("內部", "僅限機構內使用者（需要 Google Workspace）", False),
        ("外部", "任何擁有 Google 帳號的使用者均可使用", True),
    ]):
        ry = 215 + i*80
        if active:
            box(d, 280, ry, 580, 66, (232,240,254), BLUE, radius=8, bw=2)
        else:
            box(d, 280, ry, 580, 66, LGREY, (218,220,224), radius=8)
        # radio circle
        cx, cy = 302, ry+33
        draw_r = 12
        d.ellipse((cx-draw_r,cy-draw_r,cx+draw_r,cy+draw_r),
                  outline=BLUE if active else GREY, width=2)
        if active:
            d.ellipse((cx-7,cy-7,cx+7,cy+7), fill=BLUE)
        lbl(d, 322, ry+12, label_t, 16, BLUE if active else DARK, bold=active)
        lbl(d, 322, ry+36, desc,    13, GREY)

    highlight_ring(d, 280, 295, 580, 66, GREEN, 3)
    callout(d, 880, 305, "② 選「外部」")

    btn(d, 280, 400, "    建立    ", GREEN, h=40)
    highlight_ring(d, 280, 400, 100, 40, GREEN, 3)
    callout(d, 400, 396, "③ 按「建立」")

    # form fields hint
    box(d, 280, 458, 580, 110, (255,251,230), WARN_BORDER, radius=8)
    lbl(d, 300, 472, "④ 填寫必填欄位（只需填這兩項）：", 14, (92,45,0), bold=True)
    lbl(d, 300, 498, "應用程式名稱：  Claude Email", 14, DARK)
    lbl(d, 300, 522, "使用者支援電子郵件：  clawtienand7@gmail.com", 14, DARK)
    lbl(d, 300, 546, "其他欄位可留空 → 直接按「儲存並繼續」", 14, GREY)

    path = os.path.join(OUT_DIR, "04c_step3_oauth_consent.png")
    img.save(path, dpi=(144,144)); print(f"Saved: {path}"); return path


# ═══════════════════════════════════════════════════════════════════════════════
# Step 4 – Create OAuth Credentials & Download JSON
# ═══════════════════════════════════════════════════════════════════════════════
def step4():
    H = 640
    img = Image.new("RGB", (W,H), BG)
    d   = ImageDraw.Draw(img)

    step_header(d, 4, "建立 OAuth 憑證並下載 JSON 檔案",
                "憑證 → 建立憑證 → OAuth 用戶端 ID → 電腦版應用程式 → 下載")

    google_topbar(d, 80)

    box(d, 0, 136, 240, H-136, (248,249,250))
    sidebar_item(d, 10, 148, "已啟用的 API", icon="✅")
    sidebar_item(d, 10, 188, "憑證",         icon="🔑", active=True)
    highlight_ring(d, 10, 188, 220, 36, RED, 2)
    callout(d, 12, 232, "① 點「憑證」")

    box(d, 250, 136, W-260, H-146, WHITE, (218,220,224), radius=8)
    lbl(d, 280, 155, "憑證", 20, DARK, bold=True)

    # Create credentials button
    bw = btn(d, 280, 185, "+ 建立憑證 ▾", BLUE, h=38)
    highlight_ring(d, 280, 185, bw, 38, RED, 3)
    callout(d, 280+bw+20, 180, "② 按「建立憑證」")

    # Dropdown menu
    box(d, 280, 226, 220, 120, WHITE, (218,220,224), radius=6)
    items = ["API 金鑰", "OAuth 用戶端 ID", "服務帳戶"]
    for i,item in enumerate(items):
        iy = 236+i*36
        if item == "OAuth 用戶端 ID":
            box(d, 282, iy-2, 216, 32, (232,240,254), BLUE, radius=4, bw=1)
            lbl(d, 294, iy+6, item, 14, BLUE, bold=True)
            highlight_ring(d, 282, iy-2, 216, 32, RED, 2)
            callout(d, 512, iy, "③ 選「OAuth 用戶端 ID」")
        else:
            lbl(d, 294, iy+6, item, 14, DARK)

    # Application type selector
    box(d, 560, 185, 370, 180, WHITE, (218,220,224), radius=8)
    lbl(d, 580, 200, "應用程式類型", 15, DGREY, bold=True)
    box(d, 580, 224, 330, 36, LGREY, (66,133,244), radius=6, bw=2)
    lbl(d, 592, 234, "電腦版應用程式  ▾", 14, DARK)
    highlight_ring(d, 580, 224, 330, 36, RED, 3)
    callout(d, 580, 268, "④ 選「電腦版應用程式」")

    lbl(d, 580, 300, "名稱", 14, DGREY)
    box(d, 580, 320, 330, 34, LGREY, (218,220,224), radius=6)
    lbl(d, 592, 330, "Claude Email Client", 13, DARK)

    btn(d, 700, 364, "建立", GREEN, h=32)
    highlight_ring(d, 700, 364, 56, 32, GREEN, 3)
    callout(d, 772, 360, "⑤ 按「建立」")

    # Download section
    box(d, 250, 395, W-260, 220, (232,245,233), (52,168,83), radius=10, bw=2)
    lbl(d, 280, 412, "✅  OAuth 用戶端已建立！", 18, GREEN, bold=True)
    lbl(d, 280, 442, "⑥  按「下載 JSON」按鈕，儲存憑證檔案", 15, DARK)
    btn(d, 280, 470, "⬇  下載 JSON", GREEN, h=40)
    highlight_ring(d, 280, 470, 150, 40, RED, 3)

    lbl(d, 280, 524, "⑦  將下載的檔案重命名，然後複製到專案目錄：", 15, DARK)
    box(d, 280, 550, 640, 50, (40,44,52), radius=8)
    lbl(d, 296, 560, "mv ~/Downloads/client_secret_xxx.json  \\ ", 14, (224,224,224))
    lbl(d, 296, 578, "   /home/user/C007/gmail_credentials.json", 14, (152,195,121))

    path = os.path.join(OUT_DIR, "04d_step4_download_json.png")
    img.save(path, dpi=(144,144)); print(f"Saved: {path}"); return path


# ═══════════════════════════════════════════════════════════════════════════════
# Step 5 – Run setup & authorize
# ═══════════════════════════════════════════════════════════════════════════════
def step5():
    H = 560
    img = Image.new("RGB", (W,H), BG)
    d   = ImageDraw.Draw(img)

    step_header(d, 5, "執行授權指令，完成設定",
                "終端機執行 setup → 瀏覽器授權 → 貼上授權碼")

    # Terminal window
    box(d, 20, 90, W-40, 160, (30,30,30), (80,80,80), radius=10)
    # traffic lights
    for xi,col in [(38,(255,95,86)), (62,(255,189,46)), (86,(39,201,63))]:
        d.ellipse((xi,98,xi+14,112), fill=col)
    lbl(d, W//2, 99, "終端機 Terminal", 13, (150,150,150), center=True)
    lbl(d, 36, 122, "$ python3 email_gmail_api.py setup", 15, (152,195,121))
    lbl(d, 36, 146, "", 13, (150,150,150))
    lbl(d, 36, 162, "請在瀏覽器打開以下網址：", 14, (224,224,224))
    lbl(d, 36, 184, "https://accounts.google.com/o/oauth2/auth?...", 13, (97,175,239))
    lbl(d, 36, 207, "授權碼: _", 14, (224,224,224))
    highlight_ring(d, 20, 90, W-40, 160, BLUE, 2)
    callout(d, 22, 260, "① 在終端機執行此指令")

    # Google auth page mock
    box(d, 20, 280, 460, 240, WHITE, (218,220,224), radius=10)
    lbl(d, 250, 296, "Google 帳號登入", 18, DARK, bold=True, center=True)
    lbl(d, 250, 324, "Claude Email Client 要求存取", 13, GREY, center=True)
    lbl(d, 250, 344, "你的 Gmail 帳號", 13, GREY, center=True)

    # Scope
    box(d, 40, 364, 420, 36, (232,240,254), BLUE, radius=6)
    lbl(d, 60, 374, "✉️  讀取、撰寫及傳送電子郵件", 13, BLUE)

    btn(d, 40, 412, "允許", GREEN, h=38, w=200)
    highlight_ring(d, 40, 412, 200, 38, GREEN, 3)
    callout(d, 256, 408, "② 按「允許」")

    # Auth code result
    box(d, 500, 280, W-520, 240, WHITE, (218,220,224), radius=10)
    lbl(d, 760, 296, "已獲授權", 18, GREEN, bold=True, center=True)
    d.line((500,320,W-20,320), fill=(218,220,224))
    lbl(d, 516, 334, "請複製以下授權碼", 14, DARK)
    box(d, 516, 360, 440, 50, (255,251,230), WARN_BORDER, radius=8)
    lbl(d, 526, 374, "4/0AX4XfWj3mK8...(一串很長的碼)", 13, DARK)
    highlight_ring(d, 516, 360, 440, 50, RED, 3)
    callout(d, 516, 420, "③ 全選複製此授權碼")

    # back to terminal
    box(d, 500, 440, W-520, 80, (30,30,30), (80,80,80), radius=8)
    lbl(d, 520, 453, "授權碼: ", 14, (224,224,224))
    lbl(d, 608, 453, "4/0AX4XfWj3mK8...  ← 貼上", 13, (152,195,121))
    lbl(d, 520, 478, "✅ 成功連線！已登入：clawtienand7@gmail.com", 13, (39,201,63))
    highlight_ring(d, 500, 440, W-520, 80, GREEN, 2)
    callout(d, 502, 528, "④ 貼上授權碼 → 大功告成！")

    path = os.path.join(OUT_DIR, "04e_step5_authorize.png")
    img.save(path, dpi=(144,144)); print(f"Saved: {path}"); return path


# ═══════════════════════════════════════════════════════════════════════════════
# Summary card
# ═══════════════════════════════════════════════════════════════════════════════
def summary():
    H = 280
    img = Image.new("RGB", (W,H), (40,44,52))
    d   = ImageDraw.Draw(img)

    lbl(d, W//2, 22, "✅  設定完成後可使用的指令", 22, WHITE, bold=True, center=True)

    cmds = [
        ("📤 發送電郵", "python3 email_gmail_api.py send --to XXX --subject YYY --body ZZZ", BLUE),
        ("📬 查看收件",  "python3 email_gmail_api.py list --limit 20",   GREEN),
        ("📖 閱讀郵件",  "python3 email_gmail_api.py read <ID>",         (180,100,220)),
        ("↩️  回覆郵件",  "python3 email_gmail_api.py reply <ID> --body 回覆內容", ORANGE),
    ]
    for i,(label_t,cmd,col) in enumerate(cmds):
        x = 20 + i*(W-40)//4
        w = (W-40)//4 - 8
        box(d, x, 62, w, 190, (50,54,62), col, radius=8, bw=2)
        lbl(d, x+w//2, 76, label_t, 15, WHITE, bold=True, center=True)
        import textwrap
        for li,line in enumerate(textwrap.wrap(cmd, (w-16)//8)):
            lbl(d, x+8, 108+li*20, line, 11, (180,190,200))

    lbl(d, W//2, 260, "如遇問題，重新執行：python3 email_gmail_api.py setup", 13,
        (150,160,170), center=True)

    path = os.path.join(OUT_DIR, "04f_summary.png")
    img.save(path, dpi=(144,144)); print(f"Saved: {path}"); return path


if __name__ == "__main__":
    paths = [step1(), step2(), step3(), step4(), step5(), summary()]
    print(f"\n✅ All {len(paths)} guide images saved to guides/")
