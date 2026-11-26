#!/usr/bin/env python3
"""
falsch_flagge_quiz.py – Quizy4 "Finde die falsch platzierte Flagge!" Short (1080x1920, 30 fps).
Je Runde: Europakarte (Ausschnitt) mit 3 Flaggen-Pins (A/B/C), Frage + Antworten sofort sichtbar, Stimme liest Frage,
Countdown 5-4-3-2-1 (Ticken), Auflösung: falsche Flagge rot markiert, Gastland rot, richtige Pins grün umkreist,
Antwort grün + Hand hakt ab, Punktestand 1/3..3/3, falsche Flagge fliegt in ihr Heimatland (grün).
Runde 3 = "DIE SCHWERSTE!". Outro: Kommentar- + Abo-Aufruf, Abo-Button mit Bing, Wisch zurück zu Runde 1 (Loop).
Aufruf: python3 falsch_flagge_quiz.py quiz.json out.mp4 --stimme el_ordner [--tempo 1.1 --tempo-aufl 1.15 --denkzeit 5 --still]
Stimme: q0..q2.mp3, r0..r2.mp3, outro.mp3. Karte: countries.geojson (npm world-atlas@2 countries-50m, via geo.mjs).
"""
import sys, os, math, json, subprocess, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SR = 1080, 1920, 30, 44100
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work_tmp"); os.makedirs(WORK, exist_ok=True)
GREEN, ORANGE, RED, DARK, YEL = (34, 197, 94), (255, 138, 0), (230, 40, 50), (28, 32, 40), (255, 214, 0)
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
EMOJI_TTF = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
def fnt(s): return ImageFont.truetype(FONT, s)
def ease(t): t = min(1, max(0, t)); return t * t * (3 - 2 * t)
def wrap(text, f, maxw):
    lines, cur = [], ""
    for w_ in text.split():
        t = (cur + " " + w_).strip()
        if f.getlength(t) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w_
    return lines + [cur]
def over(fr, rgba, x, y, alpha=1.0, scale=1.0):
    if alpha <= 0: return
    x, y = int(round(x)), int(round(y))
    if scale != 1.0:
        h0, w0 = rgba.shape[:2]; rgba = cv2.resize(rgba, (max(1, int(w0 * scale)), max(1, int(h0 * scale))), interpolation=cv2.INTER_LINEAR)
        x += (w0 - rgba.shape[1]) // 2; y += (h0 - rgba.shape[0]) // 2
    h, w = rgba.shape[:2]; x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0: return
    s = rgba[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32); a = s[..., 3:4] / 255 * alpha
    fr[y0:y1, x0:x1] = fr[y0:y1, x0:x1] * (1 - a) + s[..., :3] * a
A_ = lambda im: np.asarray(im.convert("RGBA"))

