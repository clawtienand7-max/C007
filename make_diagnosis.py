"""
Generates a diagnostic visual explaining why SMTP/IMAP failed
and how Gmail API solves it.
"""
from PIL import Image, ImageDraw
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from make_guide import load_font, OUT_DIR, shadow_rect, warn_box, success_box, arrow, button

W = 960
BG        = (248, 249, 250)
RED       = (234,  67,  53)
GREEN     = ( 52, 168,  83)
BLUE      = ( 66, 133, 244)
ORANGE    = (251, 140,   0)
GREY      = (149, 157, 165)
DARK      = ( 32,  33,  36)
WHITE     = (255, 255, 255)
LIGHT     = (241, 243, 244)
BLOCKED   = (255, 235, 238)
BLOCKED_B = (239,  83,  80)
OPEN_BG   = (232, 245, 233)
OPEN_BD   = ( 76, 175,  80)


def box(draw, x, y, w, h, fill, border=None, radius=10, bw=2):
    if border:
        draw.rounded_rectangle((x,y,x+w,y+h), radius=radius, fill=fill,
                                outline=border, width=bw)
    else:
        draw.rounded_rectangle((x,y,x+w,y+h), radius=radius, fill=fill)


def label(draw, x, y, text, size=16, color=DARK, bold=False, align="left"):
    f = load_font(size, bold=bold)
    bb = draw.textbbox((0,0), text, font=f)
    tw = bb[2]-bb[0]
    if align == "center":
        x = x - tw//2
    draw.text((x, y), text, font=f, fill=color)
    return bb[3]-bb[1]


