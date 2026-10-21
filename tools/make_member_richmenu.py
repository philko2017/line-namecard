"""產生協會的兩張圖文選單圖片（2500 × 1686，上下兩列）：

- assets/richmenu_member.png：會員選單（正式會員）
    上列：近期活動｜協會會員列表｜啟動 AI 小幫手
    下列：名片掃描｜（空）｜（空）
- assets/richmenu_guest.png：訪客選單（潛在會員、審核中、停權）
    上列：和會員選單相同
    下列：一整格「申請加入」

標誌讀 assets/brand/mark.png、協會名稱與顏色讀 assets/brand/brand.json。換 Logo 後重新執行、推上 GitHub，
再到 Make 執行一次「朕宏｜會員：建立圖文選單（手動執行）」。按鈕範圍寫在 tools/make_member_blueprint.py，兩邊的格子要一致。

執行：python tools/make_member_richmenu.py
"""
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "assets" / "brand"
W, H, ROW = 2500, 1686, 843
COLS = [0, 833, 1667, 2500]   # 三欄的邊界，和 make_member_blueprint.py 的 COLS 一致
FONT, FONT_REG = r"C:\Windows\Fonts\msjhbd.ttc", r"C:\Windows\Fonts\msjh.ttc"
# 上列三格：標題、說明、圖示（兩張選單共用）
TOP = [("近期活動", "課程・參訪・聚會", "calendar"), ("協會會員列表", "認識其他會員", "people"),
       ("AI 小幫手", "點我啟動・有問題就問", "sparkle")]


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


# ---- 圖示：用線條畫，不依賴 emoji 字型 ----
def calendar(d, cx, cy, s, col):
    w, h, lw = s * 1.3, s * 1.15, int(s * 0.09)
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=s * 0.14, outline=col, width=lw)
    d.line([(cx - w / 2, cy - h / 2 + s * 0.3), (cx + w / 2, cy - h / 2 + s * 0.3)], fill=col, width=lw)
    for dx in (-0.3, 0.3):
        d.line([(cx + dx * s, cy - h / 2 - s * 0.14), (cx + dx * s, cy - h / 2 + s * 0.1)], fill=col, width=lw)
    r = s * 0.06
    for row in (0.12, 0.36):
        for col_ in (-0.38, 0, 0.38):
            x, y = cx + col_ * s, cy + row * s - s * 0.08
            d.ellipse([x - r, y - r, x + r, y + r], fill=col)


def people(d, cx, cy, s, col):
    lw = int(s * 0.09)
    for dx, k in ((-0.32, 0.8), (0.32, 0.8), (0, 1.0)):
        x, hr = cx + dx * s, s * 0.2 * k
        hy = cy - s * 0.25 * k
        d.ellipse([x - hr, hy - hr, x + hr, hy + hr], outline=col, width=lw)
        bw = s * 0.42 * k
        d.arc([x - bw, cy + s * 0.05, x + bw, cy + s * 0.05 + bw * 1.6], 180, 360, fill=col, width=lw)


def sparkle(d, cx, cy, s, col):
    def star(x, y, r):
        k = r * 0.22
        d.polygon([(x, y - r), (x + k, y - k), (x + r, y), (x + k, y + k), (x, y + r), (x - k, y + k), (x - r, y), (x - k, y - k)], fill=col)
    star(cx - s * 0.1, cy + s * 0.05, s * 0.55)
    star(cx + s * 0.45, cy - s * 0.4, s * 0.24)
    star(cx + s * 0.42, cy + s * 0.48, s * 0.14)


def camera(d, cx, cy, s, col):
    w, h, lw = s * 1.5, s, int(s * 0.1)
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=s * 0.18, outline=col, width=lw)
    d.rounded_rectangle([cx - w * 0.2, cy - h / 2 - s * 0.18, cx + w * 0.2, cy - h / 2 + s * 0.02], radius=s * 0.06, fill=col)
    r = s * 0.28
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=lw)


ICONS = {"calendar": calendar, "people": people, "sparkle": sparkle, "camera": camera}


def mark_shape(mark, size):
    """標誌的形狀（只取有顏色的部分）。標誌圖的圓環中間可能是白色而不是透明，白色也當成透明。"""
    m = mark.copy()
    m.thumbnail((size, size))
    # 深色帶子（棕）全不透明、淺色帶子（金）半透明，換成單色後還看得出兩條帶子交錯
    colored = m.convert("L").point(lambda v: 255 if v < 130 else 140 if v < 215 else 0)
    return m, ImageChops.multiply(m.split()[3], colored)