def emoji(code, s):
    f = ImageFont.truetype(EMOJI_TTF, 109)
    im = Image.new("RGBA", (160, 160), (0, 0, 0, 0)); ImageDraw.Draw(im).text((16, 10), chr(int(code, 16)), font=f, embedded_color=True)
    im = im.crop(im.getbbox()); sc = s / max(im.size); im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
    c = Image.new("RGBA", (s, s), (0, 0, 0, 0)); c.alpha_composite(im, ((s - im.width) // 2, (s - im.height) // 2)); return c

# ------------------------------------------------------------------ Flaggen (offizielle Farben / Proportionen, vereinfachte Wappen)
def star(cx, cy, r, rot=0.0):
    return [(cx + (r if k % 2 == 0 else r * 0.382) * math.cos(rot - math.pi / 2 + k * math.pi / 5),
             cy + (r if k % 2 == 0 else r * 0.382) * math.sin(rot - math.pi / 2 + k * math.pi / 5)) for k in range(10)]
def nordic(w, h, bg, cross, inner, cols, rows):
    # cols/rows: Abschnitte (links, Kreuz, rechts) bzw. (oben, Kreuz, unten); inner: (Rand, Kern) für Norwegen
    im = Image.new("RGB", (w, h), bg); d = ImageDraw.Draw(im); U = w / sum(cols); V = h / sum(rows)
    if inner is None:
        d.rectangle([cols[0] * U, 0, (cols[0] + cols[1]) * U, h], fill=cross); d.rectangle([0, rows[0] * V, w, (rows[0] + rows[1]) * V], fill=cross)
    else:
        d.rectangle([cols[0] * U, 0, (cols[0] + cols[1]) * U, h], fill=cross); d.rectangle([0, rows[0] * V, w, (rows[0] + rows[1]) * V], fill=cross)
        d.rectangle([(cols[0] + 1) * U, 0, (cols[0] + 3) * U, h], fill=inner); d.rectangle([0, (rows[0] + 1) * V, w, (rows[0] + 3) * V], fill=inner)
    return im
def flag(name, w):
    if name == "spanien":
        h = w * 2 // 3; im = Image.new("RGB", (w, h), (170, 21, 27)); d = ImageDraw.Draw(im)
        d.rectangle([0, h / 4, w, h * 3 / 4], fill=(241, 191, 0))
        cx, cy, s = w * 0.33, h / 2, h * 0.18      # stark vereinfachtes Wappen
        d.rounded_rectangle([cx - s * 0.75, cy - s * 0.6, cx + s * 0.75, cy + s * 0.95], s * 0.35, fill=(170, 21, 27), outline=(120, 90, 20), width=max(1, w // 120))
        d.rectangle([cx - s * 0.75, cy - s * 1.05, cx + s * 0.75, cy - s * 0.7], fill=(200, 150, 30))
        d.rectangle([cx - s * 1.25, cy - s * 0.6, cx - s * 0.95, cy + s * 0.9], fill=(220, 220, 210)); d.rectangle([cx + s * 0.95, cy - s * 0.6, cx + s * 1.25, cy + s * 0.9], fill=(220, 220, 210))
        return im
    if name == "italien": h = w * 2 // 3; cols = [(0, 146, 70), (255, 255, 255), (206, 43, 55)]; vert = True
    elif name == "frankreich": h = w * 2 // 3; cols = [(0, 38, 84), (255, 255, 255), (237, 41, 57)]; vert = True
    elif name == "deutschland": h = w * 3 // 5; cols = [(0, 0, 0), (221, 0, 0), (255, 206, 0)]; vert = False
    elif name == "oesterreich": h = w * 2 // 3; cols = [(200, 16, 46), (255, 255, 255), (200, 16, 46)]; vert = False
    elif name == "ungarn": h = w // 2; cols = [(205, 42, 62), (255, 255, 255), (67, 111, 77)]; vert = False
    elif name == "schweden": return nordic(w, int(w * 10 / 16), (0, 106, 167), (254, 204, 0), None, (5, 2, 9), (4, 2, 4))
    elif name == "norwegen": return nordic(w, int(w * 16 / 22), (186, 12, 47), (255, 255, 255), (0, 32, 91), (6, 4, 12), (6, 4, 6))
    elif name == "finnland": return nordic(w, int(w * 11 / 18), (255, 255, 255), (0, 47, 108), None, (5, 3, 10), (4, 3, 4))
    elif name == "daenemark": return nordic(w, int(w * 28 / 37), (200, 16, 46), (255, 255, 255), None, (12, 4, 21), (12, 4, 12))
    elif name == "griechenland":
        h = w * 2 // 3; im = Image.new("RGB", (w, h), (255, 255, 255)); d = ImageDraw.Draw(im); b = (13, 94, 175); sh = h / 9
        for k in range(0, 9, 2): d.rectangle([0, k * sh, w, (k + 1) * sh], fill=b)
        c = 5 * sh; d.rectangle([0, 0, c, c], fill=b); d.rectangle([2 * sh, 0, 3 * sh, c], fill=(255, 255, 255)); d.rectangle([0, 2 * sh, c, 3 * sh], fill=(255, 255, 255))
        return im
    elif name == "portugal":
        h = w * 2 // 3; im = Image.new("RGB", (w, h), (218, 41, 28)); d = ImageDraw.Draw(im); x = w * 2 / 5
        d.rectangle([0, 0, x, h], fill=(4, 106, 56)); r = h * 0.25; cy = h / 2
        d.ellipse([x - r, cy - r, x + r, cy + r], outline=(255, 225, 0), width=max(2, int(r * 0.22)))
        d.line([(x - r, cy), (x + r, cy)], fill=(255, 225, 0), width=max(1, int(r * 0.12)))
        s = r * 0.55; d.rounded_rectangle([x - s * 0.8, cy - s, x + s * 0.8, cy + s * 0.9], s * 0.5, fill=(255, 255, 255))
        d.rounded_rectangle([x - s * 0.55, cy - s * 0.72, x + s * 0.55, cy + s * 0.62], s * 0.4, fill=(218, 41, 28))
        d.rounded_rectangle([x - s * 0.3, cy - s * 0.45, x + s * 0.3, cy + s * 0.35], s * 0.2, fill=(255, 255, 255))
        return im
    else: raise KeyError(name)
    im = Image.new("RGB", (w, h)); d = ImageDraw.Draw(im)
    for k, c in enumerate(cols):
        if vert: d.rectangle([k * w / 3, 0, (k + 1) * w / 3, h], fill=c)
        else: d.rectangle([0, k * h / 3, w, (k + 1) * h / 3], fill=c)
    return im

# ------------------------------------------------------------------ Karte
MX0, MY0, MX1, MY1 = 40, 410, 1040, 1290
GEO = None
def geo():
    global GEO
    if GEO is None: GEO = json.load(open(os.path.join(HERE, "countries.geojson")))["features"]
    return GEO
def make_proj(bbox):
    lon0, lat0 = math.radians((bbox[0] + bbox[2]) / 2), math.radians((bbox[1] + bbox[3]) / 2)
    def laea(lon, lat):
        l, p = np.radians(lon), np.radians(lat); c = 1 + math.sin(lat0) * np.sin(p) + math.cos(lat0) * np.cos(p) * np.cos(l - lon0)
        k = np.sqrt(2 / np.maximum(c, 1e-6)); return k * np.cos(p) * np.sin(l - lon0), -k * (math.cos(lat0) * np.sin(p) - math.sin(lat0) * np.cos(p) * np.cos(l - lon0))
    t = np.linspace(0, 1, 50); bl = np.concatenate([bbox[0] + (bbox[2] - bbox[0]) * t, np.full(50, bbox[2]), bbox[0] + (bbox[2] - bbox[0]) * t, np.full(50, bbox[0])])
    bt = np.concatenate([np.full(50, bbox[1]), bbox[1] + (bbox[3] - bbox[1]) * t, np.full(50, bbox[3]), bbox[1] + (bbox[3] - bbox[1]) * t])
    x, y = laea(bl, bt); s = min((MX1 - MX0 - 40) / (x.max() - x.min()), (MY1 - MY0 - 40) / (y.max() - y.min()))
    cx, cy = (x.max() + x.min()) / 2, (y.max() + y.min()) / 2
    def P(lon, lat):
        X, Y = laea(np.asarray(lon, float), np.asarray(lat, float)); return (MX0 + MX1) / 2 + (X - cx) * s, (MY0 + MY1) / 2 + (Y - cy) * s
    return P
def rings(feat):
    g = feat["geometry"]
    if g is None: return []
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    return [r for poly in polys for r in poly]
def draw_map(rnd):
    """Liefert (Karten-RGBA in Vollbild-Größe, {Land: Maske})"""
    P = make_proj(rnd["bbox"]); S = 2; mw, mh = (MX1 - MX0) * S, (MY1 - MY0) * S
    sea = Image.new("RGBA", (mw, mh), (170, 214, 238, 255)); d = ImageDraw.Draw(sea)
    rng = np.random.default_rng(3)
    for k in range(9):          # Wellenlinien im Meer (Skizzen-Look)
        y = rng.uniform(0.05, 0.95) * mh; x = rng.uniform(0.05, 0.8) * mw
        pts = [(x + i * 9 * S, y + 5 * S * math.sin(i * 0.9)) for i in range(9)]; d.line(pts, fill=(120, 175, 210, 255), width=3 * S, joint="curve")
    land = Image.new("RGBA", (mw, mh), (0, 0, 0, 0)); dl = ImageDraw.Draw(land); masks = {}
    want = {p["land"] for p in rnd["pins"]} | {rnd["heimat"]["land"]}
    feats = []
    for f in geo():
        rs = rings(f)
        if not rs: continue
        a = np.concatenate([np.asarray(r) for r in rs])
        if a[:, 0].max() < -40 or a[:, 0].min() > 70 or a[:, 1].max() < 20: continue
        pr = []
        for r in rs:
            r = np.asarray(r); X, Y = P(r[:, 0], r[:, 1]); pr.append([((xx - MX0) * S, (yy - MY0) * S) for xx, yy in zip(X, Y)])
        feats.append((f["properties"]["name"], pr))
    for nm, pr in feats:
        for r in pr:
            if len(r) > 2: dl.polygon(r, fill=(247, 238, 214, 255))
    for nm, pr in feats:
        for r in pr:
            if len(r) > 2: dl.line(r + [r[0]], fill=(95, 85, 72, 255), width=3 * S, joint="curve")
        if nm in want:
            m = Image.new("L", (mw, mh), 0); dm = ImageDraw.Draw(m)
            for r in pr:
                if len(r) > 2: dm.polygon(r, fill=255)
            masks[nm] = np.asarray(m.resize((MX1 - MX0, MY1 - MY0), Image.LANCZOS)).astype(np.float32) / 255
    sea.alpha_composite(land); card = sea.resize((MX1 - MX0, MY1 - MY0), Image.LANCZOS)
    # abgerundete Karte + handgezeichneter Doppelrand + Schatten
    rm = Image.new("L", card.size, 0); ImageDraw.Draw(rm).rounded_rectangle([0, 0, card.width - 1, card.height - 1], 44, fill=255); card.putalpha(rm)
    full = Image.new("RGBA", (W, H), (0, 0, 0, 0)); shd = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shd).rounded_rectangle([MX0 + 10, MY0 + 16, MX1 + 10, MY1 + 16], 44, fill=(0, 0, 0, 120)); shd = shd.filter(ImageFilter.GaussianBlur(14))
    full.alpha_composite(shd); full.alpha_composite(card, (MX0, MY0)); d = ImageDraw.Draw(full)
    for k, off in enumerate((0, 7)):
        rr = 44; pts = []
        for t in np.linspace(0, 1, 400):
            per = 2 * (MX1 - MX0) + 2 * (MY1 - MY0); s_ = t * per
            if s_ < MX1 - MX0: x, y = MX0 + s_, MY0
            elif s_ < MX1 - MX0 + MY1 - MY0: x, y = MX1, MY0 + s_ - (MX1 - MX0)
            elif s_ < 2 * (MX1 - MX0) + MY1 - MY0: x, y = MX1 - (s_ - (MX1 - MX0) - (MY1 - MY0)), MY1
            else: x, y = MX0, MY1 - (s_ - 2 * (MX1 - MX0) - (MY1 - MY0))
            pts.append((x + (2.5 + off * 0.3) * math.sin(t * 37 + k), y + (2.5 + off * 0.3) * math.cos(t * 29 + k)))
        d.line(pts + [pts[0]], fill=(30, 30, 30, 220 - 90 * k), width=6 - 2 * k, joint="curve")
    return np.asarray(full), masks, P

def tint(fr, mask, col, a):
    if a <= 0: return
    roi = fr[MY0:MY1, MX0:MX1]; m = mask[..., None] * a * 0.55; roi[:] = roi * (1 - m) + np.array(col, np.float32) * m

# ------------------------------------------------------------------ Pins
FW = 160; STICK = 58
def pin_img(name, letter, state):
    """state: 0 normal, 1 falsch (rot), 2 richtig (grün). Ursprung = Pin-Spitze bei (ox, oy)."""
    f = flag(name, FW * 2).resize((FW, None) if False else (FW, int(flag(name, FW * 2).height / 2)), Image.LANCZOS); fh = f.height
    bw = 8; Wd, Hd = FW + 2 * bw + 80, fh + 2 * bw + STICK + 80
    L = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0)); d = ImageDraw.Draw(L); ox, oy = Wd // 2, fh + 2 * bw + STICK + 40
    fx0, fy0 = ox - FW // 2 - bw, 40
    sh = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0)); ImageDraw.Draw(sh).rectangle([fx0 + 8, fy0 + 10, fx0 + FW + 2 * bw + 8, fy0 + fh + 2 * bw + 10], fill=(0, 0, 0, 120))
    L.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7))); d = ImageDraw.Draw(L)
    d.line([(ox, fy0 + fh), (ox, oy)], fill=(60, 50, 45, 255), width=7)
    d.ellipse([ox - 11, oy - 11, ox + 11, oy + 11], fill=(230, 40, 50, 255), outline=(255, 255, 255, 255), width=4)
    border = {0: (255, 255, 255, 255), 1: RED + (255,), 2: GREEN + (255,)}[state]
    d.rectangle([fx0, fy0, fx0 + FW + 2 * bw, fy0 + fh + 2 * bw], fill=border); L.paste(f, (fx0 + bw, fy0 + bw))
    d.rectangle([fx0, fy0, fx0 + FW + 2 * bw, fy0 + fh + 2 * bw], outline=(40, 40, 40, 255), width=2)
    r = 30; cx, cy = fx0 + 4, fy0 + 4          # Buchstaben-Plakette oben links
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ORANGE + (255,), outline=(255, 255, 255, 255), width=5)
    d.text((cx, cy + 2), letter, font=fnt(40), fill="white", anchor="mm")
    if state:                                   # Markierung oben rechts: rotes X / grüner Haken
        cx2, cy2 = fx0 + FW + 2 * bw - 4, fy0 + 4; col = RED if state == 1 else GREEN
        d.ellipse([cx2 - r, cy2 - r, cx2 + r, cy2 + r], fill=col + (255,), outline=(255, 255, 255, 255), width=5)
        if state == 1:
            for s_ in (1, -1): d.line([(cx2 - 12, cy2 - 12 * s_), (cx2 + 12, cy2 + 12 * s_)], fill="white", width=8)
        else: d.line([(cx2 - 13, cy2 + 1), (cx2 - 3, cy2 + 11), (cx2 + 14, cy2 - 11)], fill="white", width=8, joint="curve")
    return A_(L), ox, oy, (fx0, fy0, fx0 + FW + 2 * bw, fy0 + fh + 2 * bw)

