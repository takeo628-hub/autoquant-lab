"""Generate the AutoQuant Lab avatar (1024 + 400 px PNG)."""
from PIL import Image, ImageDraw, ImageFont
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "assets")
os.makedirs(OUT, exist_ok=True)

S = 1024
c1, c2 = (67, 56, 202), (14, 165, 233)          # indigo -> sky
mid = tuple((a + b) // 2 for a, b in zip(c1, c2))
base = Image.new("RGB", (2, 2))
base.putpixel((0, 0), c1)
base.putpixel((1, 0), mid)
base.putpixel((0, 1), mid)
base.putpixel((1, 1), c2)
img = base.resize((S, S), Image.BICUBIC)

overlay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(overlay)

# equity-curve motif
pts = [(80, 780), (220, 700), (330, 730), (470, 600), (590, 640),
       (720, 480), (830, 520), (944, 360)]
d.line(pts, fill=(255, 255, 255, 90), width=26, joint="curve")
d.ellipse((944 - 26, 360 - 26, 944 + 26, 360 + 26), fill=(255, 255, 255, 220))

font = None
for f in ["segoeuib.ttf", "arialbd.ttf", "seguisb.ttf"]:
    p = os.path.join("C:/Windows/Fonts", f)
    if os.path.exists(p):
        font = ImageFont.truetype(p, 430)
        break
d.text((S // 2, 430), "AQ", font=font, fill=(255, 255, 255, 255), anchor="mm")

img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
img.save(os.path.join(OUT, "avatar.png"))
img.resize((400, 400), Image.LANCZOS).save(os.path.join(OUT, "avatar_400.png"))
print("saved:", os.path.join(OUT, "avatar.png"))
