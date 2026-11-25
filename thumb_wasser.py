#!/usr/bin/env python3
"""thumb_wasser.py – Thumbnail „Warum schwimmt Eis?!“ (9:16 für Shorts + 16:9), nutzt Zeichenfunktionen aus wasser.py."""
import math, numpy as np, cv2
from PIL import Image
import wasser as w

W, H = 1080, 1920

def rays(width, height, cx, cy, c1=(40, 125, 225), c2=(10, 40, 105), n=22):
    yy, xx = np.mgrid[0:height, 0:width]; ang = np.arctan2(yy - cy, xx - cx)
    m = ((ang + math.pi) / (2 * math.pi) * n).astype(int) % 2
    img = np.where(m[..., None] == 0, np.array(c1, np.float32), np.array(c2, np.float32))
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / max(width, height)
    img = img * (1 - 0.55 * np.clip(r, 0, 1)[..., None] ** 1.2)
    glow = np.exp(-(r / 0.28) ** 2)[..., None] * np.array((120, 200, 255), np.float32) * 0.55
    return np.clip(img + glow, 0, 255).astype(np.uint8)

def sticker(text, size, bg, fg=(255, 255, 255), ang=-6):
    from PIL import ImageDraw
    t = w.txt(text, size, fg); h_, w_ = t.shape[:2]
    im = Image.new("RGBA", (w_ + 70, h_ + 36), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w_ + 69, h_ + 35], 34, fill=bg + (255,), outline=(255, 255, 255, 255), width=9)
    im.alpha_composite(Image.fromarray(t), (35, 18))
    sh = Image.new("RGBA", (im.width + 30, im.height + 30), (0, 0, 0, 0)); sh.alpha_composite(im, (0, 0))
    return np.asarray(im.rotate(ang, expand=True, resample=Image.BICUBIC))

def hoch():
    fr = rays(W, H, 540, 910)
    w.poly(fr, w.circle_pts(552, 926, 430, 120), (0, 0, 0), 0.35)
    w.poly(fr, w.circle_pts(540, 910, 430, 120), (6, 22, 52), 0.96)
    w.lines(fr, w.circle_pts(540, 910, 430, 120), (150, 225, 255), 14, 1.0, True)
    w.glass_scene(fr, 0.6); roh = fr.copy()
    S = (8, 20, 50)
    w.over(fr, w.txt("WARUM", 150, (255, 255, 255), 13, S), W / 2, 150)
    w.over(fr, w.txt("SCHWIMMT", 158, (255, 255, 255), 13, S), W / 2, 305)
    w.over(fr, w.txt("EIS?!", 300, w.YEL, 20, S), W / 2, 1455)
    w.over(fr, w.emoji("🤯", 230), 880, 610)
    w.over(fr, w.emoji("🧊", 150), 170, 760)
    w.over(fr, sticker("WASSER IST EIN REBELL!", 64, w.RED), W / 2, 1720)
    Image.fromarray(fr).save("Wasser-Erklaer-Eis_Thumbnail_Shorts.jpg", quality=93)
    return roh

def quer(fr_hoch):
    TW, TH = 1280, 720
    bg = rays(TW, TH, 960, 380)
    crop = fr_hoch[910 - 445:910 + 445, 540 - 445:540 + 445].copy()   # Scheibe mit Glas
    s = 620 / crop.shape[0]; crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    h, wd = crop.shape[:2]; yy, xx = np.mgrid[0:h, 0:wd]
    rr = np.sqrt((xx - wd / 2) ** 2 + (yy - h / 2) ** 2); R = 437 * s
    m = np.clip(R - rr, 0, 1.5)[..., None] / 1.5
    x0, y0 = 945 - wd // 2, 50
    roi = bg[y0:y0 + h, x0:x0 + wd]; roi[:] = (roi * (1 - m) + crop * m).astype(np.uint8)
    S = (8, 20, 50)
    w.W, w.H = TW, TH                                           # over() mit Querformat-Grenzen
    w.over(bg, w.txt("WARUM", 104, (255, 255, 255), 10, S), 60, 120, anchor="l")
    w.over(bg, w.txt("SCHWIMMT", 112, (255, 255, 255), 10, S), 60, 245, anchor="l")
    w.over(bg, w.txt("EIS?!", 190, w.YEL, 15, S), 60, 420, anchor="l")
    w.over(bg, sticker("WASSER IST EIN REBELL!", 42, w.RED, ang=-4), 375, 625)
    w.over(bg, w.emoji("🤯", 150), 1185, 105)
    w.W, w.H = W, H
    Image.fromarray(bg).save("Wasser-Erklaer-Eis_Thumbnail_16x9.jpg", quality=93)

if __name__ == "__main__":
    quer(hoch())