def tinted_mark(mark, size, color, opacity=1.0):
    """把標誌改成單一顏色（例如棕底上的白色剪影、空格裡的淡色標誌）"""
    m, alpha = mark_shape(mark, size)
    out = Image.new("RGBA", m.size, color + (0,))
    out.putalpha(alpha.point(lambda v: int(v * opacity)))
    return out


def cell(d, box, title, sub, icon, bg, fg, subfg):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=bg)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ICONS[icon](d, cx, cy - 170, 150, fg)
    d.text((cx, cy + 90), title, font=ImageFont.truetype(FONT, 104), fill=fg, anchor="mm")
    d.text((cx, cy + 215), sub, font=ImageFont.truetype(FONT_REG, 56), fill=subfg, anchor="mm")


def draw_menu(bottom, out):
    brand = json.loads((BRAND / "brand.json").read_text(encoding="utf-8"))
    primary, accent = hex_rgb(brand["colors"]["primary"]), hex_rgb(brand["colors"]["accent"])
    cream, line = (246, 243, 238), (226, 216, 202)
    img = Image.new("RGB", (W, H), cream)
    d = ImageDraw.Draw(img)
    # 上列：米色底、棕色圖示與字
    for i, (title, sub, icon) in enumerate(TOP):
        cell(d, (COLS[i], 0, COLS[i + 1], ROW), title, sub, icon, cream, primary, (120, 104, 88))
    for x in COLS[1:-1]:
        d.line([(x, 70), (x, ROW - 70)], fill=line, width=4)
    d.line([(0, ROW), (W, ROW)], fill=line, width=4)
    mark = Image.open(BRAND / "mark.png").convert("RGBA")
    bottom(img, d, primary, accent, mark, brand)
    out.parent.mkdir(exist_ok=True)
    img.save(out, optimize=True)
    print(out, out.stat().st_size)


def member_bottom(img, d, primary, accent, mark, brand):
    """下列：名片掃描＋兩格空位（之後放新功能）。空位只放淡淡的協會標誌，LINE 上也不設按鈕。"""
    cell(d, (COLS[0], ROW, COLS[1], H), "名片掃描", "名片＋合照，AI 辨識", "camera", primary, (255, 255, 255), (246, 236, 224))
    for i in (1, 2):
        x0, x1 = COLS[i], COLS[i + 1]
        bg = mix(accent, (255, 255, 255), 0.55)
        d.rectangle([x0, ROW, x1, H], fill=bg)
        faded = tinted_mark(mark, 300, (255, 255, 255), 0.6)
        img.paste(faded, (int((x0 + x1 - faded.width) / 2), ROW + (ROW - faded.height) // 2), faded)
    d.line([(COLS[1], ROW), (COLS[1], H)], fill=(255, 255, 255), width=4)
    d.line([(COLS[2], ROW + 70), (COLS[2], H - 70)], fill=(255, 255, 255), width=4)


def guest_bottom(img, d, primary, accent, mark, brand):
    """下列：一整格「申請加入」，左側放協會標誌。"""
    d.rectangle([0, ROW, W, H], fill=primary)
    # 標誌原本是棕色，放在棕底上看不到，改成白色剪影
    white = tinted_mark(mark, 520, (255, 255, 255))
    img.paste(white, (300, ROW + (ROW - white.height) // 2), white)
    tx = 1500
    d.text((tx, ROW + 330), "申請加入", font=ImageFont.truetype(FONT, 190), fill="white", anchor="mm")
    d.text((tx, ROW + 540), f"加入{brand.get('name', '')}", font=ImageFont.truetype(FONT_REG, 66), fill=(246, 236, 224), anchor="mm")
    d.text((tx, ROW + 630), "填寫資料，審核通過後開通會員功能", font=ImageFont.truetype(FONT_REG, 56), fill=(236, 220, 200), anchor="mm")


def main():
    draw_menu(member_bottom, ROOT / "assets" / "richmenu_member.png")
    draw_menu(guest_bottom, ROOT / "assets" / "richmenu_guest.png")


if __name__ == "__main__":
    main()
