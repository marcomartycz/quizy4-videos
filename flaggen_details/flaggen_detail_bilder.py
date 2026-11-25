#!/usr/bin/env python3
"""flaggen_detail_bilder.py – zeichnet die Bilder für Flaggen-Details Teil 1 als quadratische PNGs (512 px, transparent) nach emoji/:
nepal, china, china_frage (Sterne verdeckt), eu, sterne12 (Frage-Bild für 12 Sterne) + Noto-Emojis 1f514 1f447 1f4a1 1f914."""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emoji"); os.makedirs(OUT, exist_ok=True)
S = 4; N = 512 * S
FB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"

def star(cx, cy, r, rot=0.0):
    return [(cx + (r if k % 2 == 0 else r * 0.382) * math.cos(rot - math.pi / 2 + k * math.pi / 5),
             cy + (r if k % 2 == 0 else r * 0.382) * math.sin(rot - math.pi / 2 + k * math.pi / 5)) for k in range(10)]

def finish(im, name, shadow=True):
    if shadow:
        a = im.getchannel("A"); sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.putalpha(a.point(lambda v: v * 0.45))
        sh = sh.filter(ImageFilter.GaussianBlur(10 * S)); base = Image.new("RGBA", im.size, (0, 0, 0, 0))
        base.alpha_composite(sh, (6 * S, 10 * S)); base.alpha_composite(im); im = base
    im.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, name + ".png"))

def rect_flag(w, h):
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0)); x0, y0 = (N - w) // 2, (N - h) // 2
    return im, ImageDraw.Draw(im), x0, y0

def china(hide=False):
    w = int(N * 0.9); h = w * 2 // 3; im, d, x0, y0 = rect_flag(w, h); u = w / 30
    d.rectangle([x0, y0, x0 + w, y0 + h], fill=(238, 28, 37))
    if hide:
        f = ImageFont.truetype(FB, int(h * 0.75))
        d.text((x0 + w / 2, y0 + h / 2), "?", font=f, fill=(255, 222, 0), anchor="mm", stroke_width=int(u * 0.5), stroke_fill=(150, 10, 15))
        return im
    gold = (255, 222, 0); bx, by = x0 + 5 * u, y0 + 5 * u
    d.polygon(star(bx, by, 3 * u), fill=gold)
    for sx, sy in ((10, 2), (12, 4), (12, 7), (10, 9)):
        px, py = x0 + sx * u, y0 + sy * u; ang = math.atan2(by - py, bx - px) + math.pi / 2
        d.polygon(star(px, py, u, ang), fill=gold)
    return im

def eu():
    w = int(N * 0.9); h = w * 2 // 3; im, d, x0, y0 = rect_flag(w, h)
    d.rectangle([x0, y0, x0 + w, y0 + h], fill=(0, 51, 153)); cx, cy = x0 + w / 2, y0 + h / 2
    for k in range(12):
        a = 2 * math.pi * k / 12; d.polygon(star(cx + h / 3 * math.sin(a), cy - h / 3 * math.cos(a), h / 18), fill=(255, 204, 0))
    return im

def sterne12():
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = N / 2
    d.polygon(star(c, c + 40 * S, N * 0.47), fill=(255, 204, 0), outline=(170, 120, 0))
    f = ImageFont.truetype(FB, int(N * 0.30))
    d.text((c, c + 70 * S), "12", font=f, fill=(30, 40, 90), anchor="mm")
    return im

def nepal():
    # Umriss nach dem offiziellen Konstruktionsprinzip (zwei gestapelte Wimpel), Breite 60 : Höhe 80 Einheiten (inkl. Rand)
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    hgt = N * 0.92; u = hgt / 80; x0 = (N - 60 * u) / 2 - 2 * u; y0 = (N - hgt) / 2
    P = lambda x, y: (x0 + x * u, y0 + y * u)
    outer = [P(0, 0), P(60 + 4, 37.574 + 2.4), P(17.574 + 6, 37.574 + 2.4), P(60 + 4, 80), P(0, 80)]
    inner = [P(3, 5.2), P(54, 36.0), P(13.5, 36.0), P(55, 77), P(3, 77)]
    d.polygon(outer, fill=(0, 56, 147)); d.polygon(inner, fill=(220, 20, 60))
    base, im = im, Image.new("RGBA", (N, N), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    white = (255, 255, 255)
    # Mond (oberer Wimpel): Sichel + kleiner Halbkreis mit Strahlen
    mx, my, mr = x0 + 15 * u, y0 + 22 * u, 7.5 * u
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=white)
    d.ellipse([mx - mr * 1.05, my - mr * 1.55, mx + mr * 1.05, my + mr * 0.25], fill=(220, 20, 60))
    sr = mr * 0.42; d.ellipse([mx - sr, my - sr * 0.2, mx + sr, my + sr * 1.8], fill=white)
    for k in range(8):
        a = math.pi + math.pi * k / 7; d.polygon([(mx + sr * 1.1 * math.cos(a - .12), my + sr * .8 + sr * 1.1 * math.sin(a - .12)),
                                                 (mx + sr * 1.9 * math.cos(a), my + sr * .8 + sr * 1.9 * math.sin(a)),
                                                 (mx + sr * 1.1 * math.cos(a + .12), my + sr * .8 + sr * 1.1 * math.sin(a + .12))], fill=white)
    # Sonne (unterer Wimpel): Kreis mit 12 Strahlen
    sx, sy, rr = x0 + 15 * u, y0 + 60 * u, 6 * u
    pts = []
    for k in range(24):
        a = math.pi * k / 12; r_ = rr * (1.6 if k % 2 == 0 else 1.05); pts.append((sx + r_ * math.cos(a), sy + r_ * math.sin(a)))
    d.polygon(pts, fill=white); d.ellipse([sx - rr * 0.95, sy - rr * 0.95, sx + rr * 0.95, sy + rr * 0.95], fill=white)
    m = Image.new("L", (N, N), 0); ImageDraw.Draw(m).polygon(inner, fill=255)
    base.paste(im, (0, 0), Image.fromarray((np.asarray(im.getchannel("A")).astype(np.uint16) * np.asarray(m) // 255).astype(np.uint8)))
    return base

def emoji_png(code):
    f = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0)); ImageDraw.Draw(im).text((16, 10), chr(int(code, 16)), font=f, embedded_color=True)
    im = im.crop(im.getbbox()); s = 480 / max(im.size); im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    c = Image.new("RGBA", (512, 512), (0, 0, 0, 0)); c.alpha_composite(im, ((512 - im.width) // 2, (512 - im.height) // 2)); c.save(os.path.join(OUT, code + ".png"))

if __name__ == "__main__":
    finish(nepal(), "nepal"); finish(china(), "china"); finish(china(True), "china_frage"); finish(eu(), "eu"); finish(sterne12(), "sterne12")
    for c in ("1f514", "1f447", "1f4a1", "1f914"): emoji_png(c)
    print("ok")
