#!/usr/bin/env python3
"""
schatten_quiz.py – Quizy4 "Schatten-Quiz" Short (1080x1920, 30 fps).
Ablauf je Frage: Silhouette (oder mit "schatten": false farbiges Bild, "bild_aufl" = Bild nach Auflösung; "chip" = Text statt SCHATTEN) im Spotlight + Frage + A/B/C sofort sichtbar, Stimme liest Frage,
Countdown 3-2-1 (Ticken), dann Enthüllung: Schatten -> farbiges Tier (Blitz), richtige Antwort grün,
Hand hakt ab (Ding), Stimme nennt Antwort. Frage 3 = "DIE SCHWERSTE!". Outro: Kommentar- + Abo-Aufruf,
Abo-Button mit Bing, dann wischt Frage 1 herein (Loop).
Aufruf: python3 schatten_quiz.py quiz.json out.mp4 --stimme el_ordner [--tempo 1.1 --tempo-aufl 1.2 --denkzeit 2.4]
Stimme: q0..q2.mp3, r0..r2.mp3, outro.mp3. Emojis/Bilder: emoji/<code>.png (quadratisch, 512 px).
farben.deko: "musik" | "koerper" | "flaggen" | sonst Tier-Skizzen.
"""
import sys, os, math, json, subprocess, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SR = 1080, 1920, 30, 44100
HERE = os.path.dirname(os.path.abspath(__file__)); EMO = os.path.join(HERE, "emoji")
WORK = os.path.join(HERE, "work_tmp"); os.makedirs(WORK, exist_ok=True)
GREEN, ORANGE, RED, DARK, YEL = (34, 197, 94), (255, 138, 0), (230, 40, 50), (28, 32, 40), (255, 214, 0)
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
def fnt(s): return ImageFont.truetype(FONT, s)
def emoji(code, s): return Image.open(os.path.join(EMO, code + ".png")).convert("RGBA").resize((s, s), Image.LANCZOS)
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
    if scale != 1.0:
        h0, w0 = rgba.shape[:2]; rgba = cv2.resize(rgba, (max(1, int(w0 * scale)), max(1, int(h0 * scale))), interpolation=cv2.INTER_LINEAR)
        x += (w0 - rgba.shape[1]) // 2; y += (h0 - rgba.shape[0]) // 2
    h, w = rgba.shape[:2]; x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0: return
    s = rgba[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32); a = s[..., 3:4] / 255 * alpha
    fr[y0:y1, x0:x1] = fr[y0:y1, x0:x1] * (1 - a) + s[..., :3] * a
A_ = lambda im: np.asarray(im.convert("RGBA"))

# ------------------------------------------------------------------ Hintergrund mit Skizzen
def doodles(d, rng, col):
    def paw(x, y, s, r):
        c, sn = math.cos(r), math.sin(r)
        P = lambda dx, dy: (x + (dx * c - dy * sn) * s, y + (dx * sn + dy * c) * s)
        cx, cy = P(0, 0.35); d.ellipse([cx - .42 * s, cy - .34 * s, cx + .42 * s, cy + .34 * s], outline=col, width=5)
        for dx, dy in ((-.55, -.25), (-.2, -.6), (.2, -.6), (.55, -.25)):
            px, py = P(dx, dy); d.ellipse([px - .16 * s, py - .2 * s, px + .16 * s, py + .2 * s], outline=col, width=5)
    def star(x, y, s):
        d.line([(x - s, y), (x + s, y)], fill=col, width=5); d.line([(x, y - s), (x, y + s)], fill=col, width=5)
    for x, y, s, r in ((95, 560, 55, -.4), (985, 640, 50, .5), (90, 1120, 45, .3), (990, 1100, 52, -.3)): paw(x, y, s, r)
    for x, y in ((60, 300), (1020, 330), (980, 1500), (70, 1520)): star(x, y, 16)

