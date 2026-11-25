#!/usr/bin/env python3
"""wasser.py – Quizy4-Erklär-Short „Warum schwimmt Eis?“ (1080x1920, Elli, eigene Animationen).
Aufruf: python3 wasser.py <clips-Ordner mit s0..s6.wav> Ausgabe.mp4 [--still t1,t2,...]
"""
import sys, os, math, wave, subprocess, functools
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SR = 1080, 1920, 30, 44100
FONT = "/usr/share/fonts/truetype/google-fonts/ofl/montserrat/Montserrat[wght].ttf"
EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
YEL, WHITE, DARK, RED, GREEN = (255, 214, 0), (255, 255, 255), (12, 22, 40), (232, 45, 55), (34, 197, 94)
WATER, ICE = (45, 140, 225), (200, 236, 255)

TEXTS = [
    "Wasser bricht eine Regel, an die sich fast alle Stoffe halten. Und nur deshalb schwimmt Eis auf dem Wasser!",
    "Normalerweise ziehen sich Stoffe beim Abkühlen zusammen und werden dichter. Doch Wasser ist ein echter Rebell.",
    "Wenn Wasser gefriert, passiert etwas Verrücktes: Es dehnt sich um rund 9 Prozent aus, statt kleiner zu werden!",
    "Der Grund sind Wasserstoffbrücken. Im flüssigen Wasser bewegen sich die Moleküle frei. Doch beim Gefrieren zwingen diese Brücken sie in ein starres, sechseckiges Gitter.",
    "Dieses Gitter ist wie ein offener Bauplan mit vielen Hohlräumen. Es braucht mehr Platz, bei genau gleicher Masse. Mehr Volumen bei gleicher Masse heißt: geringere Dichte. Eis ist also weniger dicht als flüssiges Wasser.",
    "Genau deshalb schwimmt Eis oben! Wäre Wasser wie die meisten Stoffe, würde Eis auf den Grund sinken. Und Seen und Meere würden von unten her zufrieren.",
    "So schützt die Eisschicht das Leben darunter. Hättest du gedacht, dass ein bisschen Struktur so viel bewirkt? Schreib's in die Kommentare und abonnier für mehr! Denn eins ist sicher:",
]
CHIPS = [None, "DIE REGEL", "DIE ÜBERRASCHUNG", "DER GRUND", "DICHTE", "DESHALB", "FAZIT"]
GAP = 0.22

# ------------------------------------------------------------------ Grundwerkzeuge
@functools.lru_cache(None)
def fnt(size, wt="Black"):
    f = ImageFont.truetype(FONT, size); f.set_variation_by_name(wt); return f

def ease(x):
    x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)

def clamp01(x): return min(1.0, max(0.0, x))

def back(x):            # Pop mit Überschwinger
    x = clamp01(x); c = 1.9; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

@functools.lru_cache(None)
def txt(s, size, fill=WHITE, stroke=0, sfill=(0, 0, 0), wt="Black"):
    f = fnt(size, wt); pad = stroke + 12
    bb = f.getbbox(s, stroke_width=stroke)
    im = Image.new("RGBA", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)
    return np.asarray(im)

@functools.lru_cache(None)
def emoji(ch, size, flip=False):
    f = ImageFont.truetype(EMOJI, 109); im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
    im = im.crop(im.getbbox()); s = size / max(im.size)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    if flip: im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return np.asarray(im)

