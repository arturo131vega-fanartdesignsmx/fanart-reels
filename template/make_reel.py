import cv2, numpy as np, json, subprocess, sys, math
from PIL import Image, ImageDraw, ImageFont
W, H, FPS = 1080, 1920, 30
mock, subs_json, wav, out = sys.argv[1:5]
FB = '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf'
FX = '/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf'
YEL = (255, 216, 74); ORG = (241, 100, 30)
meta = json.load(open(subs_json)); D = math.ceil((meta['dur'] + 0.3) * FPS) / FPS
N = int(D * FPS)
src = cv2.imread(mock)
if abs(src.shape[1] / src.shape[0] - 1) < 0.02:      # 2000x2000 mockup -> crop card
    card = src[140:1860, 384:1616]
else:                                                  # clean design file (full card)
    card = src
cw = 620; ch = int(cw * card.shape[0] / card.shape[1])
card = cv2.resize(card, (cw, ch), interpolation=cv2.INTER_AREA)
# --- visible watermark baked into the card (moves with it) ---
_wl = Image.new('RGBA', (cw * 2, cw * 2), (0, 0, 0, 0)); _wd = ImageDraw.Draw(_wl)
_wf = ImageFont.truetype('/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf', int(cw * 0.105))
_wt = 'Fanart Designs MX'; _bb = _wd.textbbox((0, 0), _wt, font=_wf, stroke_width=2)
_wd.text((cw - (_bb[2] - _bb[0]) / 2, cw - (_bb[3] - _bb[1]) / 2), _wt, font=_wf, fill=(255, 255, 255, 105), stroke_width=2, stroke_fill=(20, 10, 40, 70))
_wl = _wl.rotate(-52, resample=Image.BICUBIC)
_wl = _wl.crop((cw - cw // 2, cw - int(ch * 0.40), cw - cw // 2 + cw, cw - int(ch * 0.40) + ch))
_wa = np.array(_wl).astype(np.float32) / 255
card = (card.astype(np.float32) * (1 - _wa[..., 3:4]) + _wa[..., [2, 1, 0]] * 255 * _wa[..., 3:4]).astype(np.uint8)
am = np.zeros((ch, cw), np.uint8); r = int(cw * 0.042)
cv2.rectangle(am, (r, 0), (cw - r, ch), 255, -1); cv2.rectangle(am, (0, r), (cw, ch - r), 255, -1)
for cx, cy in [(r, r), (cw - r, r), (r, ch - r), (cw - r, ch - r)]: cv2.circle(am, (cx, cy), r, 255, -1, cv2.LINE_AA)
am = cv2.erode(am, np.ones((3, 3), np.uint8))
cardA = np.dstack([card, am]).astype(np.float32) / 255
# background: blurred centre of the art, filled to 9:16
hh, ww = card.shape[:2]; bw = int(hh * 0.55 * 9 / 16); bx = (ww - bw) // 2
bgs = card[int(hh * 0.12):int(hh * 0.67), max(0, bx):bx + bw]
bg = cv2.resize(bgs, (W, H)); bg = cv2.GaussianBlur(bg, (0, 0), 38).astype(np.float32) / 255 * 0.5

def text_img(parts, size, font, stroke=0, stroke_col=(0, 0, 0), pad=30, shadow=True):
    f = ImageFont.truetype(font, size)
    widths = [f.getbbox(t, stroke_width=stroke)[2] for t, _ in parts]
    sp = int(size * 0.28); tw = sum(widths) + sp * (len(parts) - 1); th = int(size * 1.35)
    im = Image.new('RGBA', (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = pad
    for (t, col), w in zip(parts, widths):
        if shadow: d.text((x + 4, pad + 6), t, font=f, fill=(0, 0, 0, 150), stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
        d.text((x, pad), t, font=f, fill=col + (255,), stroke_width=stroke, stroke_fill=stroke_col + (255,))
        x += w + sp
    a = np.array(im).astype(np.float32) / 255
    return np.dstack([a[..., 2], a[..., 1], a[..., 0], a[..., 3]])  # BGRA

def blit(dst, img, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.01 or scale <= 0.01: return
    h, w = img.shape[:2]
    if abs(scale - 1) > 1e-3: img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_LINEAR); h, w = img.shape[:2]
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xa >= xb or ya >= yb: return
    sub = img[ya - y0:yb - y0, xa - x0:xb - x0]; a = sub[..., 3:4] * alpha
    dst[ya:yb, xa:xb] = dst[ya:yb, xa:xb] * (1 - a) + sub[..., :3] * a

def ease_back(p):  # overshoot pop
    p = min(max(p, 0), 1); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2

# top title words
words = [('Handmade', YEL), ('Proxy', (255, 255, 255)), ('Cards', (255, 255, 255))]
TS = 92
while True:
    fT = ImageFont.truetype(FB, TS); wid = [fT.getbbox(w[0], stroke_width=3)[2] for w in words]; sp = int(TS*0.28); tot = sum(wid) + sp * 2
    if tot <= 880: break
    TS -= 2
wimgs = [text_img([w], TS, FB, stroke=3) for w in words]
print('title size', TS, tot)
wx = []; x = W / 2 - tot / 2
for w in wid: wx.append(x + w / 2); x += w + sp
TOPY = 285
# bottom pill
pill_txt = text_img([('ETSY', ORG), ('Link in Bio', (255, 255, 255))], 64, FB, stroke=0, shadow=False, pad=0)
ph, pw = pill_txt.shape[:2]; PW, PH = pw + 90, ph + 26
pim = Image.new('RGBA', (PW + 20, PH + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(pim)
d.rounded_rectangle((10, 10, 10 + PW, 10 + PH), radius=PH // 2, fill=(15, 15, 20, 215), outline=(241, 100, 30, 255), width=5)
pa = np.array(pim).astype(np.float32) / 255; pill = np.dstack([pa[..., 2], pa[..., 1], pa[..., 0], pa[..., 3]])
oy, ox = (pill.shape[0] - ph) // 2 + 2, (pill.shape[1] - pw) // 2
reg = pill[oy:oy + ph, ox:ox + pw]; a = pill_txt[..., 3:4]
reg[..., :3] = reg[..., :3] * (1 - a) + pill_txt[..., :3] * a; reg[..., 3:4] = np.maximum(reg[..., 3:4], a)
PILLY = 1530
# subtitles
KEY = ['handmade', 'holographic', '25%', '25OFF', "link's", 'link', 'in', 'my', 'bio', 'binder', 'honest']
def sub_img(text):
    low = text.lower(); fin = low.startswith("link's")
    parts = [(w, YEL if (fin or w.strip(',.!?').lower() in ['handmade', 'holographic', '25%', '25off', 'binder', 'honest']) else (255, 255, 255)) for w in text.split()]
    sz = 72
    while sz > 56:
        f = ImageFont.truetype(FX, sz); w = sum(f.getbbox(p[0], stroke_width=8)[2] for p in parts) + int(sz * 0.28) * (len(parts) - 1)
        if w <= 940: break
        sz -= 2
    return text_img(parts, sz, FX, stroke=8, pad=24)
ss = meta['subs']
subs = []
for k, x in enumerate(ss):
    t1 = ss[k+1]['t0'] if k+1 < len(ss) and ss[k+1]['t0'] - x['t1'] < 0.5 else (D + 1 if k == len(ss)-1 else x['t1'])
    subs.append((x['t0'], t1, sub_img(x['text'])))
SUBY = 1395

ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                       '-i', wav, '-af', 'apad',
                       '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000',
                       '-t', f'{D:.3f}', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
for i in range(N):
    t = i / FPS
    z = 1.04 + 0.05 * t / D
    M = np.float32([[z, 0, W / 2 * (1 - z)], [0, z, H / 2 * (1 - z)]])
    fr = cv2.warpAffine(bg, M, (W, H), borderMode=cv2.BORDER_REFLECT)
    # card perspective
    th = math.radians(17) * math.sin(2 * math.pi * t / 4.3)
    ccx = W / 2 + 8 * math.sin(t * 0.9); ccy = 850 + 10 * math.sin(t * 1.4); fpx = 2600
    def P(u, v):
        zz = u * math.sin(th); p = fpx / (fpx + zz); return [ccx + u * math.cos(th) * p, ccy + v * p]
    dst = np.float32([P(-cw / 2, -ch / 2), P(cw / 2, -ch / 2), P(cw / 2, ch / 2), P(-cw / 2, ch / 2)])
    Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [cw, 0], [cw, ch], [0, ch]]), dst)
    # shadow
    sh = np.zeros((H, W), np.float32); cv2.fillConvexPoly(sh, (dst + [0, 30]).astype(np.int32), 1.0)
    sh = cv2.GaussianBlur(sh, (0, 0), 30)[..., None] * 0.6; fr = fr * (1 - sh)
    wc = cv2.warpPerspective(cardA, Hm, (W, H), flags=cv2.INTER_LINEAR)
    a = wc[..., 3:4]; fr = fr * (1 - a) + wc[..., :3] * a
    # title words: staggered pop, then breathing
    for k, (img, x) in enumerate(zip(wimgs, wx)):
        st = 0.15 + 0.18 * k; p = (t - st) / 0.38
        sc = ease_back(p) if p < 1 else 1 + 0.025 * math.sin((t - 1.2) * 2.4 + k * 0.6)
        al = min(max(p * 2.5, 0), 1)
        blit(fr, img, x, TOPY + (0 if p >= 1 else (1 - min(max(p, 0), 1)) * -40), sc, al)
    # shine sweep across the title every 3 s
    ph_ = ((t - 1.0) % 3.0) / 0.9
    if t > 1.0 and ph_ < 1:
        sx = W / 2 - tot / 2 - 150 + ph_ * (tot + 300)
        band = np.zeros((170, W), np.float32)
        xs = np.arange(W)[None, :]; ys = np.arange(170)[:, None]
        band = np.clip(1 - np.abs((xs - sx) - (ys - 85) * 0.5) / 45, 0, 1) * 0.55
        reg = fr[TOPY - 85:TOPY + 85]
        # mask by bright title pixels only
        lum = reg.mean(2)
        m = (lum > 0.55).astype(np.float32)
        reg += (band * m)[..., None]
    # bottom pill: slide up + periodic pulse
    p = (t - 0.8) / 0.45
    if p > 0:
        e = ease_back(min(p, 1)); y = PILLY + (1 - min(p, 1)) * 120
        pulse = 1 + 0.045 * max(0, math.sin((t - 1.3) * math.pi / 1.0)) ** 8 if t > 1.3 else e
        if t > meta['subs'][-1]['t0']: pulse = 1 + 0.07 * abs(math.sin((t - meta['subs'][-1]['t0']) * 5))
        blit(fr, pill, W / 2, y, pulse if p >= 1 else e, min(p * 2, 1))
    # subtitles
    for t0, t1, img in subs:
        if t0 <= t < t1:
            q = (t - t0) / 0.12
            blit(fr, img, W / 2, SUBY, 0.86 + 0.14 * ease_back(min(q, 1)) if q < 1 else 1.0, min(q * 1.5, 1))
    ff.stdin.write((np.clip(fr, 0, 1) * 255).astype(np.uint8).tobytes())
    if i in (5, 45, 120, 300, N - 5): cv2.imwrite(f'chk_{i}.jpg', (np.clip(fr, 0, 1) * 255).astype(np.uint8))
ff.stdin.close(); ff.wait(); print('done', N, D)