def make_diagnosis():
    H = 900
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── Title ─────────────────────────────────────────────────────────────────
    draw.rectangle((0,0,W,70), fill=DARK)
    label(draw, W//2, 18, "為何電郵連線失敗？完整原因解析", 26, WHITE, bold=True, align="center")
    label(draw, W//2, 50, "App Password 正確無誤  ·  問題出在雲端環境網絡", 16,
          (180,200,220), align="center")

    # ══ Section 1: Network diagram ═══════════════════════════════════════════
    sy = 90
    label(draw, 30, sy, "① 網絡封鎖示意圖", 20, DARK, bold=True)

    # Claude cloud box
    box(draw, 30, sy+35, 200, 80, (224,231,255), BLUE, radius=12)
    label(draw, 130, sy+55, "Claude Code", 16, BLUE, bold=True, align="center")
    label(draw, 130, sy+78, "雲端沙箱環境", 13, GREY, align="center")

    # Firewall
    box(draw, 310, sy+35, 120, 80, BLOCKED, BLOCKED_B, radius=8)
    label(draw, 370, sy+52, "🔥 防火牆", 16, RED, bold=True, align="center")
    label(draw, 370, sy+75, "Firewall", 13, RED, align="center")

    # Gmail SMTP/IMAP
    box(draw, 510, sy+10, 180, 55, BLOCKED, BLOCKED_B, radius=8)
    label(draw, 600, sy+28, "Gmail SMTP", 15, RED, bold=True, align="center")
    label(draw, 600, sy+48, "Port 587  ❌ 封鎖", 13, RED, align="center")

    box(draw, 510, sy+75, 180, 55, BLOCKED, BLOCKED_B, radius=8)
    label(draw, 600, sy+93, "Gmail IMAP", 15, RED, bold=True, align="center")
    label(draw, 600, sy+113, "Port 993  ❌ 封鎖", 13, RED, align="center")

    # Gmail API (HTTPS)
    box(draw, 510, sy+145, 180, 55, OPEN_BG, OPEN_BD, radius=8)
    label(draw, 600, sy+163, "Gmail API", 15, GREEN, bold=True, align="center")
    label(draw, 600, sy+183, "Port 443  ✅ 開通", 13, GREEN, align="center")

    # Arrows SMTP/IMAP (blocked - red X)
    arrow(draw, 232, sy+75, 308, sy+75, RED, 3)
    arrow(draw, 432, sy+38, 508, sy+38, RED, 3)
    arrow(draw, 432, sy+112, 508, sy+112, RED, 3)
    # X mark on firewall
    fx, fy = 370, sy+63
    draw.line((fx-12,fy-12,fx+12,fy+12), fill=RED, width=4)
    draw.line((fx+12,fy-12,fx-12,fy+12), fill=RED, width=4)

    # Arrow API (open - green)
    arrow(draw, 232, sy+75, 308, sy+172, GREEN, 3)
    arrow(draw, 432, sy+172, 508, sy+172, GREEN, 3)

    # Legend
    lx = 720
    box(draw, lx, sy+35, 210, 170, WHITE, GREY, radius=10, bw=1)
    label(draw, lx+15, sy+50, "圖例", 15, DARK, bold=True)
    draw.line((lx+15, sy+80, lx+45, sy+80), fill=RED, width=3)
    label(draw, lx+55, sy+72, "封鎖的連接 ❌", 13, RED)
    draw.line((lx+15, sy+110, lx+45, sy+110), fill=GREEN, width=3)
    label(draw, lx+55, sy+102, "開通的連接 ✅", 13, GREEN)
    box(draw, lx+15, sy+130, 30, 20, BLOCKED, BLOCKED_B, radius=4)
    label(draw, lx+55, sy+130, "被封鎖端口", 13, RED)
    box(draw, lx+15, sy+160, 30, 20, OPEN_BG, OPEN_BD, radius=4)
    label(draw, lx+55, sy+160, "開通端口", 13, GREEN)

    # ══ Section 2: Explanation ═══════════════════════════════════════════════
    ey = sy + 245
    label(draw, 30, ey, "② 失敗原因解析", 20, DARK, bold=True)

    reasons = [
        (RED,   "❌",  "Port 587 (SMTP) 被封鎖",
                "雲端沙箱為安全理由，封鎖了所有對外 SMTP 連接（發送電郵用）"),
        (RED,   "❌",  "Port 993 (IMAP) 被封鎖",
                "雲端沙箱同樣封鎖了 IMAP 連接（接收電郵用）"),
        (ORANGE,"⚠️",  "App Password 本身正確",
                "pxsv dmmn womy agiw 格式正確，問題不是密碼錯誤"),
        (GREEN, "✅",  "Port 443 (HTTPS) 開通",
                "Gmail API 走 HTTPS，不受封鎖，可以正常使用"),
    ]

    ry = ey + 35
    for col, icon, title, desc in reasons:
        box(draw, 30, ry, W-60, 62, WHITE, col, radius=10, bw=2)
        label(draw, 60, ry+8, icon, 22, col)
        label(draw, 100, ry+8, title, 17, col, bold=True)
        label(draw, 100, ry+34, desc, 14, GREY)
        ry += 72

    # ══ Section 3: Solution ══════════════════════════════════════════════════
    sy2 = ry + 20
    label(draw, 30, sy2, "③ 解決方案：改用 Gmail API（已建立完成）", 20, DARK, bold=True)

    steps = [
        ("取得 OAuth 憑證",  "google.cloud.google.com → 建立專案 → 啟用 Gmail API → 下載 JSON"),
        ("放入憑證檔案",      "將下載的 JSON 重命名為 gmail_credentials.json 放入專案目錄"),
        ("首次授權",          "python3 email_gmail_api.py setup → 打開網址 → 貼上授權碼"),
        ("正常使用",          "python3 email_gmail_api.py send / list / read / reply ..."),
    ]

    for si, (stitle, sdesc) in enumerate(steps):
        sx = 30 + si*(W-60)//4
        sw = (W-60)//4 - 10
        box(draw, sx, sy2+35, sw, 100, WHITE, BLUE, radius=10, bw=2)
        # circle
        cx = sx + sw//2
        draw.ellipse((cx-20, sy2+45, cx+20, sy2+85), fill=BLUE)
        label(draw, cx, sy2+55, str(si+1), 22, WHITE, bold=True, align="center")
        label(draw, cx, sy2+92, stitle, 13, DARK, bold=True, align="center")

        # desc below card
        import textwrap as tw
        lines = tw.wrap(sdesc, width=sw//8+2)
        for li, line in enumerate(lines[:3]):
            label(draw, sx+5, sy2+140+li*18, line, 12, GREY)

    path = os.path.join(OUT_DIR, "03_diagnosis.png")
    img.save(path, dpi=(144,144))
    print(f"Saved: {path}")
    return path


if __name__ == "__main__":
    make_diagnosis()