def doodles_flaggen(d, rng, col):
    def flag(x, y, s, r):          # Fahnenmast mit wehender Flagge (handgezeichnet)
        c, sn = math.cos(r), math.sin(r); P = lambda dx, dy: (x + (dx * c - dy * sn) * s, y + (dx * sn + dy * c) * s)
        d.line([P(0, 1.2), P(0, -1.0)], fill=col, width=6); d.ellipse([P(0, -1.08)[0] - 7, P(0, -1.08)[1] - 7, P(0, -1.08)[0] + 7, P(0, -1.08)[1] + 7], fill=col)
        top = [P(t * 1.1, -0.95 + 0.08 * math.sin(t * 6)) for t in np.linspace(0, 1, 14)]
        bot = [P(t * 1.1, -0.25 + 0.08 * math.sin(t * 6)) for t in np.linspace(1, 0, 14)]
        d.line(top + bot + [top[0]], fill=col, width=5, joint="curve")
        d.line([P(0, -0.6 + 0.0), P(1.1, -0.6 + 0.08 * math.sin(6))], fill=col, width=3)
    def star5(x, y, r, rot=0):
        pts = [(x + (r if k % 2 == 0 else r * .42) * math.cos(rot - math.pi / 2 + k * math.pi / 5), y + (r if k % 2 == 0 else r * .42) * math.sin(rot - math.pi / 2 + k * math.pi / 5)) for k in range(10)]
        d.line(pts + [pts[0]], fill=col, width=5, joint="curve")
    def globe(x, y, r):
        d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=5); d.ellipse([x - r * .45, y - r, x + r * .45, y + r], outline=col, width=4)
        d.line([(x - r, y), (x + r, y)], fill=col, width=4); d.arc([x - r * .95, y - r * 1.2, x + r * .95, y - r * .1], 20, 160, fill=col, width=3)
        d.arc([x - r * .95, y + r * .1, x + r * .95, y + r * 1.2], 200, 340, fill=col, width=3)
    flag(80, 640, 70, -.15); flag(930, 700, 62, .12); flag(70, 1170, 55, .1); flag(950, 1150, 60, -.1)
    globe(130, 1800, 70); globe(960, 1810, 60)
    for x, y, r in ((60, 300, 22), (1020, 330, 22), (990, 1520, 26), (80, 1520, 22), (1010, 920, 16), (60, 900, 16)): star5(x, y, r, rng.uniform(-.3, .3))

def background(cfg):
    y = np.linspace(0, 1, H)[:, None, None]; x = np.linspace(-1, 1, W)[None, :, None]
    g = np.array(cfg["oben"], np.float32) * (1 - y) + np.array(cfg["unten"], np.float32) * y
    g = g * (1 - 0.3 * (x ** 2 * 0.7))
    im = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert("RGBA")
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ({"flaggen": doodles_flaggen}.get(cfg.get("deko"), doodles))(ImageDraw.Draw(L), np.random.default_rng(4), (255, 255, 255, 70))
    im.alpha_composite(L); return np.asarray(im.convert("RGB")).astype(np.float32)

SPOT_C, SPOT_R = (540, 850), 400
def spotlight():
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    cx, cy = SPOT_C; r = SPOT_R
    d.ellipse([cx - r - 18, cy - r - 18, cx + r + 18, cy + r + 18], fill=(0, 0, 0, 90))
    L = L.filter(ImageFilter.GaussianBlur(18)); d = ImageDraw.Draw(L)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 246, 214, 255))
    for k, off in enumerate((0, 7)):
        pts = [(cx + (r + 4 + off) * math.cos(t) + 3 * math.sin(5 * t + k), cy + (r + 4 + off) * math.sin(t) + 3 * math.cos(4 * t + k)) for t in np.linspace(0, 2 * math.pi, 120)]
        d.line(pts + [pts[0]], fill=(40, 40, 40, 200 - 80 * k), width=6 - 2 * k, joint="curve")
    a = np.asarray(L).astype(np.float32); yy, xx = np.mgrid[0:H, 0:W]
    glow = np.exp(-(((xx - cx) ** 2 + (yy - cy + 60) ** 2) / (2 * (r * 0.75) ** 2)))[..., None]
    inside = (((xx - cx) ** 2 + (yy - cy) ** 2) < r * r)[..., None]
    a[..., :3] = np.where(inside, a[..., :3] * (0.9 + 0.1 * glow), a[..., :3])
    return a.astype(np.uint8)

def silhouette(code, s):
    e = emoji(code, s); blk = Image.new("RGBA", e.size, (22, 22, 26, 255)); blk.putalpha(e.split()[3]); return blk