@functools.lru_cache(None)
def ball(r, col, rim=None):
    S = 4; R = r * S; im = Image.new("RGBA", (2 * R + 8, 2 * R + 8), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    dk = tuple(int(c * 0.55) for c in col); d.ellipse([4, 4, 4 + 2 * R, 4 + 2 * R], fill=dk + (255,))
    d.ellipse([4 + R * 0.08, 4 + R * 0.04, 4 + 2 * R - R * 0.18, 4 + 2 * R - R * 0.22], fill=col + (255,))
    hl = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(hl).ellipse([4 + R * 0.45, 4 + R * 0.35, 4 + R * 1.0, 4 + R * 0.8], fill=(255, 255, 255, 170))
    im.alpha_composite(hl.filter(ImageFilter.GaussianBlur(R * 0.12)))
    return np.asarray(im.resize((im.width // S, im.height // S), Image.LANCZOS))

def over(fr, rgba, cx, cy, a=1.0, sc=1.0, anchor="c"):
    if a <= 0.003 or sc <= 0.01: return
    if abs(sc - 1) > 0.005: rgba = cv2.resize(rgba, None, fx=sc, fy=sc, interpolation=cv2.INTER_LINEAR)
    h, w = rgba.shape[:2]
    x = int(round(cx - w / 2)) if anchor in ("c", "t") else int(round(cx)) if anchor == "l" else int(round(cx - w))
    y = int(round(cy - h / 2)) if anchor in ("c", "l", "r") else int(round(cy))
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0: return
    s = rgba[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32); al = s[..., 3:4] / 255 * a
    roi = fr[y0:y1, x0:x1]; roi[:] = (roi * (1 - al) + s[..., :3] * al).astype(np.uint8)

def _mask_op(fr, pts_list, col, a, draw):
    allp = np.concatenate([np.asarray(p, np.float32).reshape(-1, 2) for p in pts_list])
    x0, y0 = np.floor(allp.min(0)).astype(int) - 40; x1, y1 = np.ceil(allp.max(0)).astype(int) + 40
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1 <= x0 or y1 <= y0 or a <= 0.003: return
    roi = fr[y0:y1, x0:x1]; m = np.zeros(roi.shape[:2], np.uint8)
    draw(m, [((np.asarray(p, np.float32).reshape(-1, 2) - [x0, y0]) * 16).astype(np.int32) for p in pts_list])
    al = m[..., None].astype(np.float32) / 255 * a
    roi[:] = (roi * (1 - al) + np.array(col, np.float32) * al).astype(np.uint8)

def poly(fr, pts, col, a=1.0):
    _mask_op(fr, [pts], col, a, lambda m, P: cv2.fillPoly(m, P, 255, cv2.LINE_AA, shift=4))

def lines(fr, pts, col, th=6, a=1.0, closed=False):
    _mask_op(fr, [pts], col, a, lambda m, P: cv2.polylines(m, P, closed, 255, th, cv2.LINE_AA, shift=4))

def segs(fr, seglist, col, th=5, a=1.0):
    if not seglist: return
    _mask_op(fr, seglist, col, a, lambda m, P: [cv2.polylines(m, [p], False, 255, th, cv2.LINE_AA, shift=4) for p in P])

def dashed(p, q, dash=16, gap=11):
    p, q = np.array(p, float), np.array(q, float); L = np.linalg.norm(q - p); out = []
    if L < 1: return out
    u = (q - p) / L; s = 0.0
    while s < L: out.append([p + u * s, p + u * min(L, s + dash)]); s += dash + gap
    return out

def rrect(x0, y0, x1, y1, r, n=8):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n); pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts

def circle_pts(cx, cy, r, n=48): return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]

def rot(pts, cx, cy, ang):
    c, s = math.cos(ang), math.sin(ang); return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]

def card(fr, x0, y0, x1, y1, col=(255, 255, 255), a=0.95, r=40, shadow=True):
    if shadow: poly(fr, rrect(x0 + 8, y0 + 12, x1 + 8, y1 + 12, r), (0, 0, 0), 0.35 * a)
    poly(fr, rrect(x0, y0, x1, y1, r), col, a)

def label(fr, s, cx, cy, size=54, fill=DARK, bg=YEL, a=1.0, sc=1.0, padx=34, pady=16):
    t = txt(s, size, fill); w, h = t.shape[1] - 24 + 2 * padx, size + 2 * pady
    if a <= 0.003: return
    ww, hh = w * sc, h * sc
    card(fr, cx - ww / 2, cy - hh / 2, cx + ww / 2, cy + hh / 2, bg, a, r=hh / 2)
    over(fr, t, cx, cy + 2 * sc, a, sc)

# ------------------------------------------------------------------ Hintergrund
def make_bg():
    y = np.linspace(0, 1, H)[:, None, None]
    top, bot = np.array((14, 52, 98), np.float32), np.array((5, 16, 38), np.float32)
    bg = (top * (1 - y) + bot * y + np.zeros((1, W, 1))).astype(np.float32)
    xx = np.linspace(-1, 1, W)[None, :, None]; vig = 1 - 0.28 * (xx ** 2) - 0.18 * ((y - 0.45) * 2) ** 2
    bg = np.clip(bg * vig, 0, 255).astype(np.uint8)
    rng = np.random.default_rng(3)
    for cx, cy, r in ((120, 300, 70), (960, 230, 55), (80, 1650, 60), (990, 1560, 75), (930, 980, 40), (140, 1020, 38), (520, 1820, 45)):
        sk = []                                   # handgezeichnete Schneeflocken
        for k in range(6):
            a = math.pi / 3 * k + rng.normal(0, 0.04); ex, ey = cx + r * math.cos(a), cy + r * math.sin(a)
            sk.append([(cx + rng.normal(0, 1.5), cy + rng.normal(0, 1.5)), (ex, ey)])
            for f_ in (0.55,):
                bx, by = cx + r * f_ * math.cos(a), cy + r * f_ * math.sin(a)
                for s_ in (-1, 1):
                    b2 = a + s_ * 0.75; sk.append([(bx, by), (bx + r * 0.32 * math.cos(b2), by + r * 0.32 * math.sin(b2))])
        segs(bg, sk, (170, 215, 255), 4, 0.16)
    return bg

SNOW = np.random.default_rng(11).uniform(0, 1, (46, 4))
def snow(fr, t):
    for x, y, sp, sz in SNOW:
        yy = ((y + t * (0.012 + 0.02 * sp)) % 1.0) * H; xx = x * W + 18 * math.sin(t * 0.8 + sp * 9)
        over(fr, ball(int(3 + 4 * sz), (225, 240, 255)), xx, yy, 0.25 + 0.25 * sz)

# ------------------------------------------------------------------ Audio-Hilfen
def read_wav(p):
    with wave.open(p) as w: x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return x

def word_times(x, text, t0):
    """Wortanfänge schätzen: Gewicht ~ Zeichen, verteilt nur über die stimmhaften Abschnitte."""
    hop = int(0.01 * SR); n = len(x) // hop
    e = np.array([np.sqrt(np.mean(x[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    db = 20 * np.log10(e); v = db > db.max() - 33
    k = 0                                                   # kurze Lücken (< 90 ms) zählen als Stimme
    while k < n:
        if not v[k]:
            j = k
            while j < n and not v[j]: j += 1
            if j - k < 9 and k > 0 and j < n: v[k:j] = True
            k = j
        else: k += 1
    cum = np.concatenate([[0], np.cumsum(v)]).astype(float); tot = cum[-1]
    words = text.split(); wts = np.array([len(w) + 1.5 for w in words], float); cw = np.concatenate([[0], np.cumsum(wts)]) / wts.sum()
    def inv(fr_):
        idx = np.searchsorted(cum, fr_ * tot); return t0 + min(idx, n) * hop / SR
    return [(w, inv(cw[i] + 0.002), inv(cw[i + 1] - 0.002)) for i, w in enumerate(words)]

def tone(f, dur, dec, amp, harm=((1, 1),)):
    t = np.arange(int(dur * SR)) / SR; y = sum(a * np.sin(2 * np.pi * f * h * t) for h, a in harm)
    return y * np.exp(-t * dec) * np.minimum(1, t / 0.004) * amp

def add(buf, x, t):
    i = int(t * SR)
    if i >= len(buf) or i + len(x) <= 0: return
    if i < 0: x = x[-i:]; i = 0
    n = min(len(x), len(buf) - i); buf[i:i + n] += x[:n]

def music(total):
    """ruhige, neugierige Wissens-Musik: 100 BPM, C–Am–F–G, Marimba-Arpeggio, weiches Pad, leises Ticken."""
    n = int(total * SR) + SR; out = np.zeros(n); r = np.random.default_rng(5); beat = 60 / 100
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    prog = [(48, [60, 64, 67, 72]), (45, [57, 60, 64, 69]), (41, [57, 60, 65, 69]), (43, [59, 62, 67, 71])]
    bar, t0 = 0, 0.0
    while t0 < total + 1:
        root, ch = prog[bar % 4]
        L = int(4 * beat * SR); tt = np.arange(L) / SR; pad = np.zeros(L)
        for m_ in ch[:3]:
            for det in (-0.12, 0.12): pad += np.sin(2 * np.pi * hz(m_) * (1 + det / 100) * tt)
        pad *= np.minimum(1, tt / 0.6) * np.minimum(1, (tt[-1] - tt) / 0.5) * 0.018; add(out, pad, t0)
        add(out, tone(hz(root - 12), 4 * beat, 0.9, 0.16, ((1, 1), (2, .3))), t0)
        pat = [0, 2, 1, 3, 2, 1, 3, 2]
        for s in range(8):
            m_ = ch[pat[s]] + (12 if (bar % 2 and s in (3, 7)) else 0)
            add(out, tone(hz(m_), 0.5, 9, 0.07, ((1, 1), (4, .25), (10, .05))), t0 + s * beat / 2)
        for b in range(4):
            nz = np.diff(r.normal(0, 1, int(.025 * SR) + 1)); add(out, nz * np.exp(-np.arange(len(nz)) / SR * 120) * 0.02, t0 + b * beat + beat / 2)
        bar += 1; t0 += 4 * beat
    out = out[:int(total * SR)]; return out / (np.abs(out).max() + 1e-9) * 0.6

def whoosh(dur=0.45, amp=0.22):
    r = np.random.default_rng(1); L = int(dur * SR); nz = r.normal(0, 1, L); t = np.arange(L) / L
    out = np.zeros(L); k = 1
    for i in range(0, L, 512):
        k = int(3 + 40 * (1 - math.sin(math.pi * i / L))); seg = nz[max(0, i - k):i + 512]
        out[i:i + 512] = np.convolve(seg, np.ones(k) / k, "same")[-len(out[i:i + 512]):]
    return out * np.sin(np.pi * t) ** 2 * amp * 3

def bing():
    return tone(1318.5, 1.4, 3.2, .32, ((1, 1), (2, .4), (3, .12))) + tone(1975.5, 1.4, 4.5, .18)

def sparkle(dur=1.2):
    out = np.zeros(int(dur * SR)); r = np.random.default_rng(8)
    for k in range(14): add(out, tone(r.uniform(2200, 4200), 0.25, 18, 0.05), r.uniform(0, dur - 0.3))
    return out

def pop(): t = np.arange(int(.09 * SR)) / SR; return np.sin(2 * np.pi * (500 + 900 * np.exp(-t * 40)) * t) * np.exp(-t * 45) * 0.3

# ------------------------------------------------------------------ Zeitplan
def build(clipdir):
    secs, t = [], 0.0
    for k in range(7):
        x = read_wav(os.path.join(clipdir, f"s{k}.wav"))
        vs = 0.05 if k == 0 else t + GAP; ve = vs + len(x) / SR
        secs.append({"k": k, "x": x, "vs": vs, "ve": ve, "words": word_times(x, TEXTS[k], vs)}); t = ve
    for k, s in enumerate(secs):
        s["t0"] = 0.0 if k == 0 else s["vs"] - 0.12
    for k, s in enumerate(secs):
        s["t1"] = secs[k + 1]["t0"] if k < 6 else s["ve"] + 0.40
    return secs

def at(s, prefix, nth=0):
    hits = [w for w in s["words"] if w[0].startswith(prefix)]
    return (hits[min(nth, len(hits) - 1)][1] if hits else s["vs"]) - s["t0"]

# ------------------------------------------------------------------ Szenen
def headline(fr, a=1.0):
    over(fr, txt("WASSER BRICHT", 104, WHITE, 9, (5, 15, 35)), W / 2, 255, a)
    over(fr, txt("DIE REGELN!", 128, YEL, 10, (5, 15, 35)), W / 2, 385, a)

def glass_scene(fr, e, ice=True):
    gx, top, bot, tw, bw = 540, 560, 1260, 300, 225
    G = [(gx - tw, top), (gx + tw, top), (gx + bw, bot), (gx - bw, bot)]
    poly(fr, G, (200, 230, 255), 0.07)
    wl = 790
    def half(y): return tw + (bw - tw) * (y - top) / (bot - top)
    surf = [(gx - half(wl) + 10 + i * (2 * half(wl) - 20) / 40, wl + 7 * math.sin(e * 2.4 + i * 0.5)) for i in range(41)]
    WP = surf + [(gx + bw - 10, bot - 14), (gx - bw + 10, bot - 14)]
    poly(fr, WP, WATER, 0.80)
    for i in range(7):                                            # Bläschen
        ph = (e * 0.35 + i * 0.137) % 1; bx = gx - 150 + i * 50 + 8 * math.sin(e * 3 + i); by = bot - 40 - ph * (bot - wl - 80)
        over(fr, ball(5 + i % 3 * 2, (190, 230, 255)), bx, by, 0.6 * (1 - ph))
    if ice:
        s = 250; cy = wl + s / 2 - 30 + 6 * math.sin(e * 2.4 + 2); ang = 0.06 * math.sin(e * 1.7)
        C = rot(rrect(gx - s / 2, cy - s / 2, gx + s / 2, cy + s / 2, 30), gx, cy, ang)
        poly(fr, C, ICE, 0.95)
        segs(fr, [rot([(gx - s / 2 + 34, cy - s / 2 + 40), (gx - s / 2 + 34, cy + 40)], gx, cy, ang),
                  rot([(gx - s / 2 + 40, cy - s / 2 + 34), (gx + 30, cy - s / 2 + 34)], gx, cy, ang)], (255, 255, 255), 10, 0.9)
        lines(fr, C, (140, 200, 240), 5, 0.9, True)
        # Unterwasser-Teil leicht einfärben
        sub = [p for p in C]; clip = np.array([(0, wl + 4), (W, wl + 4), (W, bot), (0, bot)], np.float32)
        m1 = np.zeros((H, W), np.uint8); cv2.fillPoly(m1, [np.int32(sub)], 255); m2 = np.zeros((H, W), np.uint8); cv2.fillPoly(m2, [np.int32(clip)], 255)
        m = cv2.GaussianBlur(cv2.bitwise_and(m1, m2), (0, 0), 1.2)
        ys, xs = np.nonzero(m)
        if len(ys):
            y0_, y1_, x0_, x1_ = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; roi = fr[y0_:y1_, x0_:x1_]
            al = m[y0_:y1_, x0_:x1_, None].astype(np.float32) / 255 * 0.38
            roi[:] = (roi * (1 - al) + np.array(WATER, np.float32) * al).astype(np.uint8)
        lines(fr, surf, (220, 240, 255), 4, 0.8)
    lines(fr, G[1:] + G[:1], (215, 238, 255), 9, 0.85)            # Glasrand
    segs(fr, [[(gx - tw + 40, top + 40), (gx - bw + 34, bot - 60)]], (255, 255, 255), 10, 0.25)
    return gx, wl

def scene0(fr, e, d, s):
    headline(fr)
    gx, wl = glass_scene(fr, e)
    a = ease((e - 0.6) / 0.3)
    label(fr, "EIS SCHWIMMT?!", 830, 640, 46, DARK, YEL, a, 0.8 + 0.2 * back((e - 0.6) / 0.3))

def stoff_box(fr, e, f):
    bx0, bx1, by0, by1 = 170, 700, 520, 1220
    poly(fr, rrect(bx0, by0, bx1, by1, 26), (255, 255, 255), 0.06); lines(fr, [(bx0, by0), (bx0, by1), (bx1, by1), (bx1, by0)], (210, 235, 255), 8, 0.8)
    rng = np.random.default_rng(4); N = 30
    base = np.c_[rng.uniform(bx0 + 50, bx1 - 50, N), rng.uniform(by0 + 60, by1 - 50, N)]
    ph = rng.uniform(0, 6.28, (N, 2)); cols, rows = 6, 5
    grid = np.array([(bx0 + 95 + (i % cols) * 68 + (34 if (i // cols) % 2 else 0), by1 - 52 - (i // cols) * 60) for i in range(N)], float)
    amp = 55 * (1 - f) + 3
    for i in range(N):
        liq = base[i] + amp * np.array([math.sin(e * 2.3 + ph[i, 0]), math.cos(e * 1.9 + ph[i, 1])])
        p = liq * (1 - f) + grid[i] * f
        over(fr, ball(27, (245, 150, 60)), p[0], p[1])
    lab = txt("NORMALER STOFF", 50, WHITE, 6, (5, 15, 35)); over(fr, lab, (bx0 + bx1) / 2, 470)
    # Thermometer
    tx, ty0, ty1 = 860, 560, 1110
    poly(fr, rrect(tx - 34, ty0 - 20, tx + 34, ty1, 34), (255, 255, 255), 0.9); poly(fr, circle_pts(tx, ty1 + 40, 62), (255, 255, 255), 0.9)
    col = tuple(int(a * (1 - f) + b * f) for a, b in zip((235, 60, 50), (60, 150, 255)))
    lvl = ty0 + 20 + (ty1 - ty0 - 40) * (0.1 + 0.75 * f)
    poly(fr, rrect(tx - 18, lvl, tx + 18, ty1 + 10, 18), col); poly(fr, circle_pts(tx, ty1 + 40, 46), col)
    for k in range(6): segs(fr, [[(tx + 34, ty0 + 30 + k * 85), (tx + 60, ty0 + 30 + k * 85)]], (255, 255, 255), 5, 0.7)
    over(fr, txt("kalt" if f > 0.5 else "warm", 44, WHITE, 5, (5, 15, 35)), tx, ty1 + 145)
    a = ease((f - 0.6) / 0.3); label(fr, "kälter  →  enger  →  dichter", W / 2, 1310, 50, DARK, YEL, a)

def drop(fr, cx, cy, R, sc=1.0, e=0.0):
    R = R * sc; pts = []
    for k in range(80):
        t = 2 * math.pi * k / 80; pts.append((cx + R * math.sin(t) * abs(math.sin(t / 2)) ** 1.0, cy - R * 1.35 * math.cos(t)))
    poly(fr, [(x + 10, y + 16) for x, y in pts], (0, 0, 0), 0.3); poly(fr, pts, (55, 155, 240)); lines(fr, pts, (25, 90, 170), 8, 0.9, True)
    poly(fr, rot([(cx - R * 0.55 + R * 0.18 * math.cos(a_), cy - R * 0.2 + R * 0.36 * math.sin(a_)) for a_ in np.linspace(0, 6.28, 30)], cx - R * 0.55, cy - R * 0.2, 0.5), (255, 255, 255), 0.55)
    ey = cy + R * 0.18
    for sx in (-1, 1):                                            # Sonnenbrille
        ex = cx + sx * R * 0.34
        poly(fr, rrect(ex - R * 0.27, ey - R * 0.13, ex + R * 0.27, ey + R * 0.16, R * 0.1), (15, 15, 20))
        segs(fr, [[(ex - R * 0.17, ey - R * 0.06), (ex - R * 0.02, ey - R * 0.06)]], (255, 255, 255), 5, 0.6)
    segs(fr, [[(cx - R * 0.08, ey - R * 0.06), (cx + R * 0.08, ey - R * 0.06)]], (15, 15, 20), 9)
    lines(fr, [(cx - R * 0.18 + k * R * 0.04, ey + R * 0.5 + R * 0.08 * math.sin(k / 10 * math.pi) - k * R * 0.008) for k in range(11)], (15, 30, 60), 10)

def scene1(fr, e, d, s):
    a0, a1 = at(s, "Abkühlen") - 0.3, at(s, "dichter") + 0.3
    rb = at(s, "Doch") - 0.15; f = ease((e - a0) / (a1 - a0))
    if e < rb + 0.3:
        stoff_box(fr, e, f)
        if e > rb:
            k = (e - rb) / 0.3; fr[:] = (fr * (1 - k) + BG * k).astype(np.uint8)
    if e >= rb:
        p = (e - rb) / 0.45; drop(fr, W / 2, 900, 250, back(p), e)
        r_ = at(s, "Rebell") - 0.1
        if e > r_:
            q = (e - r_) / 0.25; sc = 1.6 - 0.6 * ease(q)
            st = txt("REBELL!", 120, WHITE, 0); h_, w_ = st.shape[:2]
            card_im = Image.new("RGBA", (w_ + 80, h_ + 40), (0, 0, 0, 0)); dd = ImageDraw.Draw(card_im)
            dd.rounded_rectangle([0, 0, w_ + 79, h_ + 39], 30, fill=RED + (255,), outline=WHITE + (255,), width=8)
            card_im.alpha_composite(Image.fromarray(st), (40, 20)); arr = np.asarray(card_im.rotate(-8, expand=True, resample=Image.BICUBIC))
            over(fr, arr, W / 2, 1290, clamp01(q * 3), sc)

def scene2(fr, e, d, s):
    cx, cw, y0, y100, yb = 540, 330, 520, 720, 1240
    yv = lambda v: yb - (yb - y100) * v / 100
    fz0 = at(s, "gefriert") - 0.1; fz = ease((e - fz0) / 1.4)
    ex0 = at(s, "dehnt") - 0.1; ex1 = at(s, "Prozent") + 0.1; ex = ease((e - ex0) / max(0.4, ex1 - ex0))
    level = yv(100 + 9 * ex)
    col = tuple(int(a * (1 - fz) + b * fz) for a, b in zip(WATER, (190, 230, 252)))
    wob = 5 * math.sin(e * 3) * (1 - fz)
    body = [(cx - cw / 2 + 10, level + wob), (cx + cw / 2 - 10, level - wob), (cx + cw / 2 - 10, yb - 12), (cx - cw / 2 + 10, yb - 12)]
    poly(fr, rrect(cx - cw / 2, y0, cx + cw / 2, yb, 24), (255, 255, 255), 0.06)
    poly(fr, body, col, 0.92)
    if fz > 0.05:                                                 # Kristall-Risse
        rng = np.random.default_rng(2); cr = []
        for k in range(14):
            px, py = rng.uniform(cx - cw / 2 + 30, cx + cw / 2 - 30), rng.uniform(level + 30, yb - 30); a_ = rng.uniform(0, 6.28); L = rng.uniform(30, 70)
            cr.append([(px, py), (px + L * math.cos(a_), py + L * math.sin(a_))]); cr.append([(px, py), (px + L * .6 * math.cos(a_ + 1.2), py + L * .6 * math.sin(a_ + 1.2))])
        segs(fr, cr, (255, 255, 255), 4, 0.55 * fz)
        poly(fr, rrect(cx - cw / 2 + 24, level + 18, cx - cw / 2 + 48, yb - 40, 12), (255, 255, 255), 0.4 * fz)
    lines(fr, [(cx - cw / 2, y0), (cx - cw / 2, yb), (cx + cw / 2, yb), (cx + cw / 2, y0)], (215, 238, 255), 9, 0.9)
    for v in range(0, 121, 10):
        yy = yv(v); segs(fr, [[(cx - cw / 2, yy), (cx - cw / 2 + (36 if v % 50 == 0 else 20), yy)]], (215, 238, 255), 4, 0.8)
    segs(fr, dashed((cx - cw / 2 - 150, yv(100)), (cx + cw / 2 + 20, yv(100))), WHITE, 5, 0.85)
    over(fr, txt("100", 46, WHITE, 5, (5, 15, 35)), cx - cw / 2 - 30, yv(100) - 34, 1, 1, "r")
    if ex > 0.02:
        segs(fr, dashed((cx - cw / 2 - 20, level), (cx + cw / 2 + 150, level)), YEL, 6, ex)
        over(fr, txt(f"{100 + 9 * ex:.0f}", 46, YEL, 5, (5, 15, 35)), cx + cw / 2 + 30, level - 34, ex, 1, "l")
    ph = clamp01((e - fz0) / 1.6)
    if 0 < ph < 1:                                                # Glitzern beim Gefrieren
        for k in range(10):
            a_ = k * 2.4 + e * 2; rr = 220 + 60 * math.sin(k * 1.3)
            st = emoji("✨", 60); over(fr, st, cx + rr * math.cos(a_), 880 + rr * 1.3 * math.sin(a_), math.sin(math.pi * ph))
    lab = "WASSER" if fz < 0.5 else "EIS"; over(fr, txt(lab, 62, WHITE, 7, (5, 15, 35)), cx, 455)
    nb = at(s, "9") - 0.05
    if e > nb:
        q = (e - nb) / 0.35; label(fr, "+9 %", 870, 600, 96, WHITE, RED, clamp01(q * 3), back(q))
        label(fr, "mehr Volumen", 870, 730, 40, DARK, YEL, ease((e - nb - 0.3) / 0.3))

# --- Moleküle / Gitter
L_ = 118
def honeycomb():
    pts, edges, hexc = [], set(), []
    def key(p): return (round(p[0] / 4), round(p[1] / 4))
    idx = {}
    for i in range(-1, 9):
        for j in range(-1, 9):
            cxh = 150 + i * 1.5 * L_; cyh = 470 + j * math.sqrt(3) * L_ + (i % 2) * math.sqrt(3) / 2 * L_
            vs = [(cxh + L_ * math.cos(math.radians(60 * k)), cyh + L_ * math.sin(math.radians(60 * k))) for k in range(6)]
            inside = [100 < x < 980 and 470 < y < 1250 for x, y in vs]
            if all(inside): hexc.append((cxh, cyh))
            for k in range(6):
                for v in (vs[k], vs[(k + 1) % 6]):
                    if 100 < v[0] < 980 and 470 < v[1] < 1250 and key(v) not in idx: idx[key(v)] = len(pts); pts.append(v)
                a, b = vs[k], vs[(k + 1) % 6]
                if key(a) in idx and key(b) in idx: edges.add(tuple(sorted((idx[key(a)], idx[key(b)]))))
    return np.array(pts), sorted(edges), hexc
LAT, EDGES, HEXC = honeycomb()
NB = {i: [] for i in range(len(LAT))}
for a, b in EDGES: NB[a].append(b); NB[b].append(a)
NM = len(LAT); _r = np.random.default_rng(21)
LIQ = np.c_[_r.uniform(130, 950, NM), _r.uniform(500, 1220, NM)]
ORDER = np.argsort(LIQ[:, 1] * 3 + LIQ[:, 0]); LORD = np.argsort(LAT[:, 1] * 3 + LAT[:, 0])
ASSIGN = np.empty(NM, int); ASSIGN[ORDER] = LORD                     # Molekül i -> Gitterplatz
PH = _r.uniform(0, 6.28, (NM, 4))
def lat_h(j):
    nbs = NB[j]; dirs = []
    for b in nbs[:2]: v = LAT[b] - LAT[j]; dirs.append(v / np.linalg.norm(v))
    while len(dirs) < 2:
        base = dirs[0] if dirs else np.array([1.0, 0]); a = math.atan2(base[1], base[0]) + math.radians(120); dirs.append(np.array([math.cos(a), math.sin(a)]))
    return dirs

def molecules(fr, e, f, bonds_a, liquid_bonds=True, jig=1.0):
    P = np.zeros((NM, 2)); Hs = []
    for i in range(NM):
        j = ASSIGN[i]
        liq = LIQ[i] + 55 * np.array([math.sin(e * 1.6 + PH[i, 0]), math.cos(e * 1.3 + PH[i, 1])])
        lat = LAT[j] + jig * 2.5 * np.array([math.sin(e * 9 + PH[i, 2]), math.cos(e * 8 + PH[i, 3])])
        P[i] = liq * (1 - f) + lat * f
        a0 = e * 1.1 + PH[i, 2] * 3; ld = [np.array([math.cos(a0 + s_ * 0.91), math.sin(a0 + s_ * 0.91)]) for s_ in (-1, 1)]
        hd = lat_h(j); dd = [ld[k] * (1 - f) + hd[k] * f for k in range(2)]
        Hs.append([P[i] + 44 * v / (np.linalg.norm(v) + 1e-6) for v in dd])
    if liquid_bonds and f < 0.9:
        D = np.linalg.norm(P[:, None] - P[None], axis=2); sl = []
        for a, b in zip(*np.nonzero(np.triu((D < 150) & (D > 60)))): sl += dashed(P[a], P[b], 12, 12)
        segs(fr, sl, YEL, 4, 0.45 * (1 - f) * bonds_a[1])
    if bonds_a[0] > 0:
        sl = []
        for a, b in EDGES: sl += dashed(LAT[a], LAT[b], 14, 10)
        Pm = {ASSIGN[i]: P[i] for i in range(NM)}
        sl = []
        for a, b in EDGES: sl += dashed(Pm[a], Pm[b], 14, 10)
        segs(fr, sl, YEL, 5, 0.85 * bonds_a[0])
    for i in range(NM):
        for hp in Hs[i]:
            segs(fr, [[P[i], hp]], (235, 235, 245), 8, 0.9)
    for i in range(NM):
        for hp in Hs[i]: over(fr, ball(15, (245, 245, 250)), hp[0], hp[1])
        over(fr, ball(27, (228, 60, 60)), P[i][0], P[i][1])
    return P

def legend(fr, a=1.0):
    card(fr, 60, 1280, 1020, 1360, (8, 25, 55), 0.75 * a, 40, False)
    over(fr, ball(22, (228, 60, 60)), 110, 1320, a); over(fr, txt("Sauerstoff", 38, WHITE), 145, 1320, a, 1, "l")
    over(fr, ball(13, (245, 245, 250)), 430, 1320, a); over(fr, txt("Wasserstoff", 38, WHITE), 455, 1320, a, 1, "l")
    segs(fr, dashed((750, 1320), (810, 1320), 12, 9), YEL, 5, a); over(fr, txt("Brücke", 38, WHITE), 825, 1320, a, 1, "l")

def scene3(fr, e, d, s):
    g0 = at(s, "Doch") + 0.1; f = ease((e - g0) / 1.3)
    molecules(fr, e, f, (ease((e - g0 - 1.0) / 0.5), 1.0))
    legend(fr)
    over(fr, txt("WASSERSTOFFBRÜCKEN", 64, YEL, 7, (5, 15, 35)), W / 2, 440, ease((e - 0.1) / 0.3))
    gt = at(s, "sechs") - 0.1
    if e > gt and HEXC:
        q = ease((e - gt) / 0.4); hc = HEXC[len(HEXC) // 2 - 1]
        hx = [(hc[0] + L_ * math.cos(math.radians(60 * k)), hc[1] + L_ * math.sin(math.radians(60 * k))) for k in range(6)]
        lines(fr, hx, (90, 255, 170), 14, 0.9 * q, True)
        label(fr, "SECHSECK", hc[0], hc[1], 40, DARK, (90, 255, 170), q, 0.6 + 0.4 * back((e - gt) / 0.3))

def balance(fr, e, ph):
    cx, by = 540, 700; tilt = 0.10 * math.exp(-ph * 3) * math.sin(ph * 9)
    poly(fr, [(cx - 22, by), (cx + 22, by), (cx + 60, 1240), (cx - 60, 1240)], (190, 205, 225), 0.95)
    poly(fr, rrect(cx - 200, 1230, cx + 200, 1270, 18), (190, 205, 225), 0.95)
    L = 320; p1 = (cx - L * math.cos(tilt), by - L * math.sin(tilt)); p2 = (cx + L * math.cos(tilt), by + L * math.sin(tilt))
    segs(fr, [[p1, p2]], (225, 235, 250), 20); over(fr, ball(26, (240, 200, 70)), cx, by)
    out = []
    for (px, py), side in ((p1, 0), (p2, 1)):
        pan_y = py + 330
        segs(fr, [[(px, py), (px - 120, pan_y)], [(px, py), (px + 120, pan_y)]], (200, 210, 230), 4, 0.9)
        poly(fr, [(px - 165, pan_y), (px + 165, pan_y), (px + 130, pan_y + 34), (px - 130, pan_y + 34)], (200, 210, 230))
        sz = 200 if side == 0 else 230
        col = WATER if side == 0 else ICE
        poly(fr, rrect(px - sz / 2, pan_y - sz, px + sz / 2, pan_y - 2, 18), col, 0.95)
        lines(fr, rrect(px - sz / 2, pan_y - sz, px + sz / 2, pan_y - 2, 18), (25, 90, 170) if side == 0 else (120, 180, 230), 6, 0.9, True)
        if side == 1:
            for hx in range(3): poly(fr, circle_pts(px - 55 + hx * 55, pan_y - sz / 2 + (hx % 2) * 30 - 15, 16, 6), (150, 200, 240), 0.8)
        out.append((px, pan_y, sz))
    return out

def scene4(fr, e, d, s):
    pb = at(s, "Es") - 0.2; pc = at(s, "Mehr") - 0.2
    if e < pb + 0.3:
        molecules(fr, e + 30, 1.0, (1.0, 0.0), False, 0.6)
        hq = at(s, "Hohl") - 0.2
        for hc in HEXC:
            q = ease((e - hq) / 0.4); pul = 1 + 0.08 * math.sin(e * 6)
            poly(fr, circle_pts(hc[0], hc[1], 58 * pul), (120, 255, 230), 0.35 * q)
        label(fr, "VIELE HOHLRÄUME", W / 2, 440, 54, DARK, (120, 255, 230), ease((e - hq) / 0.3), 0.7 + 0.3 * back((e - hq) / 0.3))
        if e > pb: k = (e - pb) / 0.3; fr[:] = (fr * (1 - k) + BG * k).astype(np.uint8)
    elif e < pc + 0.3:
        pans = balance(fr, e, e - pb)
        for (px, py, sz), nm, vol in zip(pans, ("Wasser", "Eis"), ("1,00 L", "1,09 L")):
            over(fr, txt(nm, 38, DARK), px, py - sz / 2 - 26); over(fr, txt(vol, 40, DARK, wt="Bold"), px, py - sz / 2 + 26)
            over(fr, txt("1 kg", 54, YEL, 6, (5, 15, 35)), px, py + 90)
        mq = at(s, "Masse") - 0.2; label(fr, "GLEICHE MASSE", W / 2, 440, 56, DARK, YEL, ease((e - mq) / 0.3), 0.7 + 0.3 * back((e - mq) / 0.3))
        if e > pc: k = (e - pc) / 0.3; fr[:] = (fr * (1 - k) + BG * k).astype(np.uint8)
    else:
        q = ease((e - pc - 0.2) / 0.35)
        card(fr, 70, 470, 1010, 760, (255, 255, 255), q)
        over(fr, txt("DICHTE =", 78, DARK), W / 2, 545, q)
        over(fr, txt("MASSE ÷ VOLUMEN", 70, (30, 110, 210)), W / 2, 670, q)
        er = at(s, "Eis") - 0.2; q2 = ease((e - er) / 0.5)
        for k, (nm, val, v, col) in enumerate((("Wasser", "1,00 g/cm³", 1.0, WATER), ("Eis", "0,92 g/cm³", 0.917, ICE))):
            y = 900 + k * 190; over(fr, txt(nm, 52, WHITE, 6, (5, 15, 35)), 90, y - 62, q2, 1, "l")
            bw = 900 * v * (0.3 + 0.7 * q2)
            poly(fr, rrect(90, y - 20, 90 + bw, y + 60, 30), col, q2); over(fr, txt(val, 44, DARK), 90 + bw - 24, y + 20, q2, 1, "r")
        a2 = ease((e - er - 0.6) / 0.3); label(fr, "Eis ist weniger dicht", W / 2, 1300, 52, WHITE, (30, 110, 210), a2)

def lake(fr, e, mode, g=0.0, alt=False):
    """mode 0: echter See mit Eisdecke; alt=True: Gedankenspiel, Eis sinkt und See friert von unten (g = 0..1)."""
    x0, x1, sky, top, bot = 60, 1020, 470, 620, 1220
    poly(fr, rrect(x0, sky, x1, bot + 50, 36), (150, 200, 240), 0.25)
    wy = top + (0 if not alt else -10)
    n = 50; yy = np.linspace(0, 1, n)
    for k in range(n - 1):
        y_a, y_b = wy + (bot - wy) * yy[k], wy + (bot - wy) * yy[k + 1] + 1
        c = tuple(int(a * (1 - yy[k]) + b * yy[k]) for a, b in zip((50, 150, 230), (12, 50, 120)))
        poly(fr, [(x0, y_a), (x1, y_a), (x1, y_b), (x0, y_b)], c, 0.95)
    gnd = [(x0 + i * (x1 - x0) / 30, bot + 10 * math.sin(i * 1.3)) for i in range(31)] + [(x1, bot + 50), (x0, bot + 50)]
    poly(fr, gnd, (110, 80, 50))
    if not alt:
        ice = [(x0, wy - 18), (x1, wy - 18)] + [(x1 - i * (x1 - x0) / 24, wy + 62 + 10 * math.sin(i * 2.1)) for i in range(25)]
        poly(fr, ice, ICE, 0.97); lines(fr, ice, (130, 190, 235), 5, 0.9, True)
        over(fr, txt("EIS · 0 °C", 46, DARK), W / 2, wy + 22)
        over(fr, txt("ca. 4 °C", 46, WHITE, 6, (5, 15, 35)), 880, bot - 50)
        for k in range(3):
            fx = 540 + 330 * math.sin(e * 0.5 + k * 2.1); fy = 820 + k * 120 + 20 * math.sin(e * 1.5 + k)
            over(fr, emoji("🐟", 110, math.cos(e * 0.5 + k * 2.1) < 0), fx, fy)
    else:
        rng = np.random.default_rng(6); fill_top = bot - (bot - 760) * g
        for k in range(9):                                  # sinkende Eisbrocken
            t0 = k * 0.12; q = ease((e - t0) / 1.3) if g == 0 else 1
            bx = 150 + k * 95 + rng.uniform(-20, 20); by = wy + 30 + (bot - 80 - wy - 30 - (k % 3) * 70) * q
            if g == 0 or by < fill_top: poly(fr, rot(rrect(bx - 45, by - 40, bx + 45, by + 40, 12), bx, by, 0.4 * k), ICE, 0.95)
        if g > 0:
            pts = [(x0, bot + 20), (x1, bot + 20)] + [(x1 - i * (x1 - x0) / 24, fill_top + 12 * math.sin(i * 1.7 + e)) for i in range(25)]
            poly(fr, pts, ICE, 0.97); lines(fr, pts, (130, 190, 235), 5, 0.9, True)
        fy = min(fill_top - 70, 800); fx = 540 + 160 * math.sin(e * 2)
        over(fr, emoji("🐟", 100, math.cos(e * 2) < 0), fx, fy)

def scene5(fr, e, d, s):
    wa = at(s, "Wäre") - 0.2
    if e < wa + 0.3:
        lake(fr, e, 0)
        q = (e - 0.2) / 0.35; label(fr, "EIS SCHWIMMT OBEN!", W / 2, 440, 52, WHITE, (22, 150, 70), clamp01(q * 3), back(q))
        if e > wa: k = (e - wa) / 0.3; fr[:] = (fr * (1 - k) + BG * k).astype(np.uint8)
    else:
        su = at(s, "Und") - 0.1; g = ease((e - su) / (d - (su) - 0.2))
        lake(fr, e - wa, 0, g if e > su else 0.0, alt=True)
        poly(fr, rrect(60, 470, 1020, 1270, 36), (200, 40, 40), 0.10)
        label(fr, "WAS WÄRE, WENN …?", W / 2, 440, 54, WHITE, RED, 1.0)
        if e > su: label(fr, "friert von unten zu", W / 2, 1310, 50, DARK, YEL, ease((e - su) / 0.3))

def sub_button(fr, e, t_click):
    q = (e - (t_click - 0.9)) / 0.35
    if q <= 0: return
    clicked = e >= t_click; sc = back(q) * (0.92 if 0 < e - t_click < 0.12 else 1.0)
    bw, bh, cy = 600, 140, 1000
    col = (60, 60, 66) if clicked else (230, 33, 23)
    card(fr, W / 2 - bw / 2 * sc, cy - bh / 2 * sc, W / 2 + bw / 2 * sc, cy + bh / 2 * sc, col, clamp01(q * 3), bh / 2 * sc)
    over(fr, txt("ABONNIERT" if clicked else "ABONNIEREN", 62, WHITE), W / 2 + (30 if clicked else 0) * sc, cy, clamp01(q * 3), sc)
    if clicked:
        over(fr, emoji("🔔", 70), W / 2 - 215 * sc, cy, 1, 1 + 0.25 * math.sin(min(1, (e - t_click) / 0.4) * math.pi * 3) * max(0, 1 - (e - t_click)))
    hx0, hy0 = W / 2 + 330, cy + 380; hx1, hy1 = W / 2 + 150, cy + 50
    k = ease((e - (t_click - 0.6)) / 0.5)
    if e < t_click + 0.6:
        over(fr, emoji("👆", 130), hx0 + (hx1 - hx0) * k, hy0 + (hy1 - hy0) * k + 40, clamp01(q * 2) * clamp01((t_click + 0.6 - e) / 0.2))

def scene6(fr, e, d, s):
    hq = at(s, "Hättest") - 0.2
    if e < hq + 0.3:
        lake(fr, e + 10, 0)
        label(fr, "EIS = SCHUTZDECKE", W / 2, 440, 56, DARK, YEL, ease((e - 0.1) / 0.3), 0.7 + 0.3 * back((e - 0.1) / 0.3))
        if e > hq: k = (e - hq) / 0.3; fr[:] = (fr * (1 - k) + BG * k).astype(np.uint8)
    else:
        q = (e - hq) / 0.4
        card(fr, 90, 520, 990, 800, (255, 255, 255), clamp01(q * 3))
        over(fr, txt("Hättest du's", 76, DARK), W / 2, 610, clamp01(q * 3), back(q))
        over(fr, txt("gedacht?", 76, DARK), W / 2, 705, clamp01(q * 3), back(q))
        over(fr, emoji("🤔", 120), 930, 530, clamp01(q * 3), back(q))
        cm = at(s, "Schreib") - 0.2
        if e > cm:
            q2 = (e - cm) / 0.35
            lw = fnt(48).getlength("Schreib's in die Kommentare") + 68
            label(fr, "Schreib's in die Kommentare", W / 2 - 50, 1230, 48, DARK, YEL, clamp01(q2 * 3), back(q2))
            over(fr, emoji("👇", 80), W / 2 - 50 + lw / 2 + 55, 1230, clamp01(q2 * 3), back(q2))
        sub_button(fr, e, at(s, "abonnier") + 0.35)

SCENES = [scene0, scene1, scene2, scene3, scene4, scene5, scene6]

# ------------------------------------------------------------------ Untertitel
def chunks(words):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 4 or w[0][-1] in ".,!?:" or sum(len(x[0]) + 1 for x in cur) > 24: out.append(cur); cur = []
    if cur: out.append(cur)
    return out

def caption(fr, t, secs):
    for s in secs:
        if s["vs"] - 0.05 <= t <= s["ve"] + 0.15:
            for c in s["chunks"]:
                if c[0][1] - 0.08 <= t < c[-1][2] + 0.12 or (c is s["chunks"][-1] and t >= c[0][1]):
                    draw_chunk(fr, c, t); return

def draw_chunk(fr, c, t):
    f = fnt(76); sp = f.getlength(" "); ws = [w for w, _, _ in c]
    lines_, cur = [], []
    for w in c:
        if cur and f.getlength(" ".join(x[0] for x in cur + [w])) > 940: lines_.append(cur); cur = []
        cur.append(w)
    lines_.append(cur)
    y = 1500 - (len(lines_) - 1) * 46
    k = clamp01((t - c[0][1] + 0.08) / 0.12); sc = 0.9 + 0.1 * ease(k)
    for ln in lines_:
        tw = sum(f.getlength(w[0]) for w in ln) + sp * (len(ln) - 1); x = W / 2 - tw / 2 * sc
        for w, a, b in ln:
            active = a - 0.03 <= t
            im = txt(w, 76, YEL if (active and t < b + 0.05) else WHITE, 9, (5, 12, 28))
            over(fr, im, x - 21 * sc, y, 1.0, sc, "l"); x += (f.getlength(w) + sp) * sc
        y += 92

# ------------------------------------------------------------------ Rendern
BG = None
def render_frame(t, secs):
    fr = BG.copy(); snow(fr, t)
    s = next((x for x in secs if x["t0"] <= t < x["t1"]), secs[-1]); k = s["k"]; e = t - s["t0"]; d = s["t1"] - s["t0"]
    SCENES[k](fr, e, d, s)
    if k > 0 and e < 0.22:                                        # weiche Überblendung
        pv = secs[k - 1]; g = BG.copy(); snow(g, t); SCENES[k - 1](g, pv["t1"] - pv["t0"] - 0.001, pv["t1"] - pv["t0"], pv)
        a = ease(e / 0.22); fr = (fr * a + g * (1 - a)).astype(np.uint8)
    if CHIPS[k]: label(fr, CHIPS[k], W / 2, 150, 44, DARK, (255, 255, 255), 0.95)
    caption(fr, t, secs)
    wipe0 = secs[-1]["t1"] - 0.38                                 # Loop-Wisch zurück zum Anfang
    if t >= wipe0:
        p = ease((t - wipe0) / 0.36); g = BG.copy(); snow(g, 0.0); scene0(g, 0.0, 1, secs[0]); dx = int(W * p)
        if dx > 0: out = fr.copy(); out[:, :W - dx] = fr[:, dx:]; out[:, W - dx:] = g[:, :dx]; fr = out
    return fr

def main():
    global BG
    clipdir, out = sys.argv[1], sys.argv[2]
    secs = build(clipdir)
    for s in secs: s["chunks"] = chunks(s["words"])
    BG = make_bg(); total = secs[-1]["t1"]
    if "--still" in sys.argv:
        ts = [float(x) for x in sys.argv[sys.argv.index("--still") + 1].split(",")]
        for t in ts: Image.fromarray(render_frame(t, secs)).save(f"{os.path.splitext(out)[0]}_{t:05.2f}.png")
        for s in secs: print(s["k"], f"{s['t0']:.2f}-{s['t1']:.2f}", [(w, round(a, 2)) for w, a, _ in s["words"]][:40])
        return
    nfr = int(round(total * FPS)); silent = out + ".stumm.mp4"
    if not os.path.exists(silent):
      p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
      for i in range(nfr):
        p.stdin.write(render_frame(i / FPS, secs).tobytes())
        if i % 300 == 0: print(f"{i}/{nfr}", flush=True)
      p.stdin.close(); p.wait()
    total = nfr / FPS
    N = int(total * SR); voice = np.zeros(N + SR); sf = np.zeros(N + SR)
    for s in secs: add(voice, s["x"], s["vs"])
    voice = voice[:N]
    for s in secs[1:]: add(sf, whoosh(0.4, 0.12), s["t0"] - 0.15)
    s2 = secs[2]; add(sf, sparkle(1.4), s2["t0"] + at(s2, "gefriert"))
    add(sf, pop() * 1.2, s2["t0"] + at(s2, "9"))
    s3 = secs[3]; g0 = s3["t0"] + at(s3, "Doch") + 0.1
    for k in range(6): add(sf, pop() * 0.6, g0 + 0.2 + k * 0.17)
    s1 = secs[1]; add(sf, pop() * 1.3, s1["t0"] + at(s1, "Rebell") - 0.1)
    s6 = secs[6]; add(sf, bing() * 1.2, s6["t0"] + at(s6, "abonnier") + 0.35)
    add(sf, pop(), s6["t0"] + at(s6, "abonnier") + 0.33)
    add(sf, whoosh(0.4, 0.12), total - 0.42)
    ev = cv2.GaussianBlur(np.abs(voice).astype(np.float32).reshape(1, -1), (0, 0), sigmaX=SR * 0.08, sigmaY=0.01).ravel()
    duck = 1 - 0.5 * np.clip(ev / (ev.max() + 1e-9) * 3, 0, 1)
    mus = music(total)[:N]
    mix = voice * 0.95 + mus * 0.30 * duck + sf[:N] * 0.8
    fi = int(0.015 * SR); mix[-fi:] *= np.linspace(1, 0, fi)
    mix = np.clip(mix / max(1, np.abs(mix).max() / 0.95), -1, 1)
    aw = out + ".mix.wav"
    with wave.open(aw, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(np.repeat((mix * 32767).astype(np.int16)[:, None], 2, axis=1).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", aw, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5",
                    "-ar", "44100", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
    os.remove(silent); os.remove(aw)
    with open(os.path.splitext(out)[0] + "_zeiten.txt", "w", encoding="utf-8") as f:
        for s in secs: f.write(f"{s['t0']:05.2f}–{s['t1']:05.2f} s  Abschnitt {s['k']}: {TEXTS[s['k']]}\n")
    print(f"Fertig: {out} ({total:.2f} s)")

if __name__ == "__main__":
    main()
