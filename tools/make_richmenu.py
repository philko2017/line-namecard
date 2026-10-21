"""產生名片官方帳號的圖文選單圖片：assets/richmenu.png（2500 × 843，左右兩格）。

左格「拍名片」打開 LIFF 頁面；右格「待確認」打開 ?v=review。按鈕的範圍寫在 make_blueprint.py 的 build_menu()。
換設計時改這裡、重新執行，推上 GitHub 後再到 Make 執行一次情境「朕宏｜名片：建立圖文選單」。

執行：python tools/make_richmenu.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H = 2500, 843
FONT = r"C:\Windows\Fonts\msjhbd.ttc"   # 微軟正黑體粗體
FONT_REG = r"C:\Windows\Fonts\msjh.ttc"

# 顏色和 LIFF 頁面一致（liff/namecard/index.html 的 --green、--blue）
CELLS = [
    {"bg": (43, 122, 61), "title": "拍名片", "sub": "名片＋合照，送出就能拍下一位", "icon": "camera"},
    {"bg": (31, 95, 168), "title": "待確認", "sub": "檢查 AI 辨識結果，確認存入", "icon": "check"},
]


def camera(d, cx, cy, s, color):
    """簡單的相機圖示（用線條畫，不依賴 emoji 字型）"""
    w, h = s * 1.5, s
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=s * 0.18, outline=color, width=int(s * 0.1))
    d.rounded_rectangle([cx - w * 0.2, cy - h / 2 - s * 0.18, cx + w * 0.2, cy - h / 2 + s * 0.02], radius=s * 0.06, fill=color)
    r = s * 0.28
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=int(s * 0.1))


def check(d, cx, cy, s, color):
    """圓圈加勾"""
    r = s * 0.62
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=int(s * 0.1))
    d.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)],
           fill=color, width=int(s * 0.12), joint="curve")


def main():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    cw = W // len(CELLS)
    white = (255, 255, 255)
    for i, cell in enumerate(CELLS):
        x0 = i * cw
        d.rectangle([x0, 0, x0 + cw, H], fill=cell["bg"])
        cx = x0 + cw / 2
        (camera if cell["icon"] == "camera" else check)(d, cx, 250, 200, white)
        title = ImageFont.truetype(FONT, 150)
        d.text((cx, 520), cell["title"], font=title, fill=white, anchor="mm")
        sub = ImageFont.truetype(FONT_REG, 64)
        d.text((cx, 680), cell["sub"], font=sub, fill=(230, 240, 235), anchor="mm")
    d.line([(cw, 60), (cw, H - 60)], fill=(255, 255, 255), width=4)
    out = ROOT / "assets" / "richmenu.png"
    out.parent.mkdir(exist_ok=True)
    img.save(out, optimize=True)
    print(out, out.stat().st_size)


if __name__ == "__main__":
    main()
