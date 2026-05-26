"""
Visual step-by-step guide generator.
Creates annotated PNG instruction cards.
"""

from PIL import Image, ImageDraw, ImageFont
import os, textwrap

OUT_DIR = os.path.join(os.path.dirname(__file__), "guides")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Colour palette ────────────────────────────────────────────────────────────
BG          = (248, 249, 250)
CARD_BG     = (255, 255, 255)
CARD_SHADOW = (220, 223, 228)
STEP_CIRCLE = (66, 133, 244)       # Google Blue
STEP_TEXT   = (255, 255, 255)
TITLE_COL   = (32,  33,  36)
BODY_COL    = (95,  99, 104)
HIGHLIGHT   = (255, 204,   0)      # Yellow highlight box
HIGHLIGHT_T = (60,  60,   0)
ARROW_COL   = (234,  67,  53)      # Red arrow
BTN_GREEN   = (52, 168,  83)
BTN_BLUE    = (66, 133, 244)
BTN_RED     = (234,  67,  53)
BTN_TEXT    = (255, 255, 255)
URL_COL     = (26, 115, 232)
WARN_BG     = (254, 243, 199)
WARN_BORDER = (245, 158,  11)
WARN_TEXT   = (92,  45,   0)
SUCCESS_BG  = (220, 252, 231)
SUCCESS_BD  = (34, 197,  94)
SUCCESS_T   = (21, 128,  61)

W = 900   # card width


