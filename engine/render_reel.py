"""Render a FanartDesignsMX Reel (1080x1920) with seeded visual variations.

Approved template (Mega Mewtwo Y, Nov 2026): tilting card with no shine, visible
"Fanart Designs MX" watermark on the card, animated "Handmade Proxy Cards" title,
"ETSY Link in Bio" button, synced subtitles, English voice-over, original chiptune bed.
"""
import json
import math
import os
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "fonts")
FB = os.path.join(FONTS, "InterDisplay-Black.otf")
FX = os.path.join(FONTS, "InterDisplay-ExtraBold.otf")
FBOLD = os.path.join(FONTS, "InterDisplay-Bold.otf")
W, H, FPS = 1080, 1920, 30
YEL = (255, 216, 74)
ORG = (241, 100, 30)
WHITE = (255, 255, 255)
BASE_KEYS = {"handmade", "holographic", "holo", "25%", "25off", "binder", "honest", "proxy", "custom",
             "original", "etsy", "bio", "bio!", "link", "collection", "rare"}


# ---------------------------------------------------------------- helpers
def text_img(parts, size, font, stroke=0, stroke_col=(0, 0, 0), pad=30, shadow=True):
    f = ImageFont.truetype(font, size)
    widths = [f.getbbox(t, stroke_width=stroke)[2] for t, _ in parts]
    sp = int(size * 0.28)
    tw = sum(widths) + sp * (len(parts) - 1)
    th = int(size * 1.35)
    im = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = pad
    for (t, col), w in zip(parts, widths):
        if shadow:
            d.text((x + 4, pad + 6), t, font=f, fill=(0, 0, 0, 150), stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
        d.text((x, pad), t, font=f, fill=col + (255,), stroke_width=stroke, stroke_fill=stroke_col + (255,))
        x += w + sp
    a = np.array(im).astype(np.float32) / 255
    return np.dstack([a[..., 2], a[..., 1], a[..., 0], a[..., 3]])


def blit(dst, img, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.01 or scale <= 0.01:
        return
    h, w = img.shape[:2]
    if abs(scale - 1) > 1e-3:
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_LINEAR)
        h, w = img.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xa >= xb or ya >= yb:
        return
    sub = img[ya - y0:yb - y0, xa - x0:xb - x0]
    a = sub[..., 3:4] * alpha
    dst[ya:yb, xa:xb] = dst[ya:yb, xa:xb] * (1 - a) + sub[..., :3] * a


def ease_back(p):
    p = min(max(p, 0), 1)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def ease_out(p):
    p = min(max(p, 0), 1)
    return 1 - (1 - p) ** 3


def load_card(path):
    src = cv2.imread(path)
    if src is None:
        raise RuntimeError(f"cannot read card image {path}")
    h, w = src.shape[:2]
    if abs(w / h - 1) < 0.02:  # 2000x2000 Etsy mockup: card sits at this region
        s = w / 2000.0
        return src[int(140 * s):int(1860 * s), int(384 * s):int(1616 * s)]
    return src


def watermark(card, cw, ch):
    lay = Image.new("RGBA", (cw * 2, cw * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    f = ImageFont.truetype(FBOLD, int(cw * 0.105))
    txt = "Fanart Designs MX"
    bb = d.textbbox((0, 0), txt, font=f, stroke_width=2)
    d.text((cw - (bb[2] - bb[0]) / 2, cw - (bb[3] - bb[1]) / 2), txt, font=f,
           fill=(255, 255, 255, 105), stroke_width=2, stroke_fill=(20, 10, 40, 70))
    lay = lay.rotate(-52, resample=Image.BICUBIC)
    lay = lay.crop((cw - cw // 2, cw - int(ch * 0.40), cw - cw // 2 + cw, cw - int(ch * 0.40) + ch))
    a = np.array(lay).astype(np.float32) / 255
    return (card.astype(np.float32) * (1 - a[..., 3:4]) + a[..., [2, 1, 0]] * 255 * a[..., 3:4]).astype(np.uint8)


# ---------------------------------------------------------------- audio
def build_audio(voice_wav, dur, music_seed, out_wav):
    import soundfile as sf
    from scipy.signal import resample_poly
    from music import chiptune, duck, SR
    v, sr = sf.read(voice_wav)
    if v.ndim > 1:
        v = v.mean(1)
    tmp_v = out_wav + ".voice.wav"
    sf.write(tmp_v, v, sr)
    # voice polish (same chain as the approved Reel)
    proc = out_wav + ".voicep.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp_v, "-af",
                    "highpass=f=70,equalizer=f=170:t=q:w=0.9:g=1.5,equalizer=f=3200:t=q:w=1.2:g=-1,"
                    "highshelf=f=8000:g=-2,aecho=0.9:0.7:19|37:0.09|0.05,"
                    "acompressor=threshold=-20dB:ratio=2.2:attack=8:release=120,aresample=48000",
                    "-ar", "48000", "-ac", "1", proc], check=True)
    v, _ = sf.read(proc)
    n = int(dur * SR)
    v = np.pad(v, (0, max(0, n - len(v))))[:n]
    v = v / (np.abs(v).max() + 1e-9) * 0.9
    m, info = chiptune(dur, seed=music_seed)
    m = np.pad(m, (0, max(0, n - len(m))))[:n]
    m = duck(m, v) * 10 ** (-17 / 20)
    mix = v + m
    sf.write(out_wav + ".mix.wav", mix / max(1.0, np.abs(mix).max()), SR)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out_wav + ".mix.wav", "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", out_wav], check=True)
    for p in (tmp_v, proc, out_wav + ".mix.wav"):
        os.remove(p)
    return info


# ---------------------------------------------------------------- video
def render(card_path, meta, voice_wav, out_path, variant_seed=0, music_seed=0, highlight=(), cover_path=None,
           check_frames=None):
    rng = np.random.default_rng(variant_seed)
    V = {
        "tilt_deg": float(rng.uniform(12, 19)),
        "period": float(rng.uniform(3.6, 5.0)),
        "pitch_deg": float(rng.choice([0.0, rng.uniform(3, 6)])),
        "phase": float(rng.uniform(0, 2 * math.pi)),
        "card_w": int(rng.integers(596, 640)),
        "entrance": str(rng.choice(["rise", "zoom", "spin", "none"])),
        "bg": str(rng.choice(["dark", "tint", "pan"])),
        "zoom_dir": float(rng.choice([1, -1])),
        "title_anim": str(rng.choice(["pop", "slide", "drop"])),
        "title_hl": int(rng.integers(0, 2)),
        "pill": str(rng.choice(["outline", "filled"])),
        "subs": "keywords",  # approved Mega Mewtwo Y style only (no box/shading behind subtitles)
    }
    keys = BASE_KEYS | {h.lower() for h in highlight}
    D = math.ceil((meta["dur"] + 0.3) * FPS) / FPS
    N = int(D * FPS)

    # card
    card = load_card(card_path)
    cw = V["card_w"]
    ch = int(cw * card.shape[0] / card.shape[1])
    card = cv2.resize(card, (cw, ch), interpolation=cv2.INTER_AREA)
    card = watermark(card, cw, ch)
    am = np.zeros((ch, cw), np.uint8)
    r = int(cw * 0.042)
    cv2.rectangle(am, (r, 0), (cw - r, ch), 255, -1)
    cv2.rectangle(am, (0, r), (cw, ch - r), 255, -1)
    for cx, cy in [(r, r), (cw - r, r), (r, ch - r), (cw - r, ch - r)]:
        cv2.circle(am, (cx, cy), r, 255, -1, cv2.LINE_AA)
    am = cv2.erode(am, np.ones((3, 3), np.uint8))
    cardA = np.dstack([card, am]).astype(np.float32) / 255

    # background
    hh, ww = card.shape[:2]
    bw = int(hh * 0.55 * 9 / 16)
    bx = (ww - bw) // 2
    bgs = card[int(hh * 0.12):int(hh * 0.67), max(0, bx):bx + bw]
    bg = cv2.GaussianBlur(cv2.resize(bgs, (W, H)), (0, 0), 38).astype(np.float32) / 255
    if V["bg"] == "dark":
        bg *= 0.5
    elif V["bg"] == "tint":
        mean = bg.reshape(-1, 3).mean(0)
        grad = np.linspace(0.65, 0.25, H)[:, None, None]
        bg = bg * 0.35 + mean[None, None, :] * grad
    else:
        bg *= 0.48
    bg = np.clip(bg, 0, 1)

    # title
    hl = YEL
    words = [("Handmade", hl if V["title_hl"] == 0 else WHITE), ("Proxy", WHITE if V["title_hl"] == 0 else hl), ("Cards", WHITE)]
    TS = 92
    while True:
        fT = ImageFont.truetype(FB, TS)
        wid = [fT.getbbox(w[0], stroke_width=3)[2] for w in words]
        sp = int(TS * 0.28)
        tot = sum(wid) + sp * 2
        if tot <= 880:
            break
        TS -= 2
    wimgs = [text_img([w], TS, FB, stroke=3) for w in words]
    wx = []
    x = W / 2 - tot / 2
    for w_ in wid:
        wx.append(x + w_ / 2)
        x += w_ + sp
    TOPY = 285

    # pill
    if V["pill"] == "outline":
        pill_txt = text_img([("ETSY", ORG), ("Link in Bio", WHITE)], 64, FB, stroke=0, shadow=False, pad=0)
        fill, outline = (15, 15, 20, 215), (241, 100, 30, 255)
    else:
        pill_txt = text_img([("ETSY", WHITE), ("Link in Bio", WHITE)], 64, FB, stroke=0, shadow=False, pad=0)
        fill, outline = (241, 100, 30, 240), (255, 255, 255, 255)
    ph, pw = pill_txt.shape[:2]
    PW, PH = pw + 90, ph + 26
    pim = Image.new("RGBA", (PW + 20, PH + 20), (0, 0, 0, 0))
    ImageDraw.Draw(pim).rounded_rectangle((10, 10, 10 + PW, 10 + PH), radius=PH // 2, fill=fill, outline=outline, width=5)
    pa = np.array(pim).astype(np.float32) / 255
    pill = np.dstack([pa[..., 2], pa[..., 1], pa[..., 0], pa[..., 3]])
    oy, ox = (pill.shape[0] - ph) // 2 + 2, (pill.shape[1] - pw) // 2
    reg = pill[oy:oy + ph, ox:ox + pw]
    a = pill_txt[..., 3:4]
    reg[..., :3] = reg[..., :3] * (1 - a) + pill_txt[..., :3] * a
    reg[..., 3:4] = np.maximum(reg[..., 3:4], a)
    PILLY = 1530

    # subtitles
    def sub_img(text):
        tokens = text.split()
        allhl = text.lower().startswith(("link", "shop", "tap", "check the link", "find"))
        parts = [(w, YEL if (allhl or w.strip(",.!?:").lower() in keys) else WHITE) for w in tokens]
        sz = 72
        while sz > 56:
            f = ImageFont.truetype(FX, sz)
            w = sum(f.getbbox(p[0], stroke_width=8)[2] for p in parts) + int(sz * 0.28) * (len(parts) - 1)
            if w <= 940:
                break
            sz -= 2
        if V["subs"] == "box":
            img = text_img([(p[0], WHITE if p[1] == WHITE else YEL) for p in parts], sz, FX, stroke=0, pad=26, shadow=False)
            box = np.zeros_like(img)
            box[..., :3] = 0.05
            box[..., 3] = 0.62
            hb, wb = box.shape[:2]
            rr = 28
            m = np.zeros((hb, wb), np.uint8)
            cv2.rectangle(m, (rr, 0), (wb - rr, hb), 255, -1)
            cv2.rectangle(m, (0, rr), (wb, hb - rr), 255, -1)
            for cx_, cy_ in [(rr, rr), (wb - rr, rr), (rr, hb - rr), (wb - rr, hb - rr)]:
                cv2.circle(m, (cx_, cy_), rr, 255, -1, cv2.LINE_AA)
            box[..., 3] *= m / 255
            a2 = img[..., 3:4]
            out = box.copy()
            out[..., :3] = box[..., :3] * (1 - a2) + img[..., :3] * a2
            out[..., 3:4] = np.maximum(box[..., 3:4], a2)
            return out
        return text_img(parts, sz, FX, stroke=8, pad=24)

    ss = meta["subs"]
    subs = []
    for k, s_ in enumerate(ss):
        t1 = ss[k + 1]["t0"] if k + 1 < len(ss) and ss[k + 1]["t0"] - s_["t1"] < 0.5 else (D + 1 if k == len(ss) - 1 else s_["t1"])
        subs.append((s_["t0"], t1, sub_img(s_["text"])))
    SUBY = 1395
    last_t0 = ss[-1]["t0"] if ss else D

    tmpdir = tempfile.mkdtemp()
    audio = os.path.join(tmpdir, "audio.wav")
    music_info = build_audio(voice_wav, D, music_seed, audio)

    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", audio, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-t", f"{D:.3f}",
                           "-movflags", "+faststart", out_path], stdin=subprocess.PIPE)
    fpx = 2600
    cover_t = None
    for i in range(N):
        t = i / FPS
        z = 1.04 + 0.05 * (t / D if V["zoom_dir"] > 0 else 1 - t / D)
        dx = (18 * math.sin(t * 0.35)) if V["bg"] == "pan" else 0
        M = np.float32([[z, 0, W / 2 * (1 - z) + dx], [0, z, H / 2 * (1 - z)]])
        fr = cv2.warpAffine(bg, M, (W, H), borderMode=cv2.BORDER_REFLECT)

        # card motion + entrance
        th = math.radians(V["tilt_deg"]) * math.sin(2 * math.pi * t / V["period"] + V["phase"])
        pt = math.radians(V["pitch_deg"]) * math.sin(2 * math.pi * t / (V["period"] * 1.7))
        sc = 1.0
        oyy = 0.0
        pe = ease_out(t / 0.7)
        if V["entrance"] == "rise":
            oyy = (1 - pe) * 520
        elif V["entrance"] == "zoom":
            sc = 0.55 + 0.45 * ease_back(t / 0.7)
        elif V["entrance"] == "spin":
            th += (1 - pe) * math.radians(85)
        ccx = W / 2 + 8 * math.sin(t * 0.9)
        ccy = 850 + 10 * math.sin(t * 1.4) + oyy

        def P(u, v_):
            u, v_ = u * sc, v_ * sc
            zz = u * math.sin(th) + v_ * math.sin(pt)
            p = fpx / (fpx + zz)
            return [ccx + u * math.cos(th) * p, ccy + v_ * math.cos(pt) * p]

        dst = np.float32([P(-cw / 2, -ch / 2), P(cw / 2, -ch / 2), P(cw / 2, ch / 2), P(-cw / 2, ch / 2)])
        Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]]), dst)
        sh = np.zeros((H, W), np.float32)
        cv2.fillConvexPoly(sh, (dst + [0, 30]).astype(np.int32), 1.0)
        sh = cv2.GaussianBlur(sh, (0, 0), 30)[..., None] * 0.6
        fr = fr * (1 - sh)
        wc = cv2.warpPerspective(cardA, Hm, (W, H), flags=cv2.INTER_LINEAR)
        a = wc[..., 3:4]
        fr = fr * (1 - a) + wc[..., :3] * a

        # title
        for k, (img, x) in enumerate(zip(wimgs, wx)):
            st = 0.15 + 0.18 * k
            p = (t - st) / 0.38
            al = min(max(p * 2.5, 0), 1)
            breathe = 1 + 0.025 * math.sin((t - 1.2) * 2.4 + k * 0.6)
            if V["title_anim"] == "pop":
                s_ = ease_back(p) if p < 1 else breathe
                blit(fr, img, x, TOPY + (0 if p >= 1 else (1 - min(max(p, 0), 1)) * -40), s_, al)
            elif V["title_anim"] == "slide":
                xo = (1 - ease_out(p)) * -(W * 0.6) if p < 1 else 0
                blit(fr, img, x + xo, TOPY, breathe if p >= 1 else 1.0, al)
            else:
                yo = (1 - ease_back(p)) * -160 if p < 1 else 0
                blit(fr, img, x, TOPY + yo, breathe if p >= 1 else 1.0, al)
        ph_ = ((t - 1.0) % 3.0) / 0.9
        if t > 1.0 and ph_ < 1:
            sx = W / 2 - tot / 2 - 150 + ph_ * (tot + 300)
            xs = np.arange(W)[None, :]
            ys = np.arange(170)[:, None]
            band = np.clip(1 - np.abs((xs - sx) - (ys - 85) * 0.5) / 45, 0, 1) * 0.55
            reg = fr[TOPY - 85:TOPY + 85]
            m = (reg.mean(2) > 0.55).astype(np.float32)
            reg += (band * m)[..., None]

        # pill
        p = (t - 0.8) / 0.45
        if p > 0:
            e = ease_back(min(p, 1))
            y = PILLY + (1 - min(p, 1)) * 120
            pulse = 1 + 0.045 * max(0, math.sin((t - 1.3) * math.pi / 1.0)) ** 8 if t > 1.3 else e
            if t > last_t0:
                pulse = 1 + 0.07 * abs(math.sin((t - last_t0) * 5))
            blit(fr, pill, W / 2, y, pulse if p >= 1 else e, min(p * 2, 1))

        # subtitles
        for t0, t1, img in subs:
            if t0 <= t < t1:
                q = (t - t0) / 0.12
                blit(fr, img, W / 2, SUBY, 0.86 + 0.14 * ease_back(min(q, 1)) if q < 1 else 1.0, min(q * 1.5, 1))

        frame = (np.clip(fr, 0, 1) * 255).astype(np.uint8)
        ff.stdin.write(frame.tobytes())
        if cover_path and cover_t is None and len(ss) > 1 and t >= ss[1]["t0"] + 0.3:
            cv2.imwrite(cover_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            cover_t = t
        if check_frames and i in check_frames:
            cv2.imwrite(check_frames[i], frame)
    ff.stdin.close()
    ff.wait()
    if ff.returncode != 0:
        raise RuntimeError("ffmpeg failed")
    return {"duration": D, "variant": V, "music": music_info}
