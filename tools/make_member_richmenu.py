"""產生協會的兩張圖文選單圖片（2500 × 843）：
- assets/richmenu_guest.png：訪客選單（潛在會員、審核中、停權）。左：協會標誌（關於協會）；右：申請入會／會員專區
- assets/richmenu_member.png：會員選單（正式會員）。左：協會標誌（關於協會）；右：拍名片、待確認、會員專區

標誌讀 assets/brand/mark.png、協會名稱與顏色讀 assets/brand/brand.json。換 Logo 後重新執行、推上 GitHub，
再到 Make 執行一次「朕宏｜會員：建立圖文選單」。按鈕範圍寫在 tools/make_member_blueprint.py 的 MENUS，兩邊要一致。

執行：python tools/make_member_richmenu.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "assets" / "brand"
W, H = 2500, 843
PANEL = 620   # 左側協會標誌區的寬度（和 make_member_blueprint.py 的 PANEL 一致）
FONT, FONT_REG = r"C:\Windows\Fonts\msjhbd.ttc", r"C:\Windows\Fonts\msjh.ttc"


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def draw_menu(cells, out):
    brand = json.loads((BRAND / "brand.json").read_text(encoding="utf-8"))
    primary, accent = hex_rgb(brand["colors"]["primary"]), hex_rgb(brand["colors"]["accent"])
    img = Image.new("RGB", (W, H), (246, 243, 238))
    d = ImageDraw.Draw(img)
    # 左側：協會標誌＋「關於協會」
    mark = Image.open(BRAND / "mark.png").convert("RGBA")
    mark.thumbnail((400, 400))
    img.paste(mark, ((PANEL - mark.width) // 2, 90), mark)
    d.text((PANEL / 2, 610), brand.get("short", ""), font=ImageFont.truetype(FONT, 64), fill=primary, anchor="mm")
    d.text((PANEL / 2, 700), "關於協會", font=ImageFont.truetype(FONT_REG, 52), fill=(107, 98, 90), anchor="mm")
    # 右側：功能格，深淺兩色交錯
    cw = (W - PANEL) / len(cells)
    for i, (title, sub) in enumerate(cells):
        x0 = PANEL + i * cw
        d.rectangle([x0, 0, x0 + cw, H], fill=primary if i % 2 == 0 else accent)
        cx = x0 + cw / 2
        size = 150 if len(cells) == 1 else 120
        d.text((cx, H / 2 - 50), title, font=ImageFont.truetype(FONT, size), fill="white", anchor="mm")
        d.text((cx, H / 2 + 90), sub, font=ImageFont.truetype(FONT_REG, 54), fill=(250, 244, 236), anchor="mm")
    out.parent.mkdir(exist_ok=True)
    img.save(out, optimize=True)
    print(out, out.stat().st_size)


def main():
    draw_menu([("申請入會", "會員專區・查看審核進度")], ROOT / "assets" / "richmenu_guest.png")
    draw_menu([("拍名片", "名片＋合照"), ("待確認", "確認名片資料"), ("會員專區", "我的會員資料")],
              ROOT / "assets" / "richmenu_member.png")


if __name__ == "__main__":
    main()