def load_font(size: int, bold=False):
    """Try to load a CJK-capable font, fall back to default."""
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def shadow_rect(draw, xy, fill, radius=12, shadow_offset=4):
    x0, y0, x1, y1 = xy
    # shadow
    draw.rounded_rectangle(
        (x0+shadow_offset, y0+shadow_offset, x1+shadow_offset, y1+shadow_offset),
        radius=radius, fill=CARD_SHADOW)
    # card
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def step_circle(draw, cx, cy, number, r=28):
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=STEP_CIRCLE)
    f = load_font(26, bold=True)
    txt = str(number)
    bb = draw.textbbox((0,0), txt, font=f)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    draw.text((cx - tw//2, cy - th//2 - 2), txt, font=f, fill=STEP_TEXT)


def button(draw, x, y, label, color=BTN_BLUE, w=None, h=40):
    f = load_font(18, bold=True)
    bb = draw.textbbox((0,0), label, font=f)
    tw = bb[2]-bb[0]
    bw = w or tw + 40
    draw.rounded_rectangle((x, y, x+bw, y+h), radius=8, fill=color)
    draw.text((x + (bw-tw)//2, y + (h - (bb[3]-bb[1]))//2 - 1),
              label, font=f, fill=BTN_TEXT)
    return bw


def url_bar(draw, x, y, url, bar_w=700, h=38):
    draw.rounded_rectangle((x, y, x+bar_w, y+h), radius=6,
                            fill=(241,243,244), outline=(218,220,224))
    # lock icon placeholder
    draw.ellipse((x+10, y+10, x+22, y+28), outline=(52,168,83), width=2)
    draw.rectangle((x+13, y+18, x+19, y+28), fill=(52,168,83))
    f = load_font(16)
    draw.text((x+32, y+10), url, font=f, fill=URL_COL)


def highlight_box(draw, xy, label=""):
    x0,y0,x1,y1 = xy
    # yellow fill
    draw.rounded_rectangle(xy, radius=6, fill=HIGHLIGHT, outline=WARN_BORDER, width=2)
    if label:
        f = load_font(15, bold=True)
        draw.text((x0+8, y0+5), label, font=f, fill=HIGHLIGHT_T)


def arrow(draw, x0, y0, x1, y1, color=ARROW_COL, width=4):
    draw.line((x0,y0,x1,y1), fill=color, width=width)
    # arrowhead
    import math
    angle = math.atan2(y1-y0, x1-x0)
    size = 16
    for da in (0.5, -0.5):
        ax = x1 - size * math.cos(angle-da)
        ay = y1 - size * math.sin(angle-da)
        draw.line((x1,y1,int(ax),int(ay)), fill=color, width=width)


def warn_box(draw, x, y, w, text, icon="⚠️ "):
    f = load_font(17)
    lines = textwrap.wrap(text, width=(w-40)//10)
    h = len(lines)*26 + 20
    draw.rounded_rectangle((x,y,x+w,y+h), radius=8,
                            fill=WARN_BG, outline=WARN_BORDER, width=2)
    for i, line in enumerate(lines):
        prefix = icon if i == 0 else "    "
        draw.text((x+14, y+10+i*26), prefix+line, font=f, fill=WARN_TEXT)
    return h


def success_box(draw, x, y, w, text):
    f = load_font(17)
    lines = textwrap.wrap(text, width=(w-40)//10)
    h = len(lines)*26 + 20
    draw.rounded_rectangle((x,y,x+w,y+h), radius=8,
                            fill=SUCCESS_BG, outline=SUCCESS_BD, width=2)
    for i, line in enumerate(lines):
        prefix = "✅ " if i == 0 else "    "
        draw.text((x+14, y+10+i*26), prefix+line, font=f, fill=SUCCESS_T)
    return h


# ══════════════════════════════════════════════════════════════════════════════
# GUIDE 1 — Gmail App Password (7 steps)
# ══════════════════════════════════════════════════════════════════════════════
def make_gmail_apppassword_guide():
    steps = [
        {
            "title": "打開 Gmail App Password 頁面",
            "desc":  "在瀏覽器輸入以下網址，然後按 Enter",
            "url":   "myaccount.google.com/apppasswords",
            "note":  "",
        },
        {
            "title": "登入你的 Google 帳號",
            "desc":  "輸入你的 Gmail 地址，然後輸入密碼",
            "highlight_label": "輸入：clawtienand7@gmail.com",
            "note":  "",
        },
        {
            "title": "如未見到選項 → 先開啟兩步驟驗證",
            "desc":  '如果頁面顯示「此設定不適用於你的帳號」，\n需要先開啟「兩步驟驗證」',
            "url":   "myaccount.google.com/security",
            "btn":   ("兩步驟驗證", BTN_BLUE),
            "note":  "warn:開啟後才能使用 App Password 功能",
        },
        {
            "title": '在「應用程式密碼」頁面選擇應用程式',
            "desc":  '下拉選單選擇「其他（自訂名稱）」\n然後輸入名稱，例如「Claude Email」',
            "btn":   ("其他（自訂名稱）▼", BTN_BLUE),
            "note":  "",
        },
        {
            "title": '按「產生」按鈕',
            "desc":  "輸入名稱後，按右下角的「產生」按鈕",
            "btn":   ("產生", BTN_GREEN),
            "note":  "",
        },
        {
            "title": "複製 16 字元的 App Password",
            "desc":  "畫面會出現一組黃色方塊內的密碼，共 16 個字元\n選取全部並複製（Ctrl+C / Cmd+C）",
            "apppassword": True,
            "note":  "success:這個密碼只顯示一次！請立即複製並儲存",
        },
        {
            "title": "將 App Password 填入設定檔",
            "desc":  "在終端機執行以下指令，將 xxxx xxxx xxxx xxxx 替換為你的密碼",
            "code":  'python3 email_tool.py setup\n# Email:    clawtienand7@gmail.com\n# Password: xxxx xxxx xxxx xxxx  ← 貼上App Password\n# Provider: gmail',
            "note":  "",
        },
    ]

    card_h = 260
    pad    = 30
    title_h = 80
    total_h = title_h + len(steps) * (card_h + 20) + pad * 2

    img  = Image.new("RGB", (W, total_h), BG)
    draw = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle((0, 0, W, title_h), fill=STEP_CIRCLE)
    f_big  = load_font(30, bold=True)
    f_sub  = load_font(18)
    draw.text((pad, 14), "Gmail App Password 設定指引", font=f_big, fill="white")
    draw.text((pad, 52), "共 7 個步驟  ·  完成後即可使用 Email Skill 發送電郵", font=f_sub, fill=(200,220,255))

    y = title_h + pad

    for i, step in enumerate(steps):
        # card shadow + bg
        shadow_rect(draw, (pad, y, W-pad, y+card_h), CARD_BG, radius=14, shadow_offset=5)

        # Step circle
        step_circle(draw, pad+44, y+44, i+1)

        # Title
        f_title = load_font(22, bold=True)
        draw.text((pad+88, y+20), step["title"], font=f_title, fill=TITLE_COL)

        # Desc
        f_body = load_font(17)
        desc_lines = step["desc"].split("\n")
        for li, line in enumerate(desc_lines):
            draw.text((pad+88, y+56+li*26), line, font=f_body, fill=BODY_COL)

        inner_y = y + 56 + len(desc_lines)*26 + 10

        # URL bar
        if step.get("url"):
            url_bar(draw, pad+88, inner_y, step["url"], bar_w=W-pad-88-pad-20)
            inner_y += 50

        # Highlight box
        if step.get("highlight_label"):
            highlight_box(draw,
                          (pad+88, inner_y, W-pad-pad-20, inner_y+36),
                          step["highlight_label"])
            inner_y += 46

        # Button mock
        if step.get("btn"):
            lbl, col = step["btn"]
            button(draw, pad+88, inner_y, lbl, color=col, h=36)
            inner_y += 46

        # App password mock
        if step.get("apppassword"):
            pw_x, pw_y = pad+88, inner_y
            draw.rounded_rectangle((pw_x, pw_y, pw_x+420, pw_y+50),
                                    radius=8, fill=HIGHLIGHT, outline=WARN_BORDER, width=2)
            f_pw = load_font(24, bold=True)
            draw.text((pw_x+20, pw_y+12), "a b c d  e f g h  i j k l  m n o p", font=f_pw, fill=(80,50,0))
            arrow(draw, pw_x+440, pw_y+25, pw_x+480, pw_y+25)
            f_copy = load_font(15)
            draw.text((pw_x+488, pw_y+12), "全選\n複製", font=f_copy, fill=ARROW_COL)
            inner_y += 60

        # Code block
        if step.get("code"):
            code_x, code_y = pad+88, inner_y
            code_lines = step["code"].split("\n")
            code_h = len(code_lines)*22 + 16
            draw.rounded_rectangle((code_x, code_y, W-pad-pad-10, code_y+code_h),
                                    radius=6, fill=(40,44,52))
            f_code = load_font(14)
            for ci, cl in enumerate(code_lines):
                col_ = (152,195,121) if cl.startswith("#") else (224,224,224)
                draw.text((code_x+12, code_y+8+ci*22), cl, font=f_code, fill=col_)
            inner_y += code_h + 10

        # Note / warn / success
        note = step.get("note", "")
        if note.startswith("warn:"):
            warn_box(draw, pad+88, inner_y, W-pad-88-pad-20, note[5:])
        elif note.startswith("success:"):
            success_box(draw, pad+88, inner_y, W-pad-88-pad-20, note[8:])

        y += card_h + 20

    path = os.path.join(OUT_DIR, "01_gmail_app_password.png")
    img.save(path, dpi=(144,144))
    print(f"Saved: {path}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
# GUIDE 2 — Email Skill 使用指引
# ══════════════════════════════════════════════════════════════════════════════
def make_email_skill_usage_guide():
    commands = [
        ("📤 發送電郵",        "python3 email_tool.py send\n  --to   recipient@example.com\n  --subject \"主題\"\n  --body  \"內文\"",  BTN_BLUE),
        ("📬 查看收件箱",      "python3 email_tool.py list --limit 20",                               BTN_GREEN),
        ("📖 閱讀指定電郵",    "python3 email_tool.py read <ID>\n# ID 從 list 指令的第一欄取得",     (100,60,200)),
        ("↩️  回覆電郵",        "python3 email_tool.py reply <ID>\n  --body \"回覆內容\"",             (200,100,20)),
        ("🔍 搜尋電郵",        "python3 email_tool.py search\n  --from-addr boss@company.com\n  --subject \"Invoice\"\n  --unread",  (20,150,150)),
        ("🗑️  刪除電郵",        "python3 email_tool.py delete <ID>",                                  BTN_RED),
        ("📁 查看所有資料夾",  "python3 email_tool.py folders",                                       (80,80,80)),
    ]

    card_h = 160
    pad    = 30
    title_h = 80
    total_h = title_h + len(commands)*(card_h+16) + pad*2

    img  = Image.new("RGB", (W, total_h), BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle((0,0,W,title_h), fill=(52,168,83))
    draw.text((pad, 14), "Email Skill 指令速查卡", font=load_font(30,bold=True), fill="white")
    draw.text((pad, 52), "設定完成後，在終端機輸入以下指令操作電郵", font=load_font(18), fill=(200,240,210))

    y = title_h + pad
    for (label, code, col) in commands:
        shadow_rect(draw, (pad,y,W-pad,y+card_h), CARD_BG, radius=12, shadow_offset=4)

        # colour sidebar
        draw.rounded_rectangle((pad,y,pad+8,y+card_h), radius=4, fill=col)

        f_lbl  = load_font(20, bold=True)
        f_code = load_font(15)
        draw.text((pad+24, y+14), label, font=f_lbl, fill=TITLE_COL)

        code_lines = code.split("\n")
        code_h = len(code_lines)*22 + 16
        cx, cy = pad+24, y+48
        draw.rounded_rectangle((cx, cy, W-pad-24, cy+code_h), radius=6, fill=(40,44,52))
        for ci, cl in enumerate(code_lines):
            c_ = (152,195,121) if cl.strip().startswith("#") else \
                 (97,175,239)  if cl.strip().startswith("--") else (224,224,224)
            draw.text((cx+12, cy+8+ci*22), cl, font=f_code, fill=c_)

        y += card_h + 16

    path = os.path.join(OUT_DIR, "02_email_skill_commands.png")
    img.save(path, dpi=(144,144))
    print(f"Saved: {path}")
    return path


if __name__ == "__main__":
    p1 = make_gmail_apppassword_guide()
    p2 = make_email_skill_usage_guide()
    print(f"\n✅ Guides saved to: guides/")