# ------------------------------------------------------------------ Texte / Pillen
PX0, PX1, PY0, PH, PG = 70, 1010, 1320, 140, 30
def pill(k, ans, state):   # 0 normal, 1 richtig (grün), 2 abgedunkelt
    L = Image.new("RGBA", (PX1 - PX0 + 40, PH + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.rounded_rectangle([20, 28, PX1 - PX0 + 20, PH + 28], PH // 2, fill=(0, 0, 0, 110))
    fill = {0: (255, 255, 255, 248), 1: GREEN + (255,), 2: (255, 255, 255, 150)}[state]
    d.rounded_rectangle([20, 20, PX1 - PX0 + 20, PH + 20], PH // 2, fill=fill)
    r = PH / 2 - 14; cx, cy = 20 + 14 + r, 20 + PH / 2
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill={0: ORANGE, 1: (255, 255, 255), 2: (190, 190, 190)}[state])
    d.text((cx, cy + 3), "ABC"[k], font=fnt(66), fill=GREEN if state == 1 else "white", anchor="mm")
    fa = 78
    while fnt(fa).getlength(ans) > PX1 - PX0 - 2 * r - 200 and fa > 40: fa -= 2
    d.text((cx + r + 32, cy + 2), ans, font=fnt(fa), fill={0: DARK, 1: "white", 2: (120, 120, 120)}[state], anchor="lm")
    return A_(L)

def question_layer(i, qd, quiz, n, ohne_frage=False):
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    if i == 0:
        f = fnt(44); t = quiz["haken"]; w = f.getlength(t) + 60
        d.rounded_rectangle([W / 2 - w / 2, 60, W / 2 + w / 2, 126], 33, fill=(0, 0, 0, 170)); d.text((W / 2, 93), t, font=f, fill=YEL, anchor="mm")
    last = i == n - 1; chip = "DIE SCHWERSTE!" if last else f"{quiz.get('chip', 'SCHATTEN')} {i + 1}/{n}"
    fc = fnt(44); cw = fc.getlength(chip) + 70
    d.rounded_rectangle([W / 2 - cw / 2, 158, W / 2 + cw / 2, 224], 33, fill=RED if last else (255, 255, 255, 240))
    d.text((W / 2, 191), chip, font=fc, fill="white" if last else DARK, anchor="mm")
    f = fnt(88); lines = [] if ohne_frage else wrap(qd["frage"], f, W - 120); y = 300
    for ln in lines:
        d.text((W / 2, y), ln, font=f, fill="white", anchor="mm", stroke_width=9, stroke_fill=(10, 10, 10)); y += 100
    return A_(L)

def number_img(k):
    L = Image.new("RGBA", (220, 220), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.ellipse([10, 14, 210, 214], fill=(0, 0, 0, 110)); d.ellipse([6, 6, 206, 206], fill=RED + (255,), outline="white", width=8)
    d.text((106, 112), str(k), font=fnt(130), fill="white", anchor="mm"); return A_(L)

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

# ------------------------------------------------------------------ Hand mit Stift (vereinfachtes Sprite)
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
    a = sys.argv[1:]; opt = {"--tempo": 1.1, "--tempo-aufl": 1.2, "--denkzeit": 2.4, "--musik-pegel": 0.4}
    k = a.index("--stimme"); stimme = a[k + 1]; del a[k:k + 2]
    for o in list(opt):
        if o in a: k = a.index(o); opt[o] = float(a[k + 1]); del a[k:k + 2]
    THINK = opt["--denkzeit"]; quiz = json.load(open(a[0], encoding="utf-8")); out = a[1]; qs = quiz["fragen"]; n = len(qs)
    P = lambda nm: os.path.join(WORK, f"sq_{nm}.wav")
    QC = [prep_clip(os.path.join(stimme, f"q{i}.mp3"), P(f"q{i}"), opt["--tempo"]) for i in range(n)]
    RC = [prep_clip(os.path.join(stimme, f"r{i}.mp3"), P(f"r{i}"), opt["--tempo-aufl"]) for i in range(n)]
    OC = prep_clip(os.path.join(stimme, "outro.mp3"), P("outro"), opt["--tempo-aufl"])

    segs, t = [], 0.0
    for i in range(n):
        s = {"i": i, "t0": t, "vs": t + (0.0 if i == 0 else 0.1)}
        s["c0"] = s["vs"] + QC[i][1] + 0.05; s["c1"] = s["c0"] + THINK
        s["rev"] = s["c1"] + 0.02; s["vr"] = s["rev"] + 0.05; s["end"] = s["vr"] + RC[i][1] + 0.3
        t = s["end"]; segs.append(s)
    O = {"t0": t, "vo": t + 0.25}; O["sub"] = O["vo"] + OC[1] * 0.62; O["end"] = O["vo"] + OC[1] + 0.1; total = O["end"] + 0.3

    BG = background(quiz["farben"]); SPOT = spotlight(); SIL, COL = [], []
    for qd in qs:
        sz = qd.get("groesse", 600); SIL.append(A_(silhouette(qd["bild"], sz) if quiz.get("schatten", True) else emoji(qd["bild"], sz))); COL.append(A_(emoji(qd.get("bild_aufl", qd["bild"]), sz)))
    QL = [question_layer(i, qd, quiz, n) for i, qd in enumerate(qs)]; QL0 = [question_layer(i, qd, quiz, n, True) for i, qd in enumerate(qs)]
    def info_layer(t):
        L = Image.new("RGBA", (W, 250), (0, 0, 0, 0)); d = ImageDraw.Draw(L); f = fnt(54)
        lines = wrap(t, f, W - 200)[:2]; hh = 60 + 66 * len(lines)
        d.rounded_rectangle([50, 10, W - 50, 10 + hh], 36, fill=(0, 0, 0, 140)); d.rounded_rectangle([44, 0, W - 56, hh], 36, fill=YEL + (255,), outline=(20, 20, 20), width=5)
        L.alpha_composite(emoji("1f4a1", 64), (70, int(hh / 2 - 32)))
        y = 30 + 33
        for ln in lines: d.text((W / 2 + 40, y), ln, font=f, fill=DARK, anchor="mm"); y += 66
        return A_(L)
    INFO = [info_layer(qd["info"]) if qd.get("info") else None for qd in qs]
    PL = [[[pill(k_, ans, st) for st in (0, 1, 2)] for k_, ans in enumerate(qd["antworten"])] for qd in qs]
    NUM = {k_: number_img(k_) for k_ in (1, 2, 3)}; SPL = splash(); CH = [check_pts(qd["richtig"]) for qd in qs]
    OB = banner(*quiz["outro_banner"]); CB = banner("Wie viele hattest du?", "Schreib's in die Kommentare", "1f447"); SB = sub_button()
    ENTRY = (W + 140, H + 300)

    def q_frame(i, tt):
        s = segs[i]; e = tt - s["t0"]; fr = BG.copy(); over(fr, SPOT, 0, 0)
        qd = qs[i]; sz = SIL[i].shape[0]; cx, cy = SPOT_C; x0, y0 = cx - sz // 2, cy - sz // 2 + qd.get("dy", 0)
        breathe = 1 + 0.015 * math.sin(e * 3.2)
        rp = (tt - s["rev"]) / 0.35
        if rp <= 0: over(fr, SIL[i], x0, y0, 1, breathe)
        else:
            fl = max(0, 1 - rp / 1.2); fr[:] = fr + (255 - fr) * 0.55 * fl * (rp < 1.2)
            pop = 1 + 0.12 * math.sin(min(1, rp) * math.pi)
            over(fr, SIL[i], x0, y0, max(0, 1 - rp), pop); over(fr, COL[i], x0, y0, min(1, rp), pop)
        ip = ease((tt - s["rev"] - 0.35) / 0.25) if INFO[i] is not None and tt >= s["rev"] + 0.35 else 0
        if ip < 1: over(fr, QL[i], 0, 0, 1 - ip)
        if ip > 0: over(fr, QL0[i], 0, 0, ip); over(fr, INFO[i], 0, 262 + int((1 - ip) * 30), ip)
        for k_ in range(3):
            pt = e - (0.05 + 0.12 * k_) if i == 0 else e - (0.3 + 0.15 * k_)
            if i == 0 and tt < 0.02: pt = 1
            if pt <= 0: continue
            sc = 0.7 + 0.3 * ease(pt / 0.14); ok = k_ == qd["richtig"]
            if tt >= s["rev"] + 0.3: st = 1 if ok else 2
            else: st = 0
            bump = 1 + 0.06 * math.sin(min(1, (tt - s["rev"] - 0.3) / 0.25) * math.pi) if st == 1 else 1
            over(fr, PL[i][k_][st], PX0 - 20, PY0 + k_ * (PH + PG) - 20, min(1, pt / 0.08), sc * bump)
        if s["c0"] <= tt < s["c1"]:
            p = (tt - s["c0"]) / THINK; num = 3 - min(2, int(p * 3)); lp = (p * 3) % 1
            over(fr, NUM[num], 800, 470, 1, 1 + 0.25 * max(0, 1 - lp / 0.2))
            x0b, y0b, x1b, y1b = 70, 1830, 1010, 1862; fr[y0b:y1b, x0b:x1b] *= 0.5; wb = int((x1b - x0b - 8) * (1 - p))
            col = np.array([34, 197, 94]) if p < 0.4 else np.array([255, 190, 0]) if p < 0.75 else np.array([235, 50, 50])
            if wb > 8: fr[y0b + 4:y1b - 4, x0b + 4:x0b + 4 + wb] = col
        tk = s["rev"] + 0.3; pts = CH[i]
        if tt >= tk: draw_check(fr, pts[:max(2, int(min(1, (tt - tk) / 0.3) * (len(pts) - 1)) + 1)])
        if tk - 0.45 <= tt < tk + 0.85:
            if tt < tk: f = ease((tt - (tk - 0.45)) / 0.45); pos = (ENTRY[0] + (pts[0][0] - ENTRY[0]) * f, ENTRY[1] + (pts[0][1] - ENTRY[1]) * f)
            elif tt < tk + 0.3: pos = pts[min(len(pts) - 1, int((tt - tk) / 0.3 * (len(pts) - 1)))]
            else: f = ease((tt - tk - 0.3) / 0.55); pos = (pts[-1][0] + (ENTRY[0] - pts[-1][0]) * f, pts[-1][1] + (ENTRY[1] - pts[-1][1]) * f)
            place_hand(fr, *pos)
        if i == n - 1 and e < 0.8:
            al = min(1, e / 0.08) * min(1, (0.8 - e) / 0.15); over(fr, SPL, 0, 640, al, 1 + 0.3 * max(0, 1 - e / 0.12))
        return fr

    def outro_frame(tt):
        e = tt - O["t0"]; fr = BG.copy()
        for k_, qd in enumerate(qs):
            cx = 200 + k_ * 340; cy = 700; r = 150; p = ease((e - 0.1 * k_) / 0.3)
            if p <= 0: continue
            L = Image.new("RGBA", (340, 340), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
            d.ellipse([170 - r, 175 - r + 8, 170 + r, 175 + r + 8], fill=(0, 0, 0, 100)); d.ellipse([170 - r, 170 - r, 170 + r, 170 + r], fill=(255, 246, 214, 255), outline=(40, 40, 40), width=6)
            L.alpha_composite(emoji(qd.get("bild_aufl", qd["bild"]), 230), (55, 55)); over(fr, A_(L), cx - 170, cy - 170, p, 0.6 + 0.4 * p)
        f = fnt(80); d0 = Image.new("RGBA", (W, 200), (0, 0, 0, 0)); ImageDraw.Draw(d0).text((W / 2, 100), quiz.get("outro_titel", "Alle 3 erkannt?"), font=f, fill="white", anchor="mm", stroke_width=9, stroke_fill=(10, 10, 10))
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
        for nm, tt in (("erstes_bild", 0.0), ("countdown", segs[0]["c0"] + 0.3), ("aufloesung1", segs[0]["end"] - 0.1), ("frage2", segs[1]["c0"] - 0.2), ("aufloesung2", segs[1]["end"] - 0.1),
                       ("frage3", segs[2]["c0"] + 0.2), ("aufloesung3", segs[2]["end"] - 0.1), ("outro", O["sub"] + 0.5), ("hand", segs[1]["rev"] + 0.45), ("letztes", total - 1 / FPS)):
            Image.fromarray(np.clip(frame(tt), 0, 255).astype(np.uint8)).save(f"{pre}_{nm}.png")
        print(f"Stills ok ({total:.2f} s)"); return

    silent = os.path.join(WORK, "sq_stumm.mp4"); nfr = int(round(total * FPS))
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    for k_ in range(nfr): p.stdin.write(np.clip(frame(k_ / FPS), 0, 255).astype(np.uint8).tobytes())
    p.stdin.close(); p.wait(); total = nfr / FPS

    N = int(total * SR); voice = np.zeros(N + SR)
    for s in segs: add(voice, read_wav(QC[s["i"]][0]), s["vs"]); add(voice, read_wav(RC[s["i"]][0]), s["vr"])
    add(voice, read_wav(OC[0]), O["vo"]); voice = voice[:N]
    sf = np.zeros(N + SR); wh = whoosh()
    for s in segs:
        for k_ in range(3): add(sf, tone(1700, .07, 60, .32) + tone(850, .07, 60, .12), s["c0"] + k_ * THINK / 3)
        for k_, tt in enumerate(np.arange(s["c0"] + THINK / 6, s["c1"] - 0.05, THINK / 3)): add(sf, tone(1250, .05, 70, .18), tt)
        if s["i"] > 0: add(sf, wh * 0.8, s["t0"] - 0.05)
        if s["i"] == n - 1:
            t_ = np.arange(int(.7 * SR)) / SR; add(sf, np.sin(2 * np.pi * (40 + 60 * np.exp(-t_ * 9)) * t_) * env(len(t_), .002, 5) * .6, s["t0"])
        for k_ in range(3): add(sf, tone(900 + 200 * k_, .08, 40, .15), s["t0"] + (0.05 + 0.12 * k_ if s["i"] == 0 else 0.3 + 0.15 * k_))
        nz = np.random.default_rng(2).normal(0, 1, int(.4 * SR)); add(sf, np.convolve(nz, np.ones(30) / 30, "same") * env(len(nz), .01, 6) * .5, s["rev"])
        add(sf, tone(1318.5, 1.0, 4.5, .45, ((1, 1), (2, .45), (3, .15))) + tone(1975.5, 1.0, 6, .24), s["rev"] + 0.3); add(sf, tone(520, .12, 30, .3) + tone(1040, .12, 35, .15), s["rev"])
    add(sf, wh, O["t0"] - 0.05)
    add(sf, tone(2093, 1.2, 3.5, .32, ((1, 1), (2, .3))) + tone(3136, 1.2, 5, .14), O["sub"])
    add(sf, wh, O["end"] - 0.02)
    ev = cv2.GaussianBlur(np.abs(voice).astype(np.float32).reshape(1, -1), (0, 0), sigmaX=SR * 0.06, sigmaY=0.01).ravel()
    duck = 1 - 0.45 * np.clip(ev / (ev.max() + 1e-9) * 3, 0, 1)
    mix = voice * 0.9 + spannung(total)[:N] * opt["--musik-pegel"] * duck + sf[:N] * 0.8
    k_ = int(0.02 * SR); mix[-k_:] *= np.linspace(1, 0, k_); mix = np.clip(mix / max(1, np.abs(mix).max() / 0.95), -1, 1)
    aw = os.path.join(WORK, "sq_mix.wav")
    with wave.open(aw, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(np.repeat((mix * 32767).astype(np.int16)[:, None], 2, axis=1).tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", aw, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5",
                    "-ar", "44100", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)
    with open(pre + "_zeiten.txt", "w", encoding="utf-8") as f:
        for s in segs: f.write(f"{s['t0']:05.2f}–{s['end']:05.2f} s  Frage {s['i'] + 1}: Stimme {s['vs']:.2f}, Countdown {s['c0']:.2f}–{s['c1']:.2f}, Auflösung {s['rev']:.2f}\n")
        f.write(f"{O['t0']:05.2f}–{O['end']:05.2f} s  Outro (Abo-Button + Bing {O['sub']:.2f})\n{total:05.2f} s  Ende -> Loop zu Frage 1\n")
    print(f"Fertig: {out} ({total:.2f} s)")

if __name__ == "__main__":
    main()