def green_ring(fr, box, p, ox, oy):
    """handgezeichneter grüner Kreis um einen Pin, p = Zeichenfortschritt 0..1"""
    if p <= 0: return
    x0, y0, x1, y1 = box; cx, cy = ox + (x0 + x1) / 2, oy + (y0 + y1) / 2 + 20; rx, ry = (x1 - x0) / 2 + 36, (y1 - y0) / 2 + 70
    n = int(8 + 70 * p); ts = np.linspace(-0.6, -0.6 + 2 * math.pi * 1.08 * p, n)
    pts = np.array([(cx + rx * (1 + 0.03 * math.sin(3 * t)) * math.cos(t), cy + ry * (1 + 0.03 * math.cos(2 * t)) * math.sin(t)) for t in ts])
    for wdt, col in ((16, (10, 70, 30)), (10, GREEN)):
        cv2.polylines(fr, [(pts * 16).astype(np.int32).reshape(-1, 1, 2)], False, col, wdt, cv2.LINE_AA, shift=4)

# ------------------------------------------------------------------ Hintergrund mit Skizzen
def doodles_flaggen(d, rng, col):
    def flg(x, y, s, r):
        c, sn = math.cos(r), math.sin(r); P = lambda dx, dy: (x + (dx * c - dy * sn) * s, y + (dx * sn + dy * c) * s)
        d.line([P(0, 1.2), P(0, -1.0)], fill=col, width=6); d.ellipse([P(0, -1.08)[0] - 7, P(0, -1.08)[1] - 7, P(0, -1.08)[0] + 7, P(0, -1.08)[1] + 7], fill=col)
        top = [P(t * 1.1, -0.95 + 0.08 * math.sin(t * 6)) for t in np.linspace(0, 1, 14)]
        bot = [P(t * 1.1, -0.25 + 0.08 * math.sin(t * 6)) for t in np.linspace(1, 0, 14)]
        d.line(top + bot + [top[0]], fill=col, width=5, joint="curve")
    def star5(x, y, r, rot=0):
        pts = star(x, y, r, rot); d.line(pts + [pts[0]], fill=col, width=5, joint="curve")
    def globe(x, y, r):
        d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=5); d.ellipse([x - r * .45, y - r, x + r * .45, y + r], outline=col, width=4)
        d.line([(x - r, y), (x + r, y)], fill=col, width=4)
    def compass(x, y, r):
        d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=5)
        d.polygon([(x, y - r * .85), (x + r * .2, y), (x, y + r * .85), (x - r * .2, y)], outline=col, width=4); d.text((x, y - r - 22), "N", font=fnt(30), fill=col, anchor="mm")
    def pinsk(x, y, s):
        d.ellipse([x - s, y - 2 * s, x + s, y], outline=col, width=5); d.line([(x - s * .9, y - s * .6), (x, y + s * 1.4), (x + s * .9, y - s * .6)], fill=col, width=5, joint="curve")
    flg(70, 300, 40, -.15); flg(985, 290, 38, .12); globe(90, 1870, 45); compass(990, 1872, 40)
    for x, y, r in ((40, 1300, 16), (1045, 1305, 16)): star5(x, y, r, rng.uniform(-.3, .3))
    pinsk(30, 380, 14); pinsk(1050, 372, 14)
def background(cfg):
    y = np.linspace(0, 1, H)[:, None, None]; x = np.linspace(-1, 1, W)[None, :, None]
    g = np.array(cfg["oben"], np.float32) * (1 - y) + np.array(cfg["unten"], np.float32) * y; g = g * (1 - 0.3 * (x ** 2 * 0.7))
    im = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert("RGBA")
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); doodles_flaggen(ImageDraw.Draw(L), np.random.default_rng(4), (255, 255, 255, 70))
    im.alpha_composite(L); return np.asarray(im.convert("RGB")).astype(np.float32)

# ------------------------------------------------------------------ Texte / Pillen
PX0, PX1, PY0, PH, PG = 70, 1010, 1330, 140, 28
def pill(k, ans, fname, state):   # 0 normal, 1 richtig (grün), 2 abgedunkelt
    L = Image.new("RGBA", (PX1 - PX0 + 40, PH + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.rounded_rectangle([20, 28, PX1 - PX0 + 20, PH + 28], PH // 2, fill=(0, 0, 0, 110))
    fill = {0: (255, 255, 255, 248), 1: GREEN + (255,), 2: (255, 255, 255, 150)}[state]
    d.rounded_rectangle([20, 20, PX1 - PX0 + 20, PH + 20], PH // 2, fill=fill)
    r = PH / 2 - 14; cx, cy = 20 + 14 + r, 20 + PH / 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill={0: ORANGE, 1: (255, 255, 255), 2: (190, 190, 190)}[state])
    d.text((cx, cy + 3), "ABC"[k], font=fnt(66), fill=GREEN if state == 1 else "white", anchor="mm")
    fl = flag(fname, 220).resize((110, None) if False else (110, int(flag(fname, 220).height / 2)), Image.LANCZOS)
    if state == 2: fl = Image.blend(fl, Image.new("RGB", fl.size, (235, 235, 235)), 0.5)
    fx = int(cx + r + 26); fy = int(cy - fl.height / 2)
    d.rectangle([fx - 4, fy - 4, fx + fl.width + 3, fy + fl.height + 3], fill=(40, 40, 40, 255)); L.paste(fl, (fx, fy))
    fa = 76; tx = fx + fl.width + 30
    while fnt(fa).getlength(ans) > PX1 - PX0 - tx - 130 and fa > 40: fa -= 2
    d.text((tx, cy + 2), ans, font=fnt(fa), fill={0: DARK, 1: "white", 2: (120, 120, 120)}[state], anchor="lm")
    return A_(L)

def question_layer(i, rd, quiz, n):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    if i == 0:
        f = fnt(44); t = quiz["haken"]; w = f.getlength(t) + 60
        d.rounded_rectangle([W / 2 - w / 2, 60, W / 2 + w / 2, 126], 33, fill=(0, 0, 0, 170)); d.text((W / 2, 93), t, font=f, fill=YEL, anchor="mm")
    last = i == n - 1; chip = "DIE SCHWERSTE!" if last else f"RUNDE {i + 1}/{n}"
    fc = fnt(44); cw = fc.getlength(chip) + 70
    d.rounded_rectangle([W / 2 - cw / 2, 158, W / 2 + cw / 2, 224], 33, fill=RED if last else (255, 255, 255, 240))
    d.text((W / 2, 191), chip, font=fc, fill="white" if last else DARK, anchor="mm")
    f = fnt(70); lines = wrap(rd["frage"], f, W - 110); y = 282 if len(lines) > 1 else 320
    for ln in lines:
        d.text((W / 2, y), ln, font=f, fill="white", anchor="mm", stroke_width=8, stroke_fill=(10, 10, 10)); y += 80
    return A_(L)

def score_img(k, n):
    L = Image.new("RGBA", (200, 90), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.rounded_rectangle([4, 10, 196, 86], 36, fill=(0, 0, 0, 110)); d.rounded_rectangle([0, 2, 192, 80], 36, fill=GREEN + (255,), outline="white", width=5)
    d.line([(30, 42), (44, 57), (68, 26)], fill="white", width=10, joint="curve"); d.text((132, 42), f"{k}/{n}", font=fnt(50), fill="white", anchor="mm")
    return A_(L)

def number_img(k):
    L = Image.new("RGBA", (190, 190), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.ellipse([10, 14, 184, 188], fill=(0, 0, 0, 110)); d.ellipse([6, 6, 178, 178], fill=RED + (255,), outline="white", width=8)
    d.text((92, 98), str(k), font=fnt(112), fill="white", anchor="mm"); return A_(L)

def splash():
    L = Image.new("RGBA", (W, 420), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.polygon([(-50, 70), (W + 50, 10), (W + 50, 350), (-50, 410)], fill=RED + (240,))
    d.text((W / 2, 205), "DIE SCHWERSTE!", font=fnt(120), fill=YEL, anchor="mm", stroke_width=10, stroke_fill=(30, 10, 10))
    return A_(L.rotate(3, resample=Image.BICUBIC))

def banner(t1, t2, emo):
    L = Image.new("RGBA", (W, 330), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.rounded_rectangle([40, 20, W - 40, 310], 50, fill=(0, 0, 0, 150)); d.rounded_rectangle([40, 0, W - 40, 290], 50, fill=YEL + (255,))
    fs = 84
    while fnt(fs).getlength(t1) > W - 140: fs -= 2
    d.text((W / 2, 95), t1, font=fnt(fs), fill=DARK, anchor="mm")
    fs2 = 54
    while fnt(fs2).getlength(t2) > W - 260: fs2 -= 2
    w2 = fnt(fs2).getlength(t2); d.text((W / 2 - 40, 205), t2, font=fnt(fs2), fill=DARK, anchor="mm")
    L.alpha_composite(emoji(emo, 70), (int(W / 2 - 40 + w2 / 2 + 12), 168)); return A_(L)

def sub_button():
    L = Image.new("RGBA", (700, 190), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.rounded_rectangle([10, 22, 690, 182], 40, fill=(0, 0, 0, 120)); d.rounded_rectangle([10, 10, 690, 170], 40, fill=(230, 20, 30, 255))
    L.alpha_composite(emoji("1f514", 100), (40, 40)); d.text((420, 92), "ABONNIEREN", font=fnt(70), fill="white", anchor="mm")
    return A_(L)

# ------------------------------------------------------------------ Hand mit Stift
def hand_sprite():
    S = 2; SPR = 900; ang = math.radians(48); u = np.array([math.cos(ang), math.sin(ang)]); nn = np.array([math.sin(ang), -math.cos(ang)])
    TIP = np.array([90.0, 90.0]); P = lambda t, o: tuple((TIP + u * t + nn * o) * S)
    im = Image.new("RGBA", (SPR * S, SPR * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    def cap(a, b, r, col):
        (x1, y1), (x2, y2) = a, b; r *= S; d.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=col); d.ellipse([x2 - r, y2 - r, x2 + r, y2 + r], fill=col)
        v = np.array([x2 - x1, y2 - y1]); L = np.linalg.norm(v) + 1e-6; pn = np.array([-v[1], v[0]]) / L * r
        d.polygon([(x1 + pn[0], y1 + pn[1]), (x2 + pn[0], y2 + pn[1]), (x2 - pn[0], y2 - pn[1]), (x1 - pn[0], y1 - pn[1])], fill=col)
    skin, dark = (230, 182, 150, 255), (205, 155, 125, 255)
    cap(P(320, 70), P(1100, 150), 104, dark)
    d.ellipse([P(250, 72)[0] - 120 * S, P(250, 72)[1] - 100 * S, P(250, 72)[0] + 120 * S, P(250, 72)[1] + 100 * S], fill=skin)
    for a_, b_, r in (((120, 52), (185, 78), 27), ((150, 100), (210, 118), 26), ((178, 142), (228, 152), 23)): cap(P(*a_), P(*b_), r, dark)
    cap(P(40, 0), P(420, 0), 12, (35, 45, 80, 255)); d.polygon([P(0, 0), P(42, 10), P(42, -10)], fill=(180, 180, 185, 255))
    cap(P(80, -20), P(150, -30), 23, skin); cap(P(150, -30), P(250, -22), 30, skin)
    cap(P(74, 13), P(140, 24), 22, skin); cap(P(140, 24), P(205, 58), 26, skin)
    im = im.resize((SPR, SPR), Image.LANCZOS); a = np.asarray(im).astype(np.float32)
    sh = cv2.GaussianBlur(a[..., 3] / 255, (0, 0), 12) * 0.35
    return a, sh, TIP
HAND, HSH, HTIP = hand_sprite()
def place_hand(fr, x, y):
    for img, dx, dy in ((HSH, 16, 22), (HAND, 0, 0)):
        ox, oy = int(x - HTIP[0] + dx), int(y - HTIP[1] + dy); h, w = img.shape[:2]
        x0, y0, x1, y1 = max(ox, 0), max(oy, 0), min(ox + w, W), min(oy + h, H)
        if x1 <= x0 or y1 <= y0: continue
        s = img[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
        if s.ndim == 2: fr[y0:y1, x0:x1] *= (1 - s[..., None])
        else: a = s[..., 3:4] / 255; fr[y0:y1, x0:x1] = s[..., :3] * a + fr[y0:y1, x0:x1] * (1 - a)
def check_pts(k):
    cy = PY0 + k * (PH + PG) + PH / 2; cx = PX1 - 80
    A, B, C = (cx - 38, cy - 2), (cx - 10, cy + 28), (cx + 40, cy - 38)
    return [(A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t) for t in np.linspace(0, 1, 9)] + \
           [(B[0] + (C[0] - B[0]) * t, B[1] + (C[1] - B[1]) * t - 6 * math.sin(math.pi * t)) for t in np.linspace(0, 1, 15)[1:]]
def draw_check(fr, pts):
    if len(pts) < 2: return
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; x0, y0, x1, y1 = int(min(xs)) - 30, int(min(ys)) - 30, int(max(xs)) + 30, int(max(ys)) + 30
    m = np.zeros((y1 - y0, x1 - x0), np.uint8); m2 = m.copy(); arr = ((np.array(pts) - [x0, y0]) * 16).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(m, [arr], False, 255, 30, cv2.LINE_AA, shift=4); cv2.polylines(m2, [arr], False, 255, 18, cv2.LINE_AA, shift=4)
    a = m[..., None] / 255.; b = m2[..., None] / 255.; roi = fr[y0:y1, x0:x1]
    roi[:] = roi * (1 - a) + np.array([16, 90, 45]) * a; roi[:] = roi * (1 - b) + 255 * b

# ------------------------------------------------------------------ Audio
def env(n, a=0.005, dec=8.0): t = np.arange(n) / SR; return np.minimum(1, t / a) * np.exp(-t * dec)
def add(buf, sig, t0):
    i = int(t0 * SR)
    if i < 0: sig = sig[-i:]; i = 0
    if i >= len(buf): return
    n = min(len(sig), len(buf) - i); buf[i:i + n] += sig[:n]
def tone(f, L, dec, amp, parts=((1, 1),)):
    t = np.arange(int(L * SR)) / SR; return sum(a * np.sin(2 * np.pi * f * m * t) for m, a in parts) * env(len(t), 0.003, dec) * amp
def whoosh(L=0.32):
    r = np.random.default_rng(9); x = r.normal(0, 1, int(L * SR)); t = np.arange(len(x)) / SR
    k = 0.03 + 0.5 * np.arange(len(x)) / len(x); y = np.zeros_like(x); a = 0.0
    for i in range(len(x)): a += k[i] * (x[i] - a); y[i] = a
    return y * np.sin(np.pi * t / L) ** 2 * 0.5
def spannung(total):   # wie musik.py: Moll, 128 BPM
    n = int(total * SR) + SR; out = np.zeros(n); r = np.random.default_rng(7); beat = 60 / 128; hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    prog = [(50, [62, 65, 69]), (46, [62, 65, 70]), (43, [62, 67, 70]), (45, [61, 64, 69])]; bar, t0 = 0, 0.0
    while t0 < total + 0.5:
        root, ch = prog[bar % 4]
        for b in range(4):
            tb = t0 + b * beat
            if b in (0, 2) or (b == 3 and bar % 2):
                k = np.arange(int(.22 * SR)) / SR; add(out, np.sin(2 * np.pi * (45 + 80 * np.exp(-k * 30)) * k) * env(len(k), .002, 14) * .5, tb)
            if b == 3:
                nz = r.normal(0, 1, int(.18 * SR)); nz -= np.convolve(nz, np.ones(10) / 10, "same"); add(out, nz * env(len(nz), .001, 18) * .12, tb)
            for h in range(2):
                nz = np.diff(r.normal(0, 1, int(.03 * SR) + 1)); add(out, nz * env(len(nz), .001, 90) * (.06 if h else .035), tb + h * beat / 2)
                add(out, tone(hz(root - 12), beat * .42, 10, .30, ((1, 1), (2, .5), (3, .2))), tb + h * beat / 2)
            for s in range(4):
                m_ = ch[(b * 4 + s) % 3] + (0 if s % 2 else -12)
                add(out, tone(hz(m_), .14, 26, .075, ((1, 1), (2, .5), (3, .33), (4, .2), (5, .12))), tb + s * beat / 4)
        if bar % 8 == 7:
            L = int(4 * beat * SR); k = np.arange(L) / SR; nz = np.convolve(r.normal(0, 1, L), np.ones(4) / 4, "same") * (k / k[-1]) ** 2 * .10
            add(out, nz + np.sin(2 * np.pi * (300 + 500 * (k / k[-1]) ** 2) * k) * (k / k[-1]) ** 2 * .03, t0)
        bar += 1; t0 += 4 * beat
    out = out[:int(total * SR)]; return out / (np.abs(out).max() + 1e-9) * 0.6

def dur(p): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout)
def prep_clip(src, dst, tempo):
    af = ("silenceremove=start_periods=1:start_threshold=-42dB,silenceremove=stop_periods=-1:stop_duration=0.12:stop_threshold=-40dB:stop_silence=0.12,"
          "areverse,silenceremove=start_periods=1:start_threshold=-42dB,areverse,"
          f"atempo={tempo},highpass=f=70,loudnorm=I=-15:TP=-1.5")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", af, "-ar", str(SR), "-ac", "1", dst], check=True); return dst, dur(dst)
def read_wav(p):
    with wave.open(p) as w: x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; return x.reshape(-1, w.getnchannels()).mean(axis=1)

# ------------------------------------------------------------------ Hauptprogramm
def main():
    a = sys.argv[1:]; opt = {"--tempo": 1.1, "--tempo-aufl": 1.15, "--denkzeit": 5.0, "--musik-pegel": 0.4, "--flug": 0.5}
    k = a.index("--stimme"); stimme = a[k + 1]; del a[k:k + 2]
    for o in list(opt):
        if o in a: k = a.index(o); opt[o] = float(a[k + 1]); del a[k:k + 2]
    a = [x for x in a if x != "--still"]
    THINK = opt["--denkzeit"]; quiz = json.load(open(a[0], encoding="utf-8")); out = a[1]; rs = quiz["runden"]; n = len(rs)
    P_ = lambda nm: os.path.join(WORK, f"ff_{nm}.wav")
    QC = [prep_clip(os.path.join(stimme, f"q{i}.mp3"), P_(f"q{i}"), opt["--tempo"]) for i in range(n)]
    RC = [prep_clip(os.path.join(stimme, f"r{i}.mp3"), P_(f"r{i}"), opt["--tempo-aufl"]) for i in range(n)]
    OC = prep_clip(os.path.join(stimme, "outro.mp3"), P_("outro"), opt["--tempo-aufl"])

    segs, t = [], 0.0
    for i in range(n):
        s = {"i": i, "t0": t, "vs": t + (0.0 if i == 0 else 0.15)}
        s["c0"] = s["vs"] + QC[i][1] + 0.1; s["c1"] = s["c0"] + THINK
        s["rev"] = s["c1"] + 0.02; s["vr"] = s["rev"] + 0.1; s["fly"] = s["vr"] + RC[i][1] * opt["--flug"]
        s["end"] = max(s["vr"] + RC[i][1] + 0.35, s["fly"] + 1.4); t = s["end"]; segs.append(s)
    O = {"t0": t, "vo": t + 0.25}; O["sub"] = O["vo"] + OC[1] * 0.55; O["end"] = O["vo"] + OC[1] + 0.1; total = O["end"] + 0.3

    BG = background(quiz["farben"]); MAPS = [draw_map(rd) for rd in rs]; QL = [question_layer(i, rd, quiz, n) for i, rd in enumerate(rs)]
    PINS = []
    for i, rd in enumerate(rs):
        P = MAPS[i][2]; row = []
        for k_, pn in enumerate(rd["pins"]):
            x, y = P(*pn["lonlat"]); imgs = [pin_img(pn["flagge"], "ABC"[k_], st) for st in (0, 1, 2)]
            row.append({"x": float(x), "y": float(y), "img": imgs})
        hx, hy = P(*rd["heimat"]["lonlat"]); PINS.append((row, (float(hx), float(hy))))
    PL = [[[pill(k_, ans, rd["pins"][k_]["flagge"] if rd["pins"][k_]["flagge"] != "x" else "", st) for st in (0, 1, 2)] for k_, ans in enumerate(rd["antworten"])] for rd in rs]
    NUM = {k_: number_img(k_) for k_ in range(1, int(round(THINK)) + 1)}; SPL = splash(); CH = [check_pts(rd["richtig"]) for rd in rs]
    SC = {k_: score_img(k_, n) for k_ in range(1, n + 1)}
    OB = banner(*quiz["outro_banner"]); CB = banner("Wie viele hattest du?", "Schreib's in die Kommentare", "1f447"); SB = sub_button()
    ENTRY = (W + 140, H + 300)
    def flagcircle(name):
        L = Image.new("RGBA", (340, 340), (0, 0, 0, 0)); d = ImageDraw.Draw(L); r = 150
        d.ellipse([170 - r, 175 - r + 8, 170 + r, 175 + r + 8], fill=(0, 0, 0, 100)); d.ellipse([170 - r, 170 - r, 170 + r, 170 + r], fill=(255, 246, 214, 255), outline=(40, 40, 40), width=6)
        f = flag(name, 210); L.paste(f, (170 - f.width // 2, 170 - f.height // 2)); d.rectangle([170 - f.width // 2, 170 - f.height // 2, 170 + f.width // 2, 170 + f.height // 2], outline=(40, 40, 40), width=3)
        return A_(L)
    OUTF = [flagcircle(rd["pins"][rd["richtig"]]["flagge"]) for rd in rs]

    def q_frame(i, tt):
        s = segs[i]; e = tt - s["t0"]; rd = rs[i]; fr = BG.copy(); mp, masks, P = MAPS[i]
        over(fr, mp, 0, 0)
        wr = rd["richtig"]; host = rd["pins"][wr]["land"]; home = rd["heimat"]["land"]
        rv = tt - s["rev"]; fl = (tt - s["fly"]) / 0.9
        if rv > 0: tint(fr, masks[host], RED, min(1, rv / 0.25) * (1 - ease(fl)))
        if fl > 0: tint(fr, masks[home], GREEN, ease(fl))
        over(fr, QL[i], 0, 0)
        row, (hx, hy) = PINS[i]
        order = sorted(range(3), key=lambda k_: row[k_]["y"])
        for k_ in order:
            pn = row[k_]; ok = k_ == wr
            pt = e - (0.05 + 0.12 * k_) if i == 0 else e - (0.25 + 0.15 * k_)
            if i == 0 and tt < 0.02: pt = 1
            if pt <= 0: continue
            drop = (1 - ease(pt / 0.25)) * -60
            st = 0 if rv < 0 else (1 if ok else 2)
            x, y = pn["x"], pn["y"]
            if ok and fl > 0:
                f_ = ease(fl); x = pn["x"] + (hx - pn["x"]) * f_; y = pn["y"] + (hy - pn["y"]) * f_ - 140 * math.sin(math.pi * min(1, fl))
                if fl >= 1: st = 2
            img, ox, oy, box = pn["img"][st]
            sc = 1 + (0.12 * math.sin(min(1, rv / 0.3) * math.pi) if ok and 0 < rv < 0.3 else 0)
            over(fr, img, x - ox, y - oy + drop, min(1, pt / 0.1), sc)
            if not ok and rv > 0.45: green_ring(fr, box, min(1, (rv - 0.45) / 0.4), x - ox, y - oy)
        for k_ in range(3):
            pt = e - (0.05 + 0.12 * k_) if i == 0 else e - (0.3 + 0.15 * k_)
            if i == 0 and tt < 0.02: pt = 1
            if pt <= 0: continue
            sc = 0.7 + 0.3 * ease(pt / 0.14); ok = k_ == wr
            st = (1 if ok else 2) if tt >= s["rev"] + 0.3 else 0
            bump = 1 + 0.06 * math.sin(min(1, (tt - s["rev"] - 0.3) / 0.25) * math.pi) if st == 1 else 1
            over(fr, PL[i][k_][st], PX0 - 20, PY0 + k_ * (PH + PG) - 20, min(1, pt / 0.08), sc * bump)
        if s["c0"] <= tt < s["c1"]:
            p = (tt - s["c0"]) / THINK; N_ = len(NUM); num = N_ - min(N_ - 1, int(p * N_)); lp = (p * N_) % 1
            over(fr, NUM[num], 860, 1105, 1, 1 + 0.25 * max(0, 1 - lp / 0.2))
            x0b, y0b, x1b, y1b = 70, 1846, 1010, 1878; fr[y0b:y1b, x0b:x1b] *= 0.5; wb = int((x1b - x0b - 8) * (1 - p))
            col = np.array([34, 197, 94]) if p < 0.4 else np.array([255, 190, 0]) if p < 0.75 else np.array([235, 50, 50])
            if wb > 8: fr[y0b + 4:y1b - 4, x0b + 4:x0b + 4 + wb] = col
        score = i + 1 if rv > 0.4 else i
        if score > 0:
            pp = min(1, (rv - 0.4) / 0.25) if score == i + 1 else 1
            over(fr, SC[score], 860, 150, 1, 1 + 0.3 * math.sin(pp * math.pi) * (score == i + 1))
        tk = s["rev"] + 0.3; pts = CH[i]
        if tt >= tk: draw_check(fr, pts[:max(2, int(min(1, (tt - tk) / 0.3) * (len(pts) - 1)) + 1)])
        if tk - 0.45 <= tt < tk + 0.85:
            if tt < tk: f = ease((tt - (tk - 0.45)) / 0.45); pos = (ENTRY[0] + (pts[0][0] - ENTRY[0]) * f, ENTRY[1] + (pts[0][1] - ENTRY[1]) * f)
            elif tt < tk + 0.3: pos = pts[min(len(pts) - 1, int((tt - tk) / 0.3 * (len(pts) - 1)))]
            else: f = ease((tt - tk - 0.3) / 0.55); pos = (pts[-1][0] + (ENTRY[0] - pts[-1][0]) * f, pts[-1][1] + (ENTRY[1] - pts[-1][1]) * f)
            place_hand(fr, *pos)
        if i == n - 1 and e < 0.9:
            al = min(1, e / 0.08) * min(1, (0.9 - e) / 0.15); over(fr, SPL, 0, 640, al, 1 + 0.3 * max(0, 1 - e / 0.12))
        return fr

    def outro_frame(tt):
        e = tt - O["t0"]; fr = BG.copy()
        for k_ in range(n):
            cx = 200 + k_ * 340; cy = 700; p = ease((e - 0.1 * k_) / 0.3)
            if p > 0: over(fr, OUTF[k_], cx - 170, cy - 170, p, 0.6 + 0.4 * p)
        f = fnt(80); d0 = Image.new("RGBA", (W, 200), (0, 0, 0, 0)); ImageDraw.Draw(d0).text((W / 2, 100), quiz.get("outro_titel", "Alle 3 gefunden?"), font=f, fill="white", anchor="mm", stroke_width=9, stroke_fill=(10, 10, 10))
        over(fr, A_(d0), 0, 330)
        p = ease((tt - O["vo"] + 0.1) / 0.25); over(fr, CB, 0, int(960 + (1 - p) * 80), p)
        sp = (tt - O["sub"]) / 0.3
        if sp > 0: over(fr, OB, 0, 1330, min(1, sp)); over(fr, SB, 190, 1660, min(1, sp), 0.6 + 0.4 * ease(sp) + 0.08 * math.sin(min(1, sp) * math.pi))
        if tt < O["t0"] + 0.2: g = q_frame(n - 1, O["t0"] - 0.001); a_ = (tt - O["t0"]) / 0.2; fr = fr * a_ + g * (1 - a_)
        if tt >= O["end"]:
            p = ease((tt - O["end"]) / 0.3); g = q_frame(0, 0.0); dx = int(W * p); o2 = fr.copy()
            if dx > 0: o2[:, :W - dx] = fr[:, dx:]; o2[:, W - dx:] = g[:, :dx]
            return o2
        return fr

    def frame(tt):
        if tt >= O["t0"]: return outro_frame(tt)
        s = next(x for x in segs if x["t0"] <= tt < x["end"]); i = s["i"]; fr = q_frame(i, tt)
        if i > 0 and tt - s["t0"] < 0.2: a_ = (tt - s["t0"]) / 0.2; fr = fr * a_ + q_frame(i - 1, segs[i - 1]["end"] - 0.001) * (1 - a_)
        return fr

    pre = os.path.splitext(out)[0]
    if "--still" in sys.argv:
        for nm, tt in (("erstes_bild", 0.0), ("countdown", segs[0]["c0"] + 0.3), ("aufl1_rot", segs[0]["rev"] + 1.0), ("aufloesung1", segs[0]["end"] - 0.1),
                       ("frage2", segs[1]["c0"] - 0.2), ("aufloesung2", segs[1]["end"] - 0.1), ("frage3", segs[2]["c0"] + 0.2), ("flug3", segs[2]["fly"] + 0.45),
                       ("aufloesung3", segs[2]["end"] - 0.1), ("outro", O["sub"] + 0.5), ("hand", segs[1]["rev"] + 0.45), ("letztes", total - 1 / FPS)):
            Image.fromarray(np.clip(frame(tt), 0, 255).astype(np.uint8)).save(f"{pre}_{nm}.png")
        print(f"Stills ok ({total:.2f} s)"); return

    silent = os.path.join(WORK, "ff_stumm.mp4"); nfr = int(round(total * FPS))
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    for k_ in range(nfr): p.stdin.write(np.clip(frame(k_ / FPS), 0, 255).astype(np.uint8).tobytes())
    p.stdin.close(); p.wait(); total = nfr / FPS

    N = int(total * SR); voice = np.zeros(N + SR)
    for s in segs: add(voice, read_wav(QC[s["i"]][0]), s["vs"]); add(voice, read_wav(RC[s["i"]][0]), s["vr"])
    add(voice, read_wav(OC[0]), O["vo"]); voice = voice[:N]
    sf = np.zeros(N + SR); wh = whoosh(); NT = len(NUM)
    for s in segs:
        for k_ in range(NT): add(sf, tone(1700, .07, 60, .32) + tone(850, .07, 60, .12), s["c0"] + k_ * THINK / NT)
        for tt in np.arange(s["c0"] + THINK / NT / 2, s["c1"] - 0.05, THINK / NT): add(sf, tone(1250, .05, 70, .18), tt)
        if s["i"] > 0: add(sf, wh * 0.8, s["t0"] - 0.05)
        if s["i"] == n - 1:
            t_ = np.arange(int(.7 * SR)) / SR; add(sf, np.sin(2 * np.pi * (40 + 60 * np.exp(-t_ * 9)) * t_) * env(len(t_), .002, 5) * .6, s["t0"])
        for k_ in range(3): add(sf, tone(900 + 200 * k_, .08, 40, .15), s["t0"] + (0.05 + 0.12 * k_ if s["i"] == 0 else 0.25 + 0.15 * k_))
        add(sf, tone(180, .25, 12, .35, ((1, 1), (2, .4))), s["rev"])                                 # Buzz: falsche Flagge
        add(sf, tone(1318.5, 1.0, 4.5, .45, ((1, 1), (2, .45), (3, .15))) + tone(1975.5, 1.0, 6, .24), s["rev"] + 0.3)
        add(sf, wh * 0.9, s["fly"]); add(sf, tone(1568, .5, 8, .25) + tone(2093, .5, 9, .15), s["fly"] + 0.9)   # Flug + Landung
    add(sf, wh, O["t0"] - 0.05)
    add(sf, tone(2093, 1.2, 3.5, .32, ((1, 1), (2, .3))) + tone(3136, 1.2, 5, .14), O["sub"])                  # Bing beim Abo-Button
    add(sf, wh, O["end"] - 0.02)
    ev = cv2.GaussianBlur(np.abs(voice).astype(np.float32).reshape(1, -1), (0, 0), sigmaX=SR * 0.06, sigmaY=0.01).ravel()
    duck = 1 - 0.45 * np.clip(ev / (ev.max() + 1e-9) * 3, 0, 1)
    mix = voice * 0.9 + spannung(total)[:N] * opt["--musik-pegel"] * duck + sf[:N] * 0.8
    k_ = int(0.02 * SR); mix[-k_:] *= np.linspace(1, 0, k_); mix = np.clip(mix / max(1, np.abs(mix).max() / 0.95), -1, 1)
    aw = os.path.join(WORK, "ff_mix.wav")
    with wave.open(aw, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(np.repeat((mix * 32767).astype(np.int16)[:, None], 2, axis=1).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", aw, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5",
                    "-ar", "44100", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
    with open(pre + "_zeiten.txt", "w", encoding="utf-8") as f:
        for s in segs: f.write(f"{s['t0']:05.2f}–{s['end']:05.2f} s  Runde {s['i'] + 1}: Stimme {s['vs']:.2f}, Countdown {s['c0']:.2f}–{s['c1']:.2f}, Auflösung {s['rev']:.2f}, Flug {s['fly']:.2f}\n")
        f.write(f"{O['t0']:05.2f}–{O['end']:05.2f} s  Outro (Abo-Button + Bing {O['sub']:.2f})\n{total:05.2f} s  Ende -> Loop zu Runde 1\n")
    print(f"Fertig: {out} ({total:.2f} s)")

if __name__ == "__main__":
    main()
